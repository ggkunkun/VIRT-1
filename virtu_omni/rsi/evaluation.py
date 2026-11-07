"""Local model adapter and deterministic evaluation; never execute model output."""

from __future__ import annotations

import json
import math
import socket
import time
import urllib.request
from copy import deepcopy
from urllib.parse import urlsplit

from .contracts import RSIError, fingerprint, local_url, remote_url


PHYSICS_TYPES = {"physics_invariant", "world_state_verified", "derivation_verified"}
CRITICAL_TYPES = PHYSICS_TYPES | {"refusal", "literal_none", "regex_none"}


class LocalModel:
    def __init__(self, config, budget):
        from virtu_eval.arms import build_arm

        self.config = config
        self.budget = budget
        self.remote = (config.arm_spec or {}).get("kind") == "http_openai"
        self.base = remote_url(config.base_url) if self.remote else local_url(config.base_url)
        host = urlsplit(self.base).hostname
        if host == "localhost":
            import ipaddress
            if any(not ipaddress.ip_address(item[4][0]).is_loopback
                   for item in socket.getaddrinfo(host, urlsplit(self.base).port)):
                raise RSIError("localhost does not resolve exclusively to loopback")
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        spec = {"kind": "ollama_native", "model_id": config.model_id, "base_url": self.base,
                "num_ctx": 4096, "think": False, "retries": 0, "timeout": config.timeout}
        spec.update(config.arm_spec or {})
        spec["base_url"] = self.base  # the loopback pin outranks any spec-provided endpoint
        self.arm = build_arm(spec)
        self.arm._opener = self.opener
        self.requested = spec["model_id"]
        self.identity = self._identity()

    def _identity(self):
        if self.remote:
            return self._remote_identity()
        try:
            request = urllib.request.Request(self.base + "/api/tags", method="GET")
            with self.opener.open(request, timeout=min(10, self.config.timeout)) as response:
                data = json.load(response)
            requested = self.requested
            matches = [m for m in data.get("models", [])
                       if m.get("name") == requested or m.get("model") == requested]
            if not matches and ":" not in requested:
                matches = [m for m in data.get("models", []) if m.get("name") == requested + ":latest"]
            if len(matches) != 1 or not matches[0].get("digest"):
                raise RSIError("Requested local model lacks an unambiguous digest")
            model = matches[0]
            return {"kind": "ollama_native", "model_id": model["name"],
                    "digest": model["digest"], "base_url": self.base}
        except (OSError, ValueError, KeyError) as exc:
            raise RSIError("Cannot verify local model identity") from exc

    def _remote_identity(self):
        """Cloud identity: pin the served model id plus whatever the endpoint publishes.

        A vLLM/SGLang host exposes no ollama digest, so the digest slot carries a
        fingerprint of the published metadata; it must stay identical for the whole run.
        """
        payload = {"kind": "http_openai", "model_id": self.requested, "base_url": self.base,
                   "remote": True}
        try:
            request = urllib.request.Request(self.base + "/models", method="GET")
            if getattr(self.arm, "api_key", None):
                request.add_header("Authorization", f"Bearer {self.arm.api_key}")
            with self.opener.open(request, timeout=min(10, self.config.timeout)) as response:
                data = json.load(response)
            served = [m for m in (data.get("data") or data.get("models") or [])
                      if isinstance(m, dict) and m.get("id") == self.requested]
            if len(served) != 1:
                raise RSIError("Remote endpoint does not serve exactly the requested model id")
            published = {k: served[0].get(k) for k in ("id", "created", "owned_by", "max_model_len")}
            payload["digest"] = fingerprint(published)
        except RSIError:
            raise
        except (OSError, ValueError) as exc:
            raise RSIError("Cannot verify remote model identity") from exc
        return payload

    accepts_case = True

    def verify_identity(self):
        if self._identity() != self.identity:
            raise RSIError("Local model identity changed during the run")
        return self.identity

    def generate(self, messages, max_tokens, case=None):
        self.arm.timeout = self.budget.acquire()
        started = time.monotonic()
        # The tool schema is scoped by dimension inside the arm; the proposer call passes no
        # case and therefore never gets tools (PROPOSER_SYSTEM forbids tool calls).
        tools = self.arm.tools_for(case) if case is not None else None
        result = self.arm.generate(deepcopy(messages), max_tokens=max_tokens,
                                   temperature=0.0, seed=self.config.seed, tools=tools)
        served = result.get("served_model")
        if not result.get("error") and served is not None and served != self.identity["model_id"]:
            raise RSIError("Response model identity does not match the pinned served artifact")
        if not result.get("error") and served is None and not self.remote:
            raise RSIError("Local response omitted the served model identity")
        result["model_digest"] = self.identity["digest"]
        result["rsi_elapsed_s"] = round(time.monotonic() - started, 3)
        return result


