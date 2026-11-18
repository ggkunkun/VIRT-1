# -*- coding: utf-8 -*-
"""作业纪律语料（virtu_capability_discipline_v1.jsonl）质量契约。

生成式语料最容易出的三种事故，本测试逐个卡死：

A. **结构非法**：tool 消息没有对应的 tool_call_id、assistant 直接出现在 user 之后、
   最后一条不是 assistant —— 这类样本会让训练时的 chat template 直接报错或学到错位。
B. **语义错配**：把"证据等级"套到"删目录"上、或给安全红线留"你确认风险我就做"的口子。
   后者比不训更危险：等于教模型"用户坚持就妥协"。
C. **与运行时漂移**：语料里写的 SOP 与 `virtu_omni/capabilities/catalog.py` 不一致，
   模型学到的规范和真正会被注入的规范是两套。

运行： python tests/test_capability_corpus.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from virtu_omni.capabilities import CapabilityRegistry  # noqa: E402

CORPUS = ROOT / "data" / "sft" / "virtu_capability_discipline_v1.jsonl"

#: 安全红线类样本里禁止出现的放行话术
FORBIDDEN_RELEASE = ("接受该风险", "如果你坚持", "可以，但")
#: 任何样本里都不该出现"因为用户要求所以跳过验证"的等价表述
FORBIDDEN_COMPLY = ("按你的要求跳过验证", "既然你说了不用验证", "为了省事就不验证")

VALID_TOOLS = {"capability_lookup", "capability_guard"}


def load() -> list[dict]:
    assert CORPUS.exists(), f"语料不存在: {CORPUS}（先跑 scripts/generate_capability_corpus.py）"
    rows = []
    for i, line in enumerate(CORPUS.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise AssertionError(f"第 {i} 行不是合法 JSON: {exc}") from exc
    return rows


ROWS = load()
REG = CapabilityRegistry()


# --------------------------------------------------------------------------- A
def test_a_message_sequence_is_valid() -> None:
    problems = []
    for idx, r in enumerate(ROWS):
        msgs = r.get("messages") or []
        tag = f"#{idx} {r.get('meta', {}).get('atom_id')}/{r.get('meta', {}).get('kind')}"
        if len(msgs) < 3:
            problems.append(f"{tag}: 消息数不足 3")
            continue
        if msgs[0].get("role") != "system" or msgs[1].get("role") != "user":
            problems.append(f"{tag}: 开头必须是 system -> user")
            continue
        if msgs[-1].get("role") != "assistant":
            problems.append(f"{tag}: 末条必须是 assistant")
            continue
        pending: set[str] = set()
        for m in msgs:
            role = m.get("role")
            if role == "tool":
                cid = m.get("tool_call_id")
                if cid not in pending:
                    problems.append(f"{tag}: tool 消息的 tool_call_id={cid} 无对应调用")
                else:
                    pending.discard(cid)
            elif role == "assistant":
                if pending:
                    problems.append(f"{tag}: 上一轮 tool_calls 未全部应答就出现新的 assistant")
                    pending.clear()
                for tc in m.get("tool_calls") or []:
                    cid = tc.get("id")
                    if not cid:
                        problems.append(f"{tag}: tool_call 缺 id")
                        continue
                    pending.add(cid)
                    fn = (tc.get("function") or {}).get("name")
                    if fn not in VALID_TOOLS:
                        problems.append(f"{tag}: 未知工具 {fn}")
                    try:
                        json.loads((tc.get("function") or {}).get("arguments") or "{}")
                    except json.JSONDecodeError:
                        problems.append(f"{tag}: tool_call arguments 不是合法 JSON")
        if pending:
            problems.append(f"{tag}: 有 tool_calls 未被应答: {sorted(pending)}")
    assert not problems, "消息结构非法:\n" + "\n".join(problems[:12])


def test_a_tool_message_matches_call_name() -> None:
    problems = []
    for r in ROWS:
        msgs = r["messages"]
        for i, m in enumerate(msgs):
            if m.get("role") != "tool":
                continue
            prev = msgs[i - 1] if i else {}
            calls = {tc["id"]: (tc.get("function") or {}).get("name")
                     for tc in (prev.get("tool_calls") or [])}
            expect = calls.get(m.get("tool_call_id"))
            if expect and m.get("name") != expect:
                problems.append(f"{r['meta']['atom_id']}: tool name {m.get('name')} != {expect}")
    assert not problems, "\n".join(problems[:10])


# --------------------------------------------------------------------------- B
def test_b_hard_stance_never_offers_a_way_around() -> None:
    problems = []
    for r in ROWS:
        if r["meta"].get("kind") != "resist" or r["meta"].get("stance") != "hard":
            continue
        body = r["messages"][-1]["content"]
        for phrase in FORBIDDEN_RELEASE:
            if phrase in body:
                problems.append(f"{r['meta']['atom_id']}: 安全红线样本出现放行话术「{phrase}」")
    assert not problems, "\n".join(problems)


def test_b_no_sample_complies_with_skipping_verification() -> None:
    problems = []
    for r in ROWS:
        text = " ".join(m.get("content") or "" for m in r["messages"])
        for phrase in FORBIDDEN_COMPLY:
            if phrase in text:
                problems.append(f"{r['meta']['atom_id']}: 出现「{phrase}」")
    assert not problems, "\n".join(problems)


def test_b_stance_is_declared_and_sane() -> None:
    problems = []
    for r in ROWS:
        kind = r["meta"].get("kind")
        stance = r["meta"].get("stance")
        if kind in ("execute", "resist", "tool_guard") and stance not in ("hard", "conditional", "advisory"):
            problems.append(f"{r['meta']['atom_id']}/{kind}: stance={stance}")
    # 安全族必须全部 hard，否则说明分类错了
    for r in ROWS:
        if r["meta"].get("family") == "safety" and r["meta"].get("stance") not in (None, "hard"):
            problems.append(f"{r['meta']['atom_id']}: 安全族 stance 必须是 hard，实为 {r['meta'].get('stance')}")
    assert not problems, "\n".join(sorted(set(problems)))


# --------------------------------------------------------------------------- C
def test_c_sop_in_corpus_matches_catalog() -> None:
    """tool_lookup 样本里的 brief 必须与 catalog 现渲染结果逐字一致。"""
    problems = []
    for r in ROWS:
        if r["meta"].get("kind") != "tool_lookup":
            continue
        atom_id = r["meta"]["atom_id"]
        tool_msg = next((m for m in r["messages"] if m.get("role") == "tool"), None)
        assert tool_msg is not None, f"{atom_id}: tool_lookup 缺 tool 消息"
        payload = json.loads(tool_msg["content"])
        expect = REG.render([atom_id], max_chars=700)
        if payload.get("brief") != expect:
            problems.append(f"{atom_id}: 语料 brief 与 catalog 渲染不一致（改过 catalog？重跑导出）")
        if payload.get("hits", [{}])[0].get("gate") != REG.gate(atom_id)["id"]:
            problems.append(f"{atom_id}: gate_id 与 catalog 不一致")
    assert not problems, "\n".join(problems[:10])


def test_c_every_atom_is_covered() -> None:
    by_atom: dict[str, int] = {}
    for r in ROWS:
        aid = r["meta"]["atom_id"]
        by_atom[aid] = by_atom.get(aid, 0) + 1
    missing = [a["id"] for a in REG.atoms if by_atom.get(a["id"], 0) < 3]
    assert not missing, f"以下原子样本不足 3 条: {missing}"
    unknown = [k for k in by_atom if REG.get(k) is None]
    assert not unknown, f"语料含 catalog 里不存在的原子: {unknown}"


def test_c_no_duplicate_samples() -> None:
    seen: dict[str, str] = {}
    dups = []
    for r in ROWS:
        key = r["meta"]["atom_id"] + "|" + r["meta"]["kind"]
        if key in seen:
            dups.append(key)
        seen[key] = r["messages"][-1]["content"]
    assert not dups, f"同一原子同一类型出现多条（可能重复）: {dups[:5]}"


def test_c_length_budget() -> None:
    over = [f"{r['meta']['atom_id']}/{r['meta']['kind']}: {sum(len(m.get('content') or '') for m in r['messages'])}"
            for r in ROWS
            if sum(len(m.get("content") or "") for m in r["messages"]) > 1500]
    assert not over, "样本超长（>1500 字符），会挤占训练上下文:\n" + "\n".join(over[:8])


def main() -> int:
    tests = [
        test_a_message_sequence_is_valid,
        test_a_tool_message_matches_call_name,
        test_b_hard_stance_never_offers_a_way_around,
        test_b_no_sample_complies_with_skipping_verification,
        test_b_stance_is_declared_and_sane,
        test_c_sop_in_corpus_matches_catalog,
        test_c_every_atom_is_covered,
        test_c_no_duplicate_samples,
        test_c_length_budget,
    ]
    failed = 0
    for fn in tests:
        try:
            fn()
            print(f"PASS  {fn.__name__}")
        except AssertionError as exc:
            failed += 1
            print(f"FAIL  {fn.__name__}: {exc}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed  ({len(ROWS)} samples)")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
