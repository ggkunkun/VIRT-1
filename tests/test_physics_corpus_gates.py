"""The corpus gates must actually fire -- prove each one on a tampered copy.

A launcher that always prints OK is worth nothing, so every gate here gets a mutation that should
make it fail, plus one control that should pass.
"""
import json
import os
import shutil

import pytest

import scripts.launch_physics_derivation_train as L

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope="module")
def staged(tmp_path_factory):
    """A private copy of the staged layout so tests can corrupt it without touching the real files."""
    if not os.path.exists(L.STAGED_CORPUS):
        pytest.skip("run scripts/launch_physics_derivation_train.py --stage first")
    base = tmp_path_factory.mktemp("corpus")
    train = base / "train"
    train.mkdir()
    shutil.copyfile(L.STAGED_CORPUS, train / "derivation_sft.jsonl")
    manifest = json.load(open(L.STAGED_MANIFEST, encoding="utf-8"))
    (base / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return base


def _point_at(monkeypatch, base):
    monkeypatch.setattr(L, "STAGED_DIR", str(base / "train"))
    monkeypatch.setattr(L, "STAGED_CORPUS", str(base / "train" / "derivation_sft.jsonl"))
    monkeypatch.setattr(L, "STAGED_MANIFEST", str(base / "manifest.json"))


def test_clean_staged_copy_passes(monkeypatch, staged):
    _point_at(monkeypatch, staged)
    problems, stats = L.preflight("v100")
    assert problems == [], problems
    assert stats["rows"] == 2400


def test_sha_gate_rejects_a_tampered_row(monkeypatch, staged):
    _point_at(monkeypatch, staged)
    path = L.STAGED_CORPUS
    before = L.sha256_file(path)
    rows = [json.loads(l) for l in open(path, encoding="utf-8")]
    # mutate a sidecar field so the bytes change while every content check still passes:
    # if the sha gate is the only thing that fires, it is provably the gate doing the work
    rows[5]["task"] = str(rows[5].get("task")) + "_tampered"
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    assert L.sha256_file(path) != before, "vacuous mutant: the file did not change"

    problems, _ = L.preflight("v100")
    assert any("sha256" in p for p in problems), problems


def test_max_len_2048_is_refused_as_truncation(monkeypatch, staged):
    """The trainer's own default max_len is 2048 and the corpus measures ~2091 est tokens."""
    _point_at(monkeypatch, staged)
    monkeypatch.setitem(L.MODES, "v100", dict(L.MODES["v100"], max_len=2048))
    problems, _ = L.preflight("v100")
    assert any("would truncate" in p for p in problems), problems
    assert not any("no longer score" in p for p in problems), problems


def test_ruler_regrade_catches_a_bad_derivation(monkeypatch, staged):
    """Rewrite every derivation to a wrong expression and refresh the manifest sha:
    only the re-grade against the ruler can catch it, which is the point of the gate."""
    _point_at(monkeypatch, staged)
    path = L.STAGED_CORPUS
    before = L.sha256_file(path)
    rows = [json.loads(l) for l in open(path, encoding="utf-8")]
    for r in rows:
        ans = json.loads(r["messages"][2]["content"])
        for field in ans["derivation"]:
            ans["derivation"][field] = "(1)+(1)"
        r["messages"][2]["content"] = json.dumps(ans, ensure_ascii=False)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    assert L.sha256_file(path) != before, "vacuous mutant: the file did not change"
    manifest_path = L.STAGED_MANIFEST
    manifest = json.load(open(manifest_path, encoding="utf-8"))
    manifest["sha256"] = L.sha256_file(path)
    json.dump(manifest, open(manifest_path, "w", encoding="utf-8"))

    problems, _ = L.preflight("v100", sample_rows=60)
    assert any("no longer score 100" in p for p in problems), problems
    assert not any("sha256" in p for p in problems), problems


def test_receipt_gate_rejects_truncated_or_wrong_corpus(monkeypatch, staged):
    _point_at(monkeypatch, staged)
    expected = {"rows": 2400, "est_p95": 2091}
    good = {"status": "COMPLETED", "data_rows": 2400, "data_file": str(L.STAGED_CORPUS),
            "train": {"max_len": 3072}}

    def run(rec, tmp_path, name="r.json"):
        p = tmp_path / name
        p.write_text(json.dumps(rec), encoding="utf-8")
        return L.verify_receipt(str(p), expected)[0]

    assert run(good, staged) == []
    short = dict(good, **{"train": {"max_len": 2048}})
    assert any("truncated" in p for p in run(short, staged, "r2.json"))
    smoke = dict(good, status="SMOKE_ONLY")
    assert any("SMOKE_ONLY" in p for p in run(smoke, staged, "r3.json"))
    wrong = dict(good, data_file="/x/dataset/virtu_capability_sft_v5.jsonl")
    assert any("not the staged" in p for p in run(wrong, staged, "r4.json"))
    fewrows = dict(good, data_rows=510)
    assert any("data_rows" in p for p in run(fewrows, staged, "r5.json"))


def test_command_targets_the_hash_gated_trainer_with_posix_paths():
    cmd = " ".join(L.build_command("v100", "out/x"))
    assert "train_virtu_v100.py" in cmd, "turnkey has a silent corpus fallback; do not target it"
    assert "--max-len 3072" in cmd
    assert "\\" not in cmd, cmd
    assert "data/physics_derivation_v1/train" in cmd


def test_no_staged_row_duplicates_an_eval_scenario():
    from virtu_eval.derivation import resolve  # noqa: F401  (import smoke)

    case_dir = os.path.join(ROOT, "data", "benchmark", "virtu_eval_phys_v1")
    eval_scens = []
    for fname in os.listdir(case_dir):
        if fname.endswith(".jsonl"):
            for line in open(os.path.join(case_dir, fname), encoding="utf-8"):
                c = json.loads(line)
                crit = [x for x in c["criteria"] if x.get("type") == "world_state_verified"][0]
                eval_scens.append((crit["scenario"]["task"], crit["scenario"]["inputs"]))
    dupes = 0
    for line in open(L.STAGED_CORPUS, encoding="utf-8"):
        r = json.loads(line)
        task, inputs = r["scenario"]["task"], r["scenario"]["inputs"]
        for e_task, e_inputs in eval_scens:
            if e_task != task or set(e_inputs) != set(inputs):
                continue
            if all(L_close(e_inputs[k], inputs[k]) for k in e_inputs):
                dupes += 1
    assert dupes == 0, f"{dupes} staged rows are near-copies of eval scenarios"


def L_close(a, b):
    if isinstance(a, list) or isinstance(b, list):
        return a == b
    try:
        return abs(float(a) - float(b)) <= 0.02 * max(abs(float(a)), 1e-9)
    except (TypeError, ValueError):
        return a == b
