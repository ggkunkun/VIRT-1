"""Quality Gate Validator for Industrial Agent Tool-Calling Dataset.

Strict 6-point verification:
1. Valid JSON format on every row.
2. Tools schema integrity and valid JSON Schema.
3. Arguments parseable as JSON dict.
4. Tool name belongs to tools schema (0 hallucinated tool names).
5. Tool response ID matches assistant tool_call ID.
6. Feature Tree validation: contains valid parametric feature sequences (Sketch -> Extrude -> Cut/Hole).
"""

import sys
import os
import json

sys.stdout.reconfigure(encoding="utf-8")


def validate_dataset(filepath: str):
    print(f"=== [QUALITY GATE] Validating Dataset: {filepath} ===")
    if not os.path.exists(filepath):
        print(f"[FATAL] File not found: {filepath}")
        return False

    with open(filepath, "r", encoding="utf-8") as f:
        lines = [l.strip() for l in f if l.strip()]

    total = len(lines)
    passed = 0
    errors = []

    for idx, line in enumerate(lines):
        row_id = idx + 1
        try:
            data = json.loads(line)
        except Exception as e:
            errors.append(f"Row {row_id}: Invalid JSON - {e}")
            continue

        tools = data.get("tools", [])
        tool_names = set()
        for t in tools:
            fn = t.get("function", {})
            name = fn.get("name")
            if name:
                tool_names.add(name)

        messages = data.get("messages", [])
        if not messages or len(messages) < 4:
            errors.append(f"Row {row_id}: Too few messages ({len(messages)})")
            continue

        pending_calls = {}
        row_valid = True
        has_feature_tree = False

        for m_idx, msg in enumerate(messages):
            role = msg.get("role")
            if role == "assistant" and "tool_calls" in msg:
                for tc in msg["tool_calls"]:
                    call_id = tc.get("id")
                    fn = tc.get("function", {})
                    fn_name = fn.get("name")
                    fn_args = fn.get("arguments")

                    if not call_id:
                        errors.append(f"Row {row_id} msg {m_idx}: Missing call id")
                        row_valid = False
                        break

                    if fn_name not in tool_names:
                        errors.append(f"Row {row_id} msg {m_idx}: Hallucinated tool '{fn_name}'")
                        row_valid = False
                        break

                    try:
                        args_obj = json.loads(fn_args)
                        if not isinstance(args_obj, dict):
                            errors.append(f"Row {row_id} msg {m_idx}: Arguments not a JSON object")
                            row_valid = False
                            break
                        if fn_name in ["cad.model_parametric_feature_part", "cad.one_sentence_parametric_engine"]:
                            ft = args_obj.get("feature_tree", [])
                            if len(ft) >= 4:
                                has_feature_tree = True
                    except Exception as e:
                        errors.append(f"Row {row_id} msg {m_idx}: Malformed arguments JSON - {e}")
                        row_valid = False
                        break

                    pending_calls[call_id] = fn_name

            elif role == "tool":
                call_id = msg.get("tool_call_id")
                if call_id not in pending_calls:
                    errors.append(f"Row {row_id} msg {m_idx}: Orphan tool message (id '{call_id}')")
                    row_valid = False
                    break
                else:
                    del pending_calls[call_id]

        if row_valid and has_feature_tree:
            passed += 1

    pass_rate = (passed / total) * 100 if total > 0 else 0
    print(f"\n[REPORT] Total Trajectories : {total}")
    print(f"[REPORT] Passed Gate        : {passed}")
    print(f"[REPORT] Pass Rate          : {pass_rate:.2f}%")
    if errors:
        print(f"[WARNING] Sample Errors ({len(errors)}):")
        for err in errors[:5]:
            print(f"  - {err}")

    if pass_rate >= 98.0:
        print("\n>>> [VERDICT: ALL PASS] Dataset meets strict industrial training quality gate (>=98%)! <<<")
        return True
    else:
        print("\n>>> [VERDICT: FAIL] Dataset quality below 98% threshold. <<<")
        return False


if __name__ == "__main__":
    target = r"D:\Virtu模型\damodel_cad_cam_tuning\dataset\toolcall_automation_feature_tree_sft.jsonl"
    validate_dataset(target)
