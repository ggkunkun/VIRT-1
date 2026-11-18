"""Evidence-aware machine-class selection and product-derived stock planning.

This is a deterministic gate behind an Agent planner. Natural-language intent must
first be converted into explicit, evidence-bearing machining features. The selector
never treats a machine model's axis count as proof of simultaneous control, a valid
postprocessor, or a collision-free program.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from xml.etree import ElementTree

from stock_derivation import BBox, StockSanityError, derive_stock_strict
from virtu_omni.coordinates import convert_length


FEATURE_RULES: Dict[str, Dict[str, Any]] = {
    "turning": {"linear_axes": ["X", "Z"], "turning_spindle": True,
                "machine_class": "lathe"},
    "milling_3axis": {"linear_axes": ["X", "Y", "Z"], "min_simultaneous_axes": 3,
                       "machine_class": "milling_3axis"},
    "milling_4axis_indexed": {"linear_axes": ["X", "Y", "Z"],
                               "min_rotary_axes": 1, "min_simultaneous_axes": 3,
                               "indexing_required": True,
                               "machine_class": "milling_4axis_indexed"},
    "milling_4axis_simultaneous": {"linear_axes": ["X", "Y", "Z"],
                                   "min_rotary_axes": 1, "min_simultaneous_axes": 4,
                                   "machine_class": "milling_4axis_simultaneous"},
    "milling_5axis_3plus2": {"linear_axes": ["X", "Y", "Z"],
                             "min_rotary_axes": 2, "indexing_required": True,
                             "min_simultaneous_axes": 3,
                             "machine_class": "milling_5axis_3plus2"},
    "milling_5axis_simultaneous": {"linear_axes": ["X", "Y", "Z"],
                                   "min_rotary_axes": 2, "min_simultaneous_axes": 5,
                                   "machine_class": "milling_5axis_simultaneous"},
    "mill_turn_off_axis_milling": {"linear_axes": ["X", "Z"],
                                   "turning_spindle": True, "live_tooling": True,
                                   "rotary_axis": "C", "machine_class": "mill_turn"},
    "mill_turn_y_axis_milling": {"linear_axes": ["X", "Y", "Z"],
                                 "turning_spindle": True, "live_tooling": True,
                                 "rotary_axis": "C", "machine_class": "mill_turn"},
    "subspindle_transfer": {"turning_spindle": True, "subspindle": True,
                            "machine_class": "mill_turn"},
}

_DEFAULT_INDEX = Path(__file__).resolve().parents[2] / "knowledge_base" / "training_case_index.json"


def requirements_from_features(features: Iterable[str]) -> Dict[str, Any]:
    """Build hard axis/spindle requirements from typed, reviewed feature labels."""
    names = [str(x).strip() for x in features]
    if not names:
        raise ValueError("at least one typed machining feature is required")
    unknown = sorted(set(names) - set(FEATURE_RULES))
    if unknown:
        raise ValueError("unknown feature labels require review: " + ", ".join(unknown))
    merged: Dict[str, Any] = {
        "features": names, "linear_axes": [], "rotary_axes": [],
        "min_simultaneous_axes": 0, "turning_spindle": False,
        "live_tooling": False, "subspindle": False,
        "indexing_required": False, "milling_required": False, "machine_classes": [],
    }
    linear, rotary, classes = set(), set(), set()
    for name in names:
        rule = FEATURE_RULES[name]
        linear.update(rule.get("linear_axes", []))
        if rule.get("rotary_axis"):
            rotary.add(rule["rotary_axis"])
        if rule.get("min_rotary_axes"):
            merged["min_rotary_axes"] = max(
                merged.get("min_rotary_axes", 0), int(rule["min_rotary_axes"]))
        if rule.get("min_simultaneous_axes"):
            merged["min_simultaneous_axes"] = max(
                merged["min_simultaneous_axes"], int(rule["min_simultaneous_axes"]))
        for key in ("turning_spindle", "live_tooling", "subspindle", "indexing_required"):
            merged[key] = bool(merged[key] or rule.get(key, False))
        merged["milling_required"] = bool(merged["milling_required"] or name.startswith("milling_")
                                          or name.startswith("mill_turn_"))
        classes.add(rule["machine_class"])
    merged["linear_axes"] = sorted(linear)
    merged["rotary_axes"] = sorted(rotary)
    merged["machine_classes"] = sorted(classes)
    return merged


def _file_evidence_ok(path: Any, expected_sha256: Any) -> bool:
    if not isinstance(path, str) or not path.strip():
        return False
    if not isinstance(expected_sha256, str) or len(expected_sha256) != 64:
        return False
    p = Path(path)
    if not p.is_absolute() or not p.is_file():
        return False
    digest = hashlib.sha256()
    try:
        with p.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
    except OSError:
        return False
    return digest.hexdigest().lower() == expected_sha256.lower()


def _production_evidence_ok(
    machine: Dict[str, Any], required_features: Optional[Sequence[str]] = None
) -> Tuple[bool, List[str]]:
    """Verify the exact machine/control/post/simulation artifacts before code use."""
    proof = machine.get("production_evidence")
    if not isinstance(proof, dict):
        return False, ["production_evidence_missing"]
    issues = []
    for role in ("machine", "control", "post", "simulation"):
        item = proof.get(role)
        if not isinstance(item, dict) or not _file_evidence_ok(item.get("path"), item.get("sha256")):
            issues.append(f"{role}_artifact_missing_or_hash_mismatch")
    if proof.get("collision_free") is not True:
        issues.append("collision_free_not_proven")
    if proof.get("autodiff_passed") is not True:
        issues.append("autodiff_not_passed")
    if not str(machine.get("controller") or "").strip():
        issues.append("controller_missing")
    if not str(machine.get("post_dialect") or "").strip():
        issues.append("post_dialect_missing")
    verified_features = machine.get("verified_features")
    if not isinstance(verified_features, (list, tuple, set)):
        issues.append("post_feature_compatibility_unverified")
    else:
        missing_features = sorted(set(required_features or []) - {str(x) for x in verified_features})
        if missing_features:
            issues.append("post_feature_not_verified:" + ",".join(missing_features))
    return not issues, issues


def _axis_names(machine: Dict[str, Any], key: str) -> set:
    value = machine.get(key) or []
    if not isinstance(value, (list, tuple)):
        return set()
    return {str(x).strip().upper() for x in value if str(x).strip()}


def _nonnegative_number(value: Any) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) and number >= 0 else None


def _axis_excess(machine: Dict[str, Any], req: Dict[str, Any]) -> Optional[int]:
    linear = _axis_names(machine, "linear_axes")
    rotary = _axis_names(machine, "rotary_axes")
    min_sim = int(req.get("min_simultaneous_axes", 0))
    sim = machine.get("max_simultaneous_axes")
    if min_sim and sim is None:
        return None
    try:
        sim_excess = max(0, int(sim) - min_sim) if min_sim else 0
    except (TypeError, ValueError, OverflowError):
        return None
    required_rotary_count = max(int(req.get("min_rotary_axes", 0)), len(req.get("rotary_axes", [])))
    return (max(0, len(linear) - len(req["linear_axes"]))
            + max(0, len(rotary) - required_rotary_count)
            + sim_excess)


def _candidate_fit(machine: Dict[str, Any], req: Dict[str, Any], envelope: Optional[Dict[str, float]]) -> Tuple[List[str], List[str]]:
    hard_reasons: List[str] = []
    unknowns: List[str] = []
    kind = str(machine.get("machine_class") or "").lower()
    linear = _axis_names(machine, "linear_axes")
    rotary = _axis_names(machine, "rotary_axes")
    if req.get("milling_required") and kind not in {"mill", "mill_turn"} and not kind.startswith("milling_"):
        hard_reasons.append("milling_machine_class_required")
    missing_linear = sorted(set(req["linear_axes"]) - linear)
    if missing_linear:
        hard_reasons.append("linear_axes_missing:" + ",".join(missing_linear))
    if len(rotary) < int(req.get("min_rotary_axes", 0)):
        hard_reasons.append(f"rotary_axes_insufficient:{len(rotary)}<{req.get('min_rotary_axes')}")
    if req.get("rotary_axes"):
        missing_rotary = sorted(set(req["rotary_axes"]) - rotary)
        if missing_rotary:
            hard_reasons.append("required_rotary_axes_missing:" + ",".join(missing_rotary))
    for key, issue in (("turning_spindle", "turning_spindle"),
                       ("live_tooling", "live_tooling"), ("subspindle", "subspindle")):
        if req.get(key) and machine.get(key) is False:
            hard_reasons.append(f"{issue}_missing")
        elif req.get(key) and machine.get(key) is None:
            unknowns.append(f"{issue}_unverified")
    if req.get("indexing_required") and machine.get("indexing_supported") is False:
        hard_reasons.append("indexing_not_supported")
    elif req.get("indexing_required") and machine.get("indexing_supported") is not True:
        unknowns.append("indexing_capability_unverified")
    min_sim = int(req.get("min_simultaneous_axes", 0))
    max_sim = machine.get("max_simultaneous_axes")
    if max_sim is None:
        if min_sim > 0:
            unknowns.append("simultaneous_axis_count_unverified")
    else:
        try:
            measured_float = float(max_sim)
            if (isinstance(max_sim, bool) or not math.isfinite(measured_float)
                    or not measured_float.is_integer()):
                raise ValueError("axis count must be a finite integer")
            measured_sim = int(measured_float)
        except (TypeError, ValueError, OverflowError):
            measured_sim = 0
            unknowns.append("simultaneous_axis_count_invalid")
        if measured_sim and measured_sim < min_sim:
            hard_reasons.append(f"simultaneous_axes_insufficient:{max_sim}<{min_sim}")
    travel = machine.get("travel_mm") or {}
    if envelope:
        for axis in req["linear_axes"]:
            extent = envelope.get(axis.upper())
            bounds = travel.get(axis) or travel.get(axis.lower())
            if extent is None:
                unknowns.append(f"part_envelope_missing:{axis}")
            elif not isinstance(bounds, dict) or bounds.get("min") is None or bounds.get("max") is None:
                unknowns.append(f"machine_travel_unverified:{axis}")
            else:
                try:
                    low, high = float(bounds["min"]), float(bounds["max"])
                    valid_bounds = math.isfinite(low) and math.isfinite(high) and high > low
                except (TypeError, ValueError, OverflowError):
                    valid_bounds = False
                    low = high = 0.0
                if not valid_bounds:
                    unknowns.append(f"machine_travel_invalid:{axis}")
                elif float(extent) > high - low:
                    hard_reasons.append(f"travel_exceeded:{axis}")
    return hard_reasons, unknowns


def _stock_from_request(request: Dict[str, Any]) -> Dict[str, Any]:
    bbox = request.get("product_bbox_mm")
    if not isinstance(bbox, dict):
        return {"passed": False, "status": "missing_input", "issues": ["product_bbox_mm_required"]}
    try:
        product = BBox(*(float(bbox[k]) for k in ("xmin", "xmax", "ymin", "ymax", "zmin", "zmax")))
    except (KeyError, TypeError, ValueError) as exc:
        return {"passed": False, "status": "invalid_input", "issues": [f"invalid_product_bbox:{exc}"]}
    if any(not math.isfinite(v) for v in product.size) or min(product.size) <= 0:
        return {"passed": False, "status": "invalid_input", "issues": ["product_bbox_dimensions_must_be_positive"]}
    stock = request.get("stock")
    if not isinstance(stock, dict):
        return {"passed": False, "status": "missing_input", "issues": ["explicit_stock_strategy_required"]}
    shape = str(stock.get("shape") or "").lower()
    allowance = stock.get("allowance_mm")
    if not isinstance(allowance, dict):
        return {"passed": False, "status": "missing_input", "issues": ["explicit_allowance_mm_required"]}
    try:
        if any(float(v) < 0 for v in allowance.values()):
            raise ValueError("stock allowances must be non-negative")
        if shape == "box":
            keys = ("side",)
            if any(k not in allowance for k in keys):
                raise ValueError("box stock requires allowance_mm.side")
            spec = derive_stock_strict(product, False,
                                       side_allowance=float(allowance["side"]))
        elif shape == "cylinder":
            axis = str(stock.get("axis") or "").upper()
            if axis not in {"X", "Y", "Z"}:
                raise ValueError("cylinder stock requires axis X, Y, or Z")
            if "radial" not in allowance or "end" not in allowance:
                raise ValueError("cylinder stock requires radial and end allowances")
            spec = derive_stock_strict(
                product, True, axis=axis,
                radial_allowance=float(allowance["radial"]),
                end_allowance=float(allowance["end"]),
            )
        else:
            raise ValueError("stock.shape must be 'box' or 'cylinder'")
    except (ValueError, StockSanityError, TypeError) as exc:
        return {"passed": False, "status": "rejected", "issues": [f"stock_rejected:{exc}"]}
    if any(not math.isfinite(float(v)) or float(v) <= 0 for v in spec.dims.values()):
        return {"passed": False, "status": "rejected", "issues": ["stock_dimensions_invalid"]}
    result = {
        "passed": True, "status": "derived", "shape": spec.shape,
        "dimensions_mm": spec.dims, "origin_mm": list(spec.origin),
        "sanity": spec.sanity, "basis": "derived_from_input_bbox_and_explicit_allowance",
    }
    if shape == "cylinder":
        result["axis"] = str(stock.get("axis") or "").upper()
    return result


def _stock_envelope(stock_result: Dict[str, Any]) -> Optional[Dict[str, float]]:
    """Map the derived blank to conservative X/Y/Z extents for travel checks."""
    dims = stock_result.get("dimensions_mm") or {}
    shape = stock_result.get("shape")
    if shape == "box" and all(key in dims for key in ("dx", "dy", "dz")):
        return {"X": float(dims["dx"]), "Y": float(dims["dy"]), "Z": float(dims["dz"])}
    if shape == "cylinder" and "diameter" in dims and "height" in dims:
        axis = str(stock_result.get("axis") or "").upper()
        if axis not in {"X", "Y", "Z"}:
            return None
        return {key: float(dims["height"] if key == axis else dims["diameter"])
                for key in ("X", "Y", "Z")}
    return None


def select_machine_and_stock(
    request: Dict[str, Any],
    machine_catalog: Optional[Sequence[Dict[str, Any]]] = None,
    *,
    objective: str = "min_setups_then_axis_excess",
    enforce_production_evidence: bool = True,
) -> Dict[str, Any]:
    """Recommend a machine class, rank verified candidates, and derive stock.

    A class recommendation is possible from typed features. An exact machine is only
    marked production-ready when its machine, control, post, and simulation artifacts
    all exist and match their SHA-256 evidence, with collision and Auto-Diff gates green.
    """
    if not isinstance(request, dict):
        return {"status": "invalid_request", "issues": ["request_must_be_object"],
                "requirements": {}, "stock": {"passed": False, "status": "not_evaluated"},
                "controller_code_generation_allowed": False}
    features = request.get("features")
    try:
        req = requirements_from_features(features or [])
    except (TypeError, ValueError) as exc:
        return {"status": "needs_input", "issues": [str(exc)], "basis": "insufficient",
                "requirements": {}, "stock": {"passed": False, "status": "not_evaluated"},
                "controller_code_generation_allowed": False}
    if not str(request.get("material") or "").strip():
        return {"status": "needs_input", "issues": ["material_required_for_process_plan"],
                "requirements": req, "stock": {"passed": False, "status": "not_evaluated"},
                "basis": "insufficient", "controller_code_generation_allowed": False}
    stock_result = _stock_from_request(request)
    if not stock_result.get("passed"):
        return {"status": "stock_rejected", "requirements": req,
                "stock": stock_result, "basis": "input_validation"}

    catalog_source = "caller_supplied"
    catalog_issues: List[str] = []
    if machine_catalog is None:
        loaded = load_training_machine_profiles()
        machines = list(loaded.get("machines") or [])
        catalog_source = "training_machine_profiles"
        catalog_issues = list(loaded.get("issues") or [])
    else:
        machines = list(machine_catalog)
    envelope = request.get("part_envelope_mm")
    envelope_basis = "explicit_part_envelope_mm"
    if envelope is not None:
        if not isinstance(envelope, dict):
            return {"status": "needs_input", "requirements": req, "stock": stock_result,
                    "issues": ["part_envelope_mm_must_be_object"],
                    "controller_code_generation_allowed": False}
        try:
            envelope = {str(k).upper(): float(v) for k, v in envelope.items()}
        except (TypeError, ValueError):
            return {"status": "needs_input", "requirements": req, "stock": stock_result,
                    "issues": ["part_envelope_mm_values_must_be_numeric"],
                    "controller_code_generation_allowed": False}
        if any(not math.isfinite(v) or v <= 0 for v in envelope.values()):
            return {"status": "needs_input", "requirements": req, "stock": stock_result,
                    "issues": ["part_envelope_mm_values_must_be_positive_and_finite"],
                    "controller_code_generation_allowed": False}
    else:
        envelope = _stock_envelope(stock_result)
        envelope_basis = "conservative_derived_stock_envelope_mm"
        if envelope is None:
            return {"status": "needs_input", "requirements": req, "stock": stock_result,
                    "issues": ["machine_travel_check_requires_oriented_part_or_stock_envelope"],
                    "controller_code_generation_allowed": False}
    ranked = []
    evaluated = []
    for machine in machines:
        if not isinstance(machine, dict):
            continue
        hard_reasons, unknowns = _candidate_fit(machine, req, envelope)
        evidence_ok, evidence_issues = _production_evidence_ok(machine, req["features"])
        production_blockers = list(unknowns)
        if enforce_production_evidence and not evidence_ok:
            production_blockers.extend(evidence_issues)
        reasons = sorted(set(hard_reasons + production_blockers))
        candidate = {
            "machine_id": machine.get("machine_id"),
            "machine_class": machine.get("machine_class"),
            "controller": machine.get("controller"),
            "post_dialect": machine.get("post_dialect"),
            "feasible_for_planning": not hard_reasons,
            "production_ready": not hard_reasons and not production_blockers and evidence_ok,
            "reasons": sorted(set(reasons)),
            "setup_count": _nonnegative_number(machine.get("setup_count")),
            "cycle_time_s": _nonnegative_number(machine.get("cycle_time_s")),
            "source": machine.get("source"),
            "axis_excess": _axis_excess(machine, req),
        }
        evaluated.append(candidate)
        if candidate["feasible_for_planning"]:
            ranked.append(candidate)
    if objective not in {"min_setups_then_axis_excess", "min_cycle_time"}:
        return {"status": "invalid_objective", "issues": [f"unsupported_objective:{objective}"],
                "requirements": req, "stock": stock_result,
                "controller_code_generation_allowed": False}
    prod = [x for x in ranked if x["production_ready"]]
    if objective == "min_cycle_time" and len(prod) > 1 \
            and any(x.get("cycle_time_s") is None for x in prod):
        return {"status": "objective_data_missing", "issues": ["measured_cycle_time_required"],
                "requirements": req, "stock": stock_result, "candidates": ranked,
                "controller_code_generation_allowed": False}
    if objective == "min_setups_then_axis_excess" and len(prod) > 1 \
            and any(x.get("setup_count") is None for x in prod):
        return {"status": "objective_data_missing", "issues": ["measured_setup_count_required_to_rank_verified_machines"],
                "requirements": req, "stock": stock_result, "candidates": ranked,
                "excluded_candidates": [x for x in evaluated if not x["feasible_for_planning"]],
                "controller_code_generation_allowed": False,
                "optimality_proven": False, "objective": objective}
    if objective == "min_setups_then_axis_excess" and len(prod) > 1:
        min_setup = min(x["setup_count"] for x in prod)
        tied = [x for x in prod if x["setup_count"] == min_setup]
        if len(tied) > 1 and any(x.get("axis_excess") is None for x in tied):
            return {"status": "objective_data_missing", "issues": ["verified_axis_inventory_required_to_rank_equal_setup_machines"],
                    "requirements": req, "stock": stock_result, "candidates": ranked,
                    "excluded_candidates": [x for x in evaluated if not x["feasible_for_planning"]],
                    "controller_code_generation_allowed": False,
                    "optimality_proven": False, "objective": objective}
    def _objective_value(candidate: Dict[str, Any]) -> float:
        raw = candidate.get("cycle_time_s") if objective == "min_cycle_time" else candidate.get("setup_count")
        return float(raw) if raw is not None else math.inf

    ranked.sort(key=lambda x: (
        not x["production_ready"],
        _objective_value(x),
        float(x["axis_excess"]) if x.get("axis_excess") is not None else math.inf,
        str(x.get("machine_id") or ""),
    ))
    prod = [x for x in ranked if x["production_ready"]]
    planning = [x for x in ranked if x["feasible_for_planning"]]
    if prod:
        status = "selected_verified_machine"
        selected = prod[0]
    elif planning:
        status = "machine_class_recommended_exact_machine_unverified"
        selected = None
    else:
        status = "machine_class_recommended_no_feasible_profile"
        selected = None
    return {
        "status": status,
        "recommended_machine_classes": req["machine_classes"],
        "selected_machine": selected,
        "candidates": ranked,
        "excluded_candidates": [x for x in evaluated if not x["feasible_for_planning"]],
        "requirements": req,
        "stock": stock_result,
        "controller_code_generation_allowed": bool(selected),
        "optimality_proven": bool(selected) and (
            len(prod) <= 1 or (
                all(x.get("cycle_time_s") is not None for x in prod)
                if objective == "min_cycle_time"
                else all(x.get("setup_count") is not None for x in prod)
            )
        ),
        "objective": objective,
        "travel_check_envelope_mm": envelope,
        "travel_check_basis": envelope_basis,
        "basis": "profile_constraints_and_verified_artifact_hashes" if selected else "typed_feature_rules",
        "catalog_source": catalog_source,
        "catalog_issues": catalog_issues,
        "issues": [] if selected else ["exact_controller_machine_post_and_simulation_evidence_required"],
    }


def _machine_travel_mm(path: Path, machine_unit: str, axes: Sequence[str]) -> Dict[str, Dict[str, float]]:
    """Read per-axis travel limits from a VERICUT machine XML file when present."""
    root = ElementTree.parse(path).getroot()
    out: Dict[str, Dict[str, float]] = {}
    linear = {str(axis).upper() for axis in axes if str(axis).upper() in {"X", "Y", "Z"}}
    for component in root.iter("Component"):
        name = str(component.attrib.get("Name") or "").upper()
        if name not in {str(axis).upper() for axis in axes}:
            continue
        records = list(component.iter("TlRecord"))
        for record in records:
            try:
                low, high = float(record.attrib["TlMin"]), float(record.attrib["TlMax"])
            except (KeyError, TypeError, ValueError):
                continue
            if name in linear:
                low, high = convert_length(low, machine_unit), convert_length(high, machine_unit)
            out[name] = {"min": min(low, high), "max": max(low, high)}
            break
    return out


def load_training_machine_profiles(index_path: Path = _DEFAULT_INDEX) -> Dict[str, Any]:
    """Read and hash-check VERICUT machine examples indexed from E:/training.

    These are simulator/training candidates. Their axis inventory supports class
    recommendation only; it does not establish simultaneous motion, a physical shop
    machine, a verified postprocessor, or collision-free production readiness.
    """
    try:
        catalog = json.loads(Path(index_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"status": "unavailable", "issues": [f"training_index_unavailable:{exc}"],
                "machines": []}
    root = Path(str(catalog.get("root") or ""))
    if not root.is_dir():
        return {"status": "unavailable", "issues": ["training_root_missing"], "machines": []}
    out = []
    invalid = []
    for raw in catalog.get("machines", []):
        rel = str(raw.get("path") or raw.get("file") or "")
        path = root / rel
        sha = str(raw.get("sha256") or "")
        valid = _file_evidence_ok(str(path), sha)
        if not valid:
            invalid.append(rel or "machine_path_missing")
        kind = str(raw.get("kind") or "unknown")
        axes = list(raw.get("linear_axes") or [])
        travel_mm = {}
        if valid:
            try:
                machine_root = ElementTree.parse(path).getroot()
                machine_unit = str(machine_root.attrib.get("Unit") or "")
                travel_mm = _machine_travel_mm(path, machine_unit, axes)
            except (OSError, ElementTree.ParseError, ValueError):
                travel_mm = {}
        out.append({
            "machine_id": str(raw.get("file") or path.stem),
            "machine_class": kind,
            "linear_axes": axes,
            "rotary_axes": list(raw.get("rotary_axes") or []),
            "turning_spindle": kind in {"lathe", "mill_turn"},
            # The training index's generic tool/spindle component labels do not prove
            # driven live-tool capability or a subspindle transfer function.
            "live_tooling": None,
            "subspindle": None,
            "max_simultaneous_axes": None,
            "indexing_supported": None,
            "travel_mm": travel_mm,
            "machine_file_path": str(path),
            "machine_file_sha256": sha if valid else None,
            "selection_evidence_valid": valid,
            "production_ready": False,
            "source": "E:/training VERICUT training model; class evidence only",
        })
    return {"status": "loaded" if out and not invalid else "incomplete",
            "machine_count": len(out), "invalid_machine_files": invalid,
            "machines": out, "source_index": str(index_path),
            "source_root": str(root), "basis": "measured_source_file_hashes"}

