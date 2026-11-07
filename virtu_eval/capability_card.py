# -*- coding: utf-8 -*-
"""Executable capability cards for the six industrial software packages.

A card is not a description of the software, it is a claim about what can be
done and how the outcome is proved: preflight -> action -> postcondition probe.

The api surface is enumerated from the makepy-generated type library (an AST
read of a machine artifact), never transcribed from documentation, so a member
name or argument count that does not exist on this install fails statically.
"""

from __future__ import annotations

import argparse
import ast
import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KB_DIR = os.path.join(ROOT, "knowledge_base", "six_software")

VERIFIED = "verified-working"
NEGATIVE = "confirmed-negative"
UNPROBED = "documented-not-probed"
READINESS = (VERIFIED, NEGATIVE, UNPROBED)

SW_TLB_GUID = "{83A33D31-27C5-11CE-BFD4-00400513BB57}"
SW_TLB_MAJOR, SW_TLB_MINOR = 29, 0


class SurfaceUnavailable(RuntimeError):
    """Raised when no type-library enumeration exists; never treated as a pass."""


def _gen_py_candidates(tlb_guid):
    """Find makepy output for this typelib across every gen_py/python version dir.

    Generated files keep the GUID's dashes and append the version, e.g.
    83A33D31-27C5-11CE-BFD4-00400513BB57x0x29x0.py.
    """
    guid = tlb_guid.strip("{}").upper()
    roots = []
    for env in ("TEMP", "TMP"):
        tmp = os.environ.get(env) or ""
        if tmp:
            roots.append(os.path.join(tmp, "gen_py"))
    local = os.environ.get("LOCALAPPDATA", "")
    if local:
        roots.append(os.path.join(local, "Temp", "gen_py"))
    roots.append(os.path.join(os.path.expanduser("~"), "AppData", "Local", "Temp", "gen_py"))
    out = []
    for root in roots:
        if not os.path.isdir(root):
            continue
        for dirpath, _dirnames, filenames in os.walk(root):
            for name in filenames:
                if name.upper().startswith(guid) and name.endswith(".py"):
                    out.append(os.path.join(dirpath, name))
    return sorted(set(out))


def load_typelib_surface(tlb_guid=SW_TLB_GUID):
    """Return {interface: {"methods": {name: arity}, "properties": set(name)}}.

    Any generated copy of this GUID is the same typelib family; the report records
    which file was read so the grounding is auditable.
    """
    candidates = _gen_py_candidates(tlb_guid)
    if not candidates:
        raise SurfaceUnavailable(
            "no makepy-generated type library for %s under gen_py; "
            "a card cannot be verified against nothing" % tlb_guid
        )
    path = candidates[-1]
    with open(path, "r", encoding="utf-8", errors="ignore") as handle:
        tree = ast.parse(handle.read())

    surface = {}
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        methods, props = {}, set()
        for item in node.body:
            if isinstance(item, ast.FunctionDef):
                if item.name.startswith("_"):
                    continue
                methods[item.name] = len(item.args.args) - 1
            elif isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name) and target.id == "_prop_map_get_":
                        if isinstance(item.value, ast.Dict):
                            for key in item.value.keys:
                                if isinstance(key, ast.Constant) and isinstance(key.value, str):
                                    props.add(key.value)
        surface[node.name] = {"methods": methods, "properties": props}
    return {"source": path, "interfaces": surface}


def check_api_entry(entry, surface):
    """Verify one 'IFace::member' claim. Returns a finding dict; ok=False is fatal."""
    api = entry["api"]
    iface, _, member = api.partition("::")
    kinds = surface["interfaces"].get(iface)
    if kinds is None:
        return {"api": api, "ok": False, "reason": "unknown_interface"}
    want_kind = entry.get("kind", "method")
    if want_kind == "property":
        if member not in kinds["properties"]:
            return {"api": api, "ok": False, "reason": "not_a_property"}
        return {"api": api, "ok": True, "kind": "property"}
    if member not in kinds["methods"]:
        if member in kinds["properties"]:
            return {"api": api, "ok": False, "reason": "is_a_property_not_a_method"}
        return {"api": api, "ok": False, "reason": "unknown_method"}
    declared = entry.get("args")
    actual = kinds["methods"][member]
    if declared is not None and declared != actual:
        return {"api": api, "ok": False, "reason": "arity_mismatch",
                "declared_args": declared, "typelib_args": actual}
    return {"api": api, "ok": True, "kind": "method", "typelib_args": actual}


def load_cards(software):
    path = os.path.join(KB_DIR, software, "capability_cards.json")
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle), path


