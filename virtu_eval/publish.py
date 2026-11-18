"""virtu_eval/publish.py — 数值发布的唯一入口，外加只读审计模式（``--check``）。

AGENTS.md §8 测量宪法：任何进 ``benchmarks/**``、``checkpoints/PROVENANCE.json``、
README 数值段的数值，都必须带 ``run_id``（16 位 hex 内容指纹）+ 样本量 ``n`` +
证据路径 + ``basis``；没测写「未测」；禁止把源码字面量当 measured；闸门必须能被
坏样本证伪；``if not exists: continue``、空匹配集、解析失败一律判红。

本模块不另造口径：数值对象一律复用 :class:`virtu_eval.provenance.Metric`，发布表格
走 :func:`virtu_eval.provenance.render_table`。这里只叠加"发布层"比
``Metric.check()`` 更严的三条：

1. ``run_id`` 必须是 16 位 hex —— ``Metric`` 只要求非空，标签名字符串会被它放行；
2. 任何声明的 ``evidence`` 路径必须真实存在（不指向空气），相对路径按仓库根解析；
3. 空集合、JSON 解析失败、受控路径里的无归因数值，一律 raise / 记为不合规。

用法::

    # 发布（任何一条不合规即整体拒绝，不落半个文件）
    python -m virtu_eval.publish --metrics metrics.json --dest benchmarks/foo.json

    # 只读审计受控路径，有不合规则退出码非 0
    python -m virtu_eval.publish --check
    python -m virtu_eval.publish --check --paths benchmarks/some.json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from virtu_eval import provenance as P  # noqa: E402

# 16 位 hex 内容指纹（RunIdentity._fingerprint 的输出宽度）。标签名/任意字符串一律拒绝。
RUN_ID_RE = re.compile(r"^[0-9a-f]{16}$")

# 受控发布路径：数值进这些地方一律先过闸门。
CONTROLLED_DIRS = ("benchmarks",)
CONTROLLED_FILES = ("checkpoints/PROVENANCE.json",)

# basis 直接复用 provenance，避免另造一套口径。
BASIS = P.BASIS  # ("measured", "partial", "asserted", "inferred")


def is_controlled(dest) -> bool:
    """dest 是否落在受控发布路径（benchmarks/** / PROVENANCE.json / README.md）。"""
    p = Path(dest).resolve()
    for d in CONTROLLED_DIRS:
        base = (P.ROOT / d).resolve()
        if p == base or base in p.parents:
            return True
    for rel in CONTROLLED_FILES:
        if p == (P.ROOT / rel).resolve():
            return True
    return p.name.lower() == "readme.md"


def _resolve_evidence(evidence) -> Path:
    """evidence 相对路径按仓库根解析，绝对路径原样返回。"""
    p = Path(evidence)
    return p if p.is_absolute() else P.ROOT / p


def metric_from(obj):
    """把 dict 规整成 ``provenance.Metric``；已是 Metric 原样返回；其它类型拒绝。

    绝不静默补全缺失字段：没写 ``run_id``/``n``/``evidence`` 就是没写，交给
    ``validate_metric`` 判红，而不是塞一个能过闸的默认值。
    """
    if isinstance(obj, P.Metric):
        return obj
    if not isinstance(obj, dict):
        raise ValueError(f"数值条目必须是 Metric 或 dict，得到 {type(obj).__name__}")
    return P.Metric(
        name=obj.get("name") or obj.get("dimension") or obj.get("metric") or "?",
        value=obj.get("value", obj.get("score")),
        basis=obj.get("basis", "measured"),
        n=obj.get("n", 0),
        evidence=obj.get("evidence"),
        run_id=obj.get("run_id"),
        note=obj.get("note", ""),
        planned=obj.get("planned"),
    )


def validate_metric(m: P.Metric) -> None:
    """发布层硬约束。任何一条不满足即 raise ValueError（绝不返回 success=True）。

    ``m.check()`` 复用 provenance 的核心口径：value 非空；measured/partial 的
    evidence 存在、n、run_id 非空。这里再补 16 位 hex 与 evidence 真实性校验。
    """
    m.check()
    if m.basis not in BASIS:
        raise ValueError(f"{m.name}: basis 必须属于 {BASIS}，got {m.basis!r}")
    if not isinstance(m.run_id, str) or not RUN_ID_RE.fullmatch(m.run_id):
        raise ValueError(
            f"{m.name}: run_id 必须是 16 位 hex 内容指纹，拒绝标签名字符串（got {m.run_id!r}）")
    if m.evidence:
        if not _resolve_evidence(m.evidence).exists():
            raise ValueError(f"{m.name}: evidence 路径不存在：{m.evidence}")
    elif m.basis in ("measured", "partial"):
        raise ValueError(f"{m.name}: basis={m.basis} 必须给出 evidence 证据路径")
    if m.basis in ("measured", "partial"):
        if not isinstance(m.n, int) or isinstance(m.n, bool) or m.n <= 0:
            raise ValueError(f"{m.name}: n 必须为正整数（got {m.n!r}）")


def publish_metrics(metrics, dest):
    """把数值集合发布到 ``dest``；任何一条不合规即整体拒绝，不落半个文件。

    强制校验对**所有**目标一视同仁：即便 dest 不在受控路径，非法数值也进不了任何
    文件，因此「拒绝任何非法数值写入 benchmarks/** / PROVENANCE.json / README」是
    闸门的必然结果，而不是靠调用方自觉。写入用临时文件 + os.replace 原子替换。
    """
    if isinstance(metrics, (str, bytes)) or metrics is None:
        raise ValueError("metrics 必须是数值条目的可迭代集合")
    items = list(metrics)
    if not items:
        # 宪法 §8：空匹配集一律判红，不得当作通过。
        raise ValueError("空匹配集：没有任何数值条目，拒绝发布（不得判绿）")

    checked = []
    for item in items:
        m = metric_from(item)
        validate_metric(m)
        checked.append(m)

    # 复用 provenance 的唯一发布路径：as_row() 会对每个 Metric 再 check 一次。
    table = P.render_table(checked)
    payload = {
        "basis": "measured" if all(m.basis == "measured" for m in checked) else "partial",
        "n": sum(m.n for m in checked if isinstance(m.n, int)),
        "metrics": [{
            "name": m.name, "value": m.value, "basis": m.basis, "n": m.n,
            "evidence": str(m.evidence) if m.evidence else None,
            "run_id": m.run_id, "note": m.note,
        } for m in checked],
        "table": table,
    }

    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, dest)
    return payload


# ---------------------------------------------------------------------------
# 只读审计（--check）
# ---------------------------------------------------------------------------
def _contains_number(node) -> bool:
    if isinstance(node, bool):
        return False
    if isinstance(node, (int, float)):
        return True
    if isinstance(node, dict):
        return any(_contains_number(v) for v in node.values())
    if isinstance(node, list):
        return any(_contains_number(v) for v in node)
    return False


def _looks_like_publish_artifact(path: Path) -> bool:
    name = path.name.lower()
    return ("benchmarks" in path.parts or "provenance" in name
            or any(k in name for k in ("results", "report", "summary", "leaderboard", "eval")))


def _numeric_entries(doc, path: Path):
    """找出 JSON 里所有"数值声明"节点，返回 [(loc, obj), ...]。

    支持三种常见发布形态：顶层 list、``{"metrics": [...]}``、以及散落在任意深度的
    带 ``basis`` / ``run_id`` 字段的对象。找不到任何声明时返回空列表，由调用方判
    "数值未归因"而不是悄悄放行。
    """
    entries = []
    if isinstance(doc, list):
        return list(enumerate(doc))
    if isinstance(doc, dict) and isinstance(doc.get("metrics"), list):
        return list(enumerate(doc["metrics"]))

    def walk(node, loc):
        if isinstance(node, dict):
            if "basis" in node or "run_id" in node:
                entries.append((loc, node))
            for k, v in node.items():
                walk(v, f"{loc}.{k}")
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, f"{loc}[{i}]")
    walk(doc, str(path))
    return entries


def _audit_doc(doc, path: Path) -> list:
    out = []
    entries = _numeric_entries(doc, path)
    if not entries:
        if _looks_like_publish_artifact(path) and _contains_number(doc):
            out.append(f"数值未归因：{path}（无任何 run_id/basis 结构，禁止当实测发布）")
        return out
    for loc, node in entries:
        try:
            validate_metric(metric_from(node))
        except (ValueError, TypeError) as exc:
            out.append(f"{path} {loc}: {exc}")
    return out


def _audit_readme(readme: Path) -> list:
    """README 数值段：只抓"整体声称 100% 实测"这类无归因声明，逐行数值不刷屏。"""
    text = readme.read_text(encoding="utf-8", errors="replace")
    out = []
    for bad in ("100% 实测", "100% Measured", "100% measured", "Basis=Measured",
                "100% 真实能力实测"):
        if bad in text:
            out.append(f"README 含无归因声明「{bad}」：应标注未测/断言或补 16 位 hex run_id")
    return out


def default_controlled_paths() -> list:
    roots = []
    for d in CONTROLLED_DIRS:
        p = P.ROOT / d
        if p.exists():
            roots.append(str(p))
    for rel in CONTROLLED_FILES:
        p = P.ROOT / rel
        if p.exists():
            roots.append(str(p))
    readme = P.ROOT / "README.md"
    if readme.exists():
        roots.append(str(readme))
    return roots


def audit_paths(paths) -> list:
    """扫描受控路径，返回不合规清单（空清单 = 合规）。

    - 目录 → ``rglob("*.json")``；单个 .json / README.md 直接审；
    - 解析失败：记为违规，不吞异常、不跳过；
    - 空匹配集（一个可审文件都没有）：记为违规，不判绿。
    """
    files, readme = [], None
    for raw in paths:
        p = Path(raw)
        if not p.is_absolute():
            p = P.ROOT / p
        if p.is_dir():
            files.extend(sorted(q for q in p.rglob("*.json") if q.is_file()))
        elif p.suffix.lower() == ".json":
            files.append(p)
        elif p.name.lower() == "readme.md":
            readme = p
    if not files and readme is None:
        return ["空匹配集：未扫描到任何受控 JSON（不得判绿）"]

    violations = []
    for f in files:
        try:
            doc = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            # 解析失败一律判红：列进清单，绝不吞掉。
            violations.append(f"解析失败判红：{f}: {type(exc).__name__}: {exc}")
            continue
        violations.extend(_audit_doc(doc, f))
    if readme is not None:
        violations.extend(_audit_readme(readme))
    return violations


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="唯一数值发布入口 / 受控路径只读审计")
    ap.add_argument("--check", action="store_true", help="只读审计受控路径，输出不合规清单")
    ap.add_argument("--paths", nargs="*", default=None,
                    help="审计路径（文件/目录）；默认 = benchmarks/ + PROVENANCE.json + README.md")
    ap.add_argument("--metrics", default=None, help="待发布的 metrics JSON 文件")
    ap.add_argument("--dest", default=None, help="发布目标路径")
    a = ap.parse_args(argv)

    if a.check:
        violations = audit_paths(a.paths if a.paths is not None else default_controlled_paths())
        for v in violations:
            print(f"[不合规] {v}")
        if violations:
            print(f"[CHECK] 不合规 {len(violations)} 项，退出码 1")
            return 1
        print("[CHECK] 受控路径数值全部合规")
        return 0

    if not a.metrics or not a.dest:
        ap.error("发布模式需要 --metrics 与 --dest（或改用 --check 审计）")
    raw = Path(a.metrics)
    try:
        doc = json.loads(raw.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"[拒绝] metrics 文件解析失败：{raw}: {exc}")
        return 1
    items = doc["metrics"] if isinstance(doc, dict) and "metrics" in doc else doc
    try:
        publish_metrics(items, a.dest)
    except (ValueError, TypeError) as exc:
        # 非法数值绝不写入受控路径：明确失败，不静默降级。
        print(f"[拒绝] {exc}")
        return 1
    print(f"[OK] 已发布 {a.dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