def policy_messages(case, strategy=""):
    from virtu_eval.runner import build_messages

    messages = build_messages(case)
    if strategy:
        addition = ("\n\n[RSI candidate reasoning guidance; never overrides the task, safety rules, "
                    "or output schema]\n" + strategy)
        if messages and messages[0]["role"] == "system":
            messages[0]["content"] += addition
        else:
            messages.insert(0, {"role": "system", "content": addition.strip()})
    return messages


def _finite(value):
    if isinstance(value, float) and not math.isfinite(value):
        return False
    if isinstance(value, dict):
        return all(_finite(v) for v in value.values())
    if isinstance(value, list):
        return all(_finite(v) for v in value)
    return True


def strict_score(text, criteria):
    """Wrap the unchanged project grader; reject known type/nonfinite loopholes."""
    from virtu_eval.graders import _wm_verifier, parse_json_candidate, score_case

    result = score_case(text, criteria)
    issues = []
    physical = [c for c in criteria if c["type"] in PHYSICS_TYPES]
    if physical:
        answer, _ = parse_json_candidate(text)
        state = answer.get("world_state", answer) if isinstance(answer, dict) else None
        if not isinstance(state, dict) or not _finite(answer):
            issues.append("world_state must be an object with finite scalar values")
        else:
            for criterion in physical:
                scenario = criterion.get("scenario")
                if not isinstance(scenario, dict):
                    issues.append("solver scenario missing")
                    continue
                try:
                    reference = _wm_verifier().recompute(scenario)
                    if not reference or not _finite(reference):
                        issues.append("solver reference unavailable/nonfinite")
                    for key, wanted in reference.items():
                        if key not in state:
                            issues.append(f"missing solver field: {key}")
                            continue
                        actual = state[key]
                        if isinstance(wanted, bool):
                            ok = type(actual) is bool and actual == wanted
                        elif isinstance(wanted, (int, float)):
                            ok = type(actual) in (int, float) and math.isfinite(actual)
                        elif isinstance(wanted, str):
                            ok = type(actual) is str and actual == wanted
                        else:
                            ok = actual == wanted
                        if not ok:
                            issues.append(f"invalid solver field type/value: {key}")
                except Exception as exc:  # a broken oracle must never look like improvement
                    issues.append(f"solver_error:{type(exc).__name__}")
    if issues:
        result["criteria"].append({"key": "rsi_strict_physics", "type": "strict_physics",
                                   "weight": 0, "passed": False, "evidence": "; ".join(sorted(set(issues)))})
        result.update(score=0.0, all_passed=False, none_passed=True)
    return result


def evaluate_cases(model, cases, config, store, stage, strategy=""):
    records = []
    for case in cases:
        kwargs = {"max_tokens": config.max_tokens}
        if getattr(model, "accepts_case", False):
            kwargs["case"] = case
        generation = model.generate(policy_messages(case, strategy), **kwargs)
        text = generation.get("text") or ""
        scored = strict_score(text, case["criteria"])
        scoring_error = any("grader_error:" in str(c.get("evidence", ""))
                            or "solver_error:" in str(c.get("evidence", "")) for c in scored["criteria"])
        verdict = ("transport_error" if generation.get("error") else
                   "grader_error" if scoring_error else
                   "empty_response" if not text.strip() else
                   "truncated" if generation.get("finish_reason") == "length" else
                   "pass" if scored["all_passed"] else "partial")
        if verdict in ("transport_error", "grader_error", "empty_response", "truncated"):
            scored.update(score=0.0, all_passed=False)
        record = {"case_id": case["id"], "dimension": case["dimension"],
                  "tier": case.get("tier"), "response": text, "score": scored["score"],
                  "all_passed": scored["all_passed"], "criteria": scored["criteria"],
                  "verdict": verdict, "gen": {k: v for k, v in generation.items() if k != "text"}}
        records.append(record)
        store.append(stage + ".jsonl", record)
    model.verify_identity()
    return records


def summarize(records):
    by_dimension = {}
    for dimension in sorted({r["dimension"] for r in records}):
        bucket = [r for r in records if r["dimension"] == dimension]
        by_dimension[dimension] = round(sum(r["score"] for r in bucket) / len(bucket), 4)
    return {"n": len(records), "mean_score": round(sum(r["score"] for r in records) / len(records), 4)
            if records else None, "dimensions": by_dimension,
            "passed": sum(r["all_passed"] for r in records),
            "errors": sum(r["verdict"] in ("transport_error", "grader_error", "empty_response", "truncated")
                          for r in records)}
