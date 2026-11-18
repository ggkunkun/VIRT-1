"""把能力目录导出为 skills/<name>/SKILL.md（与仓内既有 52 个技能同格式）。

为什么要生成而不是手写：
    手写 11 份正文必然与 catalog.py 漂移，而"文档说一套、运行时跑另一套"正是
    本仓反复修过的病（AGENTS.md §4.1 legacy vs 真实运行时）。单一真源 + 生成，
    测试里再断言 skills 与 catalog 一致，漂移就变成红灯而不是隐患。

用法：
    PYTHONPATH=. python scripts/export_capability_skills.py [--check]

    --check  只比对不写入，发现漂移返回退出码 1（供 CI / 测试调用）
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from virtu_omni.capabilities import CATALOG_VERSION, CapabilityRegistry  # noqa: E402

SKILLS_DIR = ROOT / "skills"
NAME_PREFIX = "core-"


def _frontmatter(fam: dict) -> str:
    desc = fam["one_line"].replace('"', "'")
    return (
        "---\n"
        f"name: {NAME_PREFIX}{fam['id']}\n"
        f"description: \"{fam['title']}。{desc} 由能力传授目录生成，勿手改；改 virtu_omni/capabilities/catalog.py 后重跑导出。\"\n"
        "metadata:\n"
        f"  version: \"{CATALOG_VERSION}\"\n"
        "  owner: \"Virtu Capability Transfer\"\n"
        "  supported-consequence-levels: \"advisory\"\n"
        f"  generated-from: \"virtu_omni/capabilities/catalog.py#{fam['id']}\"\n"
        "---\n"
    )


def render_family(fam: dict, family_atoms: list) -> str:
    lines = [_frontmatter(fam), "", f"# {fam['title']}", "", f"> {fam['one_line']}", ""]
    for atom in family_atoms:
        lines += [
            f"## {atom['id']} — {atom['title']}",
            "",
            f"**何时适用**：{atom['when']}",
            "",
            "**步骤**",
            "",
        ]
        lines += [f"{i}. {s}" for i, s in enumerate(atom["procedure"], 1)]
        lines += ["", "**硬约束**", ""]
        lines += [f"- {r}" for r in atom["hard_rules"]]
        gate = atom["gate"]
        lines += [
            "",
            "**验收门**",
            "",
            f"- `{gate['id']}`：{gate['check']}",
            f"- 判失败：{gate['fail_if']}",
            "",
            "**反例（真实踩过的坑）**",
            "",
        ]
        lines += [f"- {f}" for f in atom["failure_modes"]]
        if atom.get("tools"):
            lines += ["", f"**相关工具**：{', '.join(atom['tools'])}"]
        if atom.get("references"):
            lines += ["", "**GitHub 参考**", ""]
            lines += [f"- [{ref['title']}]({ref['url']})" for ref in atom["references"]]
        lines.append("")
    lines += [
        "## 输出契约",
        "",
        "执行本族任一原子后，输出必须包含：所用原子 id、实际执行的检查、检查的原始输出（或摘要）、",
        "以及 `measured` / `asserted` / `insufficient` 三档证据等级。无证据不得写 `measured`。",
        "",
    ]
    return "\n".join(lines)


def build_all() -> dict[str, str]:
    reg = CapabilityRegistry()
    out: dict[str, str] = {}
    for fam in reg.families:
        atoms = [a for a in reg.atoms if a["family"] == fam["id"]]
        out[f"{NAME_PREFIX}{fam['id']}"] = render_family(fam, atoms)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="只比对，不写盘")
    args = ap.parse_args(argv)

    rendered = build_all()
    drifted: list[str] = []
    for name, text in rendered.items():
        path = SKILLS_DIR / name / "SKILL.md"
        if not path.exists():
            drifted.append(f"缺失: {name}")
            continue
        if path.read_text(encoding="utf-8", errors="replace") != text:
            drifted.append(f"漂移: {name}")

    if args.check:
        if drifted:
            print("能力技能与 catalog 不一致：")
            for d in drifted:
                print("  -", d)
            print("修复：PYTHONPATH=. python scripts/export_capability_skills.py")
            return 1
        print(f"OK：{len(rendered)} 个能力技能与 catalog 一致")
        return 0

    written = 0
    for name, text in rendered.items():
        d = SKILLS_DIR / name
        d.mkdir(parents=True, exist_ok=True)
        p = d / "SKILL.md"
        if not p.exists() or p.read_text(encoding="utf-8", errors="replace") != text:
            p.write_text(text, encoding="utf-8")
            written += 1
    print(f"写入 {written} 个 / 共 {len(rendered)} 个能力技能 -> {SKILLS_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
