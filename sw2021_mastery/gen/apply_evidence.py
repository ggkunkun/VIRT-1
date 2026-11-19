# -*- coding: utf-8 -*-
"""把实测证据回写到训练集 review 字段，并生成证据台账。

用法：
  python gen/apply_evidence.py --ops SKT-02,SKT-06,FEAT-01,FEAT-02 \
         --result machine_observed --evidence out/evidence/pilot_result.json
"""
import argparse
import hashlib
import json
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, "out")


def load_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def write_jsonl(path, rows):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ops", required=True)
    ap.add_argument("--result", default="machine_observed")
    ap.add_argument("--evidence", default="out/evidence/pilot_result.json")
    ap.add_argument("--note", default="COM 实测生成几何并回读体积；界面截图与人工签署仍待完成")
    args = ap.parse_args()
    ops = {x.strip() for x in args.ops.split(",") if x.strip()}

    ev_path = os.path.join(BASE, args.evidence)
    with open(ev_path, encoding="utf-8") as f:
        ev = json.load(f)
    artifacts = [str(ev.get("part") or ""), str(ev.get("step") or "")] + [str(p) for p in ev.get("previews", [])]
    artifacts = [a for a in artifacts if a]

    ds_path = os.path.join(OUT, "train_dataset.jsonl")
    rows = load_jsonl(ds_path)
    hits, ledger = 0, []
    for r in rows:
        if r.get("op_code") in ops and r.get("task_type") == "operation":
            r["review"] = {
                "owner": "agent:sw_com",
                "verified_at": ev.get("finished_at") or "2026-11-18",
                "result": args.result,
                "artifacts": artifacts,
                "note": args.note,
                "volume_mm3": ev.get("volume_mm3"),
                "volume_deviation": ev.get("volume_deviation"),
                "revision": ev.get("revision"),
            }
            hits += 1
            ledger.append({"sample_id": r["id"], "op_code": r["op_code"], "result": args.result,
                           "artifacts": artifacts, "revision": ev.get("revision")})
    if not hits:
        raise SystemExit(f"没有任何样本命中 op_code={ops}")

    write_jsonl(ds_path, rows)
    with open(os.path.join(OUT, "evidence", "evidence_ledger.jsonl"), "a", encoding="utf-8", newline="\n") as f:
        for item in ledger:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    mp = os.path.join(OUT, "manifest.json")
    if os.path.exists(mp):
        with open(mp, encoding="utf-8") as f:
            man = json.load(f)
        man.setdefault("files", {})["train_dataset.jsonl"] = {
            "bytes": os.path.getsize(ds_path), "sha256": sha256(ds_path)}
        man["review"] = man.get("review", {})
        man["review"]["machine_observed_samples"] = man["review"].get("machine_observed_samples", 0) + hits
        with open(mp, "w", encoding="utf-8", newline="\n") as f:
            json.dump(man, f, ensure_ascii=False, indent=2)

    print(json.dumps({"op_codes": sorted(ops), "updated_samples": hits, "artifacts": len(artifacts),
                      "dataset_bytes": os.path.getsize(ds_path)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
