#!/usr/bin/env python
"""Drive one RSI run against a non-loopback OpenAI-compatible endpoint.

The local loop pins RSI to loopback by default; a cloud arm is never the default and
must be opted into. This entry keeps that opt-in in exactly one place, so the run that
reaches the cloud is the run a human can read back from `runs/rsi/<ts>_<id>/`.

Environment (nothing else is read):
  VIRTU_RSI_BASE_URL   required  e.g. https://host:8000/v1   (bare origin or /v1 only)
  VIRTU_RSI_MODEL_ID   required  the id the endpoint actually serves
  VIRTU_EVAL_API_KEY   optional  bearer token; never written to disk
  VIRTU_API_KEY        optional  fallback for the same token
  VIRTU_RSI_CASE_DIR   optional  default data/benchmark/virtu_rsi_pool_v2
  VIRTU_RSI_DIMS       optional  comma separated, default the seven measured dimensions
  VIRTU_RSI_MAX_CALLS  optional  default 160
  VIRTU_RSI_MAX_SECONDS optional default 7200
  VIRTU_RSI_ROUNDS     optional  default 2
  VIRTU_RSI_MAX_TOKENS optional  default 256
  VIRTU_RSI_SEED       optional  default 20261106

Usage:
  python cloud_train_pack/rsi_cloud_entry.py --probe     # identity + one scored call
  python cloud_train_pack/rsi_cloud_entry.py             # full bounded run
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from virtu_omni.rsi import cli as rsi_cli  # noqa: E402
from virtu_omni.rsi.contracts import Config, RSIError, remote_url  # noqa: E402

DEFAULT_DIMS = ("reasoning", "knowledge", "instruction", "generation",
                "generalization", "boundary", "toolcall")
DEFAULT_CASE_DIR = "data/benchmark/virtu_rsi_pool_v2"
# The served profile is the measured one: same tool schema the toolcall board uses, and
# the same context the 13.63B MoE is actually run with. num_gpu is dropped because a
# remote host owns the placement.
PROFILE_SOURCE = "virtu_moe_14b"


def _env_int(env, name, default):
    raw = env.get(name)
    if raw is None or raw.strip() == "":
        return default
    return int(raw)


def served_profile(root, model_id):
    """Tool schema from the measured arm registry, retargeted at the cloud model id."""
    try:
        spec = rsi_cli.load_arm(root, PROFILE_SOURCE)
    except RSIError:
        spec = {}
    profile = {k: v for k, v in spec.items() if k in ("tools", "tools_dimensions")}
    profile.update({"kind": "http_openai", "model_id": model_id,
                    "num_ctx": 8192, "think": False, "retries": 1})
    return profile


def _reject_loopback(url):
    """A cloud run that points at this box is a local run wearing the wrong label."""
    import ipaddress
    from urllib.parse import urlsplit

    host = urlsplit(url).hostname or ""
    if host == "localhost":
        raise RSIError("VIRTU_RSI_BASE_URL points at loopback; run the local arm instead")
    try:
        if ipaddress.ip_address(host).is_loopback:
            raise RSIError("VIRTU_RSI_BASE_URL points at loopback; run the local arm instead")
    except ValueError:
        pass


def build_config(root, env=None):
    """Assemble the one Config object a cloud run is allowed to use."""
    env = os.environ if env is None else env
    base_url = (env.get("VIRTU_RSI_BASE_URL") or "").strip()
    model_id = (env.get("VIRTU_RSI_MODEL_ID") or "").strip()
    if not base_url:
        raise RSIError("VIRTU_RSI_BASE_URL is required for a cloud run")
    if not model_id:
        raise RSIError("VIRTU_RSI_MODEL_ID is required for a cloud run")
    _reject_loopback(base_url)
    dims = tuple(d.strip() for d in (env.get("VIRTU_RSI_DIMS") or "").split(",") if d.strip())
    case_dir = (env.get("VIRTU_RSI_CASE_DIR") or DEFAULT_CASE_DIR).strip()
    config = Config(
        case_dir=case_dir,
        dimensions=dims or DEFAULT_DIMS,
        model_id=model_id,
        base_url=base_url,
        allow_remote=True,                     # the single, explicit cloud opt-in
        arm_spec=served_profile(root, model_id),
        rounds=_env_int(env, "VIRTU_RSI_ROUNDS", 2),
        seed=_env_int(env, "VIRTU_RSI_SEED", 20261106),
        max_calls=_env_int(env, "VIRTU_RSI_MAX_CALLS", 160),
        max_seconds=_env_int(env, "VIRTU_RSI_MAX_SECONDS", 7200),
        max_tokens=_env_int(env, "VIRTU_RSI_MAX_TOKENS", 256),
        timeout=_env_int(env, "VIRTU_RSI_TIMEOUT", 180),
    )
    return config


def probe(config):
    """Fail before the loop starts when identity or a single call cannot be measured."""
    from virtu_omni.rsi.contracts import Budget
    from virtu_omni.rsi.evaluation import LocalModel

    budget = Budget(config)
    budget.acquire()
    model = LocalModel(config, budget)
    started = time.monotonic()
    result = model.generate([{"role": "user", "content": "Reply with the single word: ready"}],
                            max_tokens=16)
    return {
        "endpoint": remote_url(config.base_url),
        "requested_model_id": model.requested,
        "identity": model.identity,
        "error": result.get("error"),
        "served_model": result.get("served_model"),
        "text": (result.get("text") or "")[:120],
        "elapsed_s": round(time.monotonic() - started, 2),
        "budget": budget.snapshot(),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="RSI against a cloud OpenAI-compatible arm")
    parser.add_argument("--probe", action="store_true",
                        help="verify identity and one scored call, then stop")
    parser.add_argument("--dry-run", action="store_true",
                        help="build and print the config without contacting the endpoint")
    args = parser.parse_args(argv)

    try:
        config = build_config(ROOT)
    except RSIError as exc:
        print(json.dumps({"blocked": str(exc)}, ensure_ascii=False))
        return 2

    if args.dry_run:
        snap = config.snapshot()
        snap["arm_spec"] = {k: (f"<{len(v)} items>" if isinstance(v, list) else v)
                            for k, v in snap["arm_spec"].items()}
        print(json.dumps({"config": snap}, ensure_ascii=False, indent=2, default=str))
        return 0

    if args.probe:
        print(json.dumps({"probe": probe(config)}, ensure_ascii=False, indent=2, default=str))
        return 0

    result = rsi_cli.run(ROOT, config)
    print(json.dumps({"run": result}, ensure_ascii=False, indent=2, default=str))
    return 3 if result.get("status") == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