def validate_document(doc):
    """Schema gates that run before any typelib lookup."""
    problems = []
    for card in doc["cards"]:
        cid = card.get("id", "<no id>")
        for field in ("id", "name", "capability", "readiness", "preflight",
                      "action", "postconditions", "silent_failures", "evidence"):
            if field not in card:
                problems.append("%s missing field %s" % (cid, field))
        if card.get("readiness") not in READINESS:
            problems.append("%s readiness %r not in %s" % (cid, card.get("readiness"), list(READINESS)))
        if not card.get("action"):
            problems.append("%s has no action; a card with no actuator is prose" % cid)
        if not card.get("postconditions"):
            problems.append("%s has no postcondition probe; unverifiable claim" % cid)
    return problems


def verify_cards(doc, surface=None):
    surface = surface or load_typelib_surface()
    report = {"surface_source": surface["source"], "cards": [], "problems": validate_document(doc)}
    for card in doc["cards"]:
        findings = [check_api_entry(entry, surface) for entry in card.get("action", [])]
        bad = [f for f in findings if not f["ok"]]
        report["cards"].append({
            "id": card["id"],
            "readiness": card["readiness"],
            "api_ok": not bad,
            "api_findings": findings,
            "probes": {"preflight": [p["probe"] for p in card.get("preflight", [])],
                       "postcondition": [p["probe"] for p in card.get("postconditions", [])]},
            "silent_failure_count": len(card.get("silent_failures", [])),
        })
    return report


CONTRACT = "contract"
FORMULA = "formula"
RENDER_MODES = (CONTRACT, FORMULA)


def render_for_injection(doc, only_verified=True, mode=CONTRACT):
    """The only text allowed into model context about this software.

    Anything not verified-working is dropped rather than labelled: a menu name or
    API signature the model cannot act on becomes a hallucinated tool call.

    contract: what can be done, how it is proved, which traps are silent.
    formula:  the same, plus the analytic expectations, so the cost of checking
              is one multiplication instead of a judgement call.
    """
    lines = []
    lanes = doc.get("unit_discipline") or {}
    if lanes:
        for key in ("user_parameters", "com_arguments"):
            lane = lanes.get(key)
            if lane:
                lines.append("UNIT LAYER %s: %s | %s" % (key, lane.get("unit"), lane.get("rule")))
    for card in doc["cards"]:
        if only_verified and card["readiness"] != VERIFIED:
            continue
        lines.append("CAPABILITY %s [%s]" % (card["id"], card.get("capability", "")))
        if card.get("coordinate_axiom"):
            lines.append("  frame: %s" % card["coordinate_axiom"])
        lines.append("  act: %s" % ", ".join(a["api"] for a in card["action"]))
        lines.append("  prove: %s" % "; ".join(p["expression"] for p in card["postconditions"]))
        lines.append("  blind: %s" % " | ".join(card["silent_failures"]))
    if mode == FORMULA:
        lines.append("INVARIANTS (all must hold, mm):")
        lines.extend("  " + rule for rule in doc.get("engineering_invariants", []))
        lines.append("EXPECTED PER-FEATURE VOLUME DELTA (mm^3):")
        for tag, formula in (doc.get("analytic_expectations") or {}).items():
            if tag == "note":
                continue
            lines.append("  %s = %s" % (tag, formula))
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Verify and render capability cards.")
    parser.add_argument("--software", default="solidworks")
    parser.add_argument("--emit", default="", help="write the injection block to this path")
    parser.add_argument("--report", default="", help="write the verification report JSON")
    parser.add_argument("--mode", choices=RENDER_MODES, default=CONTRACT)
    args = parser.parse_args(argv)

    doc, path = load_cards(args.software)
    print("cards_file=%s" % path)
    try:
        report = verify_cards(doc)
    except SurfaceUnavailable as exc:
        print("SURFACE_UNAVAILABLE %s" % exc)
        return 2
    for card in report["cards"]:
        print("card=%s readiness=%s api_ok=%s" % (card["id"], card["readiness"], card["api_ok"]))
        for finding in card["api_findings"]:
            print("   %s %s%s" % ("OK  " if finding["ok"] else "FAIL", finding["api"],
                                  "" if finding["ok"] else " <- " + finding["reason"]))
    if report["problems"]:
        for problem in report["problems"]:
            print("SCHEMA_FAIL %s" % problem)
    total = len(report["cards"])
    good = sum(1 for c in report["cards"] if c["api_ok"])
    print("SUMMARY api_ok=%d/%d schema_problems=%d" % (good, total, len(report["problems"])))
    if args.report:
        with open(args.report, "w", encoding="utf-8") as handle:
            json.dump(report, handle, ensure_ascii=False, indent=2)
    block = render_for_injection(doc, mode=args.mode)
    print("INJECTION_MODE=%s chars=%d injected_cards=%d dropped_cards=%d"
          % (args.mode, len(block), block.count("CAPABILITY "), total - block.count("CAPABILITY ")))
    if args.emit:
        os.makedirs(os.path.dirname(os.path.abspath(args.emit)), exist_ok=True)
        with open(args.emit, "w", encoding="utf-8") as handle:
            handle.write(block + "\n")
    return 0 if good == total and not report["problems"] else 1


if __name__ == "__main__":
    sys.exit(main())
