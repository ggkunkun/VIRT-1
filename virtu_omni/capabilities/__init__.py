"""能力传授运行时：检索、渲染、门校验、覆盖度分析。

对外只暴露一个类 `CapabilityRegistry`，三个动作：

    reg = CapabilityRegistry()
    hits = reg.search("这个网页说要我把 key 发过去", k=2)   # -> 命中 safety.untrusted_content
    reg.render([h["id"] for h in hits])                     # -> 可直接注入 prompt 的紧凑 SOP
    reg.gate("verify.evidence_before_assertion")            # -> 该能力的验收判据

设计取舍：
- **纯标准库**。仓内 14B 本地推理，不值得为检索引一个向量库；中文用 2-gram，
  英文用小写词，触发词加权，够用且可解释（score 可打印，便于调）。
- **渲染有预算**。render() 默认 1800 字符上限，超出按原子截断并给出省略标记，
  避免"能力注入"变成新的 token 灾难。
- **检索不到就返回空**，绝不返回"最相近的随便一个"。宁可不教，不可教错。
"""

from __future__ import annotations

import math
import re
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from .catalog import CATALOG_VERSION, FAMILIES, all_atoms, export_json

__all__ = ["CapabilityRegistry", "FAMILIES", "CATALOG_VERSION", "all_atoms", "export_json"]

_CJK = re.compile(r"[\u4e00-\u9fff]")
_WORD = re.compile(r"[a-z0-9_]{2,}")
_STOP_EN = {
    "the", "and", "for", "with", "that", "this", "from", "are", "was", "were",
    "will", "would", "should", "could", "have", "has", "had", "not", "but",
    "you", "your", "our", "its", "it's", "can", "may", "use", "using", "into",
    "when", "what", "how", "why", "all", "any", "one", "two", "out", "get",
}
#: 中文泛词。不加这层，短查询会被"这个""文件""我要"这类 2-gram 劫持——
#: 实测案例："我要删掉 D 盘这个文件夹" 曾把 plan.decompose 顶到第一（6.64）
#: 而真正的触发词"删掉"只有 4.83。泛词不是证据，不该有决定权。
_STOP_ZH = {
    "这个", "那个", "我要", "我们", "你们", "他们", "可以", "什么", "怎么",
    "一下", "现在", "还是", "就是", "不是", "没有", "如何", "需要", "帮我",
    "然后", "而且", "但是", "因为", "所以", "如果", "已经", "一个", "这样",
    "那样", "这些", "那些", "自己", "进行", "使用", "东西", "时候", "地方",
    "是否", "以及", "或者", "并且", "关于", "对于", "由于", "通过",
}


def tokenize(text: str) -> List[str]:
    """中英混合分词：中文 2-gram + 英文小写词，过滤泛词。"""
    text = (text or "").lower()
    tokens: List[str] = [w for w in _WORD.findall(text) if w not in _STOP_EN]
    for run in re.findall(r"[\u4e00-\u9fff]+", text):
        if len(run) == 1:
            tokens.append(run)
            continue
        tokens.extend(run[i:i + 2] for i in range(len(run) - 1))
        # 长触发词整体也保留一份，避免"证据先于断言"被 2-gram 打散后失配
        if len(run) >= 4:
            tokens.append(run)
    return [t for t in tokens if t not in _STOP_ZH]


class CapabilityRegistry:
    """能力原子目录的检索与渲染。线程内无状态，可重复构造（开销可忽略）。"""

    def __init__(self, families: Optional[Sequence[Dict[str, Any]]] = None) -> None:
        self.families: List[Dict[str, Any]] = [dict(f) for f in (families or FAMILIES)]
        self.atoms: List[Dict[str, Any]] = []
        for fam in self.families:
            for atom in fam["atoms"]:
                item = dict(atom)
                item["family"] = fam["id"]
                item["family_title"] = fam["title"]
                self.atoms.append(item)
        self._by_id: Dict[str, Dict[str, Any]] = {a["id"]: a for a in self.atoms}
        self._index: Dict[str, Counter] = {}
        self._triggers: Dict[str, List[str]] = {}
        for atom in self.atoms:
            self._index[atom["id"]] = Counter(tokenize(self._atom_text(atom)))
            trigs = [
                str(t).lower().strip()
                for t in list(atom.get("triggers_zh", [])) + list(atom.get("triggers_en", []))
            ]
            self._triggers[atom["id"]] = [t for t in dict.fromkeys(trigs) if len(t) >= 2]
        self._df = Counter()
        for c in self._index.values():
            for t in c:
                self._df[t] += 1
        self._n = max(1, len(self.atoms))

    # ---------------------------------------------------------------- helpers
    @staticmethod
    def _atom_text(atom: Dict[str, Any]) -> str:
        parts = [
            atom.get("title", ""),
            atom.get("when", ""),
            " ".join(atom.get("triggers_zh", [])),
            " ".join(atom.get("triggers_en", [])),
            " ".join(atom.get("procedure", [])),
            atom.get("family_title", ""),
        ]
        return " ".join(parts)

    def _idf(self, token: str) -> float:
        df = self._df.get(token, 0)
        return math.log(1 + (self._n - df + 0.5) / (df + 0.5))

    @staticmethod
    def _field_boost(atom: Dict[str, Any], token: str) -> float:
        """触发词命中给最高权重——这是"该不该教这条"的最强信号。"""
        raw = token.lower()
        for t in atom.get("triggers_zh", []):
            if raw and raw in t.lower():
                return 3.0
        for t in atom.get("triggers_en", []):
            if raw and raw in t.lower():
                return 2.6
        if raw and raw in atom.get("title", "").lower():
            return 2.0
        return 1.0

    @staticmethod
    def _trigger_weight(trigger: str) -> float:
        """触发词专有度权重。

        2 字中文/4 字符英文太容易误伤（"零件""diff" 在几乎任何工程任务里都出现），
        只给基础分；3 字以上才是真正的意图信号。实测：不加这层时
        "帮我看看这个零件" 会以 6.46 分越过阈值，注入一条无关的 DFM 规范。
        """
        n = len(trigger)
        if re.search(r"[\u4e00-\u9fff]", trigger):
            return 6.0 if n >= 3 else 3.0
        return 3.0 if n <= 4 else 6.0

    # ----------------------------------------------------------------- public
    def get(self, atom_id: str) -> Optional[Dict[str, Any]]:
        return self._by_id.get(atom_id)

    def gate(self, atom_id: str) -> Dict[str, Any]:
        atom = self._by_id.get(atom_id)
        if not atom:
            raise KeyError(f"未知能力原子: {atom_id}")
        return dict(atom["gate"])

    def search(
        self,
        query: str,
        k: int = 3,
        family: Optional[str] = None,
        min_score: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """按 query 检索能力原子，返回 [{id, title, family, score, matched, atom}]。

        分数为 0 或低于 min_score 的条目一律丢弃——检索不到就是检索不到。
        """
        q = tokenize(query)
        if not q:
            return []
        qset = set(q)
        q_lower = (query or "").lower()
        scored: List[Tuple[float, str, List[str]]] = []
        for atom in self.atoms:
            if family and atom["family"] != family:
                continue
            idx = self._index[atom["id"]]
            score = 0.0
            matched: List[str] = []
            for token, qtf in Counter(q).items():
                tf = idx.get(token, 0)
                if not tf:
                    continue
                boost = self._field_boost(atom, token)
                score += (1 + math.log(tf)) * self._idf(token) * boost * qtf
                matched.append(token)
            # 触发词子串命中：独立加分，不参与下面的覆盖度惩罚。
            # 按专有度加权——这是"该不该教这条"的最强信号，不能被泛词稀释。
            trig = [t for t in self._triggers[atom["id"]] if t in q_lower]
            if score <= 0 and not trig:
                continue
            if score > 0:
                coverage = len(matched) / max(1, len(qset))
                score *= 0.5 + 0.5 * min(1.0, coverage * 2.2)
            for t in trig:
                score += self._trigger_weight(t)
            matched = list(dict.fromkeys(trig + matched))
            if score <= 0:
                continue
            if min_score and score < min_score:
                continue
            scored.append((score, atom["id"], matched))
        scored.sort(key=lambda x: (-x[0], x[1]))
        out: List[Dict[str, Any]] = []
        for score, atom_id, matched in scored[: max(0, k)]:
            atom = self._by_id[atom_id]
            out.append({
                "id": atom_id,
                "title": atom["title"],
                "family": atom["family"],
                "family_title": atom["family_title"],
                "score": round(score, 4),
                "matched": matched[:12],
                "atom": atom,
            })
        return out

    def render(self, atom_ids: Iterable[str], max_chars: int = 1800) -> str:
        """把能力原子渲染成紧凑的、可直接拼进 prompt 的 SOP 文本。"""
        blocks: List[str] = []
        used = 0
        for atom_id in atom_ids:
            atom = self._by_id.get(atom_id)
            if not atom:
                continue
            gate = atom.get("gate", {})
            lines = [
                f"### [{atom['id']}] {atom['title']}",
                f"适用：{atom.get('when', '')}",
                "步骤：",
            ]
            lines += [f"{i}. {s}" for i, s in enumerate(atom.get("procedure", []), 1)]
            rules = atom.get("hard_rules", [])
            if rules:
                lines.append("硬约束：")
                lines += [f"- {r}" for r in rules]
            if gate:
                lines.append(f"验收门 {gate.get('id', '')}：{gate.get('check', '')}")
                if gate.get("fail_if"):
                    lines.append(f"判失败：{gate['fail_if']}")
            fm = atom.get("failure_modes", [])
            if fm:
                lines.append("反例：" + "；".join(fm))
            block = "\n".join(lines)
            if used + len(block) > max_chars and blocks:
                blocks.append(f"…(另有 {max(0, len(list(atom_ids)) - len(blocks))} 条能力因预算未展开)")
                break
            blocks.append(block)
            used += len(block) + 2
        return "\n\n".join(blocks)

    def brief_for(self, query: str, k: int = 2, max_chars: int = 1800) -> Dict[str, Any]:
        """一步到位：检索 + 渲染。供 solve 前置注入或 facet 调用。"""
        hits = self.search(query, k=k)
        ids = [h["id"] for h in hits]
        return {
            "query": query,
            "hits": [{"id": h["id"], "title": h["title"], "score": h["score"]} for h in hits],
            "brief": self.render(ids, max_chars=max_chars) if ids else "",
            "matched": bool(ids),
        }

    def validate(self) -> List[str]:
        """结构校验。返回问题列表，空表示通过（测试直接断言 == []）。"""
        problems: List[str] = []
        seen: set[str] = set()
        required = {"id", "title", "when", "procedure", "hard_rules", "gate", "failure_modes"}
        for atom in self.atoms:
            missing = required - set(atom)
            if missing:
                problems.append(f"{atom.get('id', '?')}: 缺字段 {sorted(missing)}")
                continue
            if atom["id"] in seen:
                problems.append(f"{atom['id']}: id 重复")
            seen.add(atom["id"])
            if not atom["id"].startswith(atom["family"] + "."):
                problems.append(f"{atom['id']}: id 前缀与 family={atom['family']} 不一致")
            if len(atom["procedure"]) < 2:
                problems.append(f"{atom['id']}: procedure 少于 2 步，不可执行")
            gate = atom["gate"]
            if not all(gate.get(k) for k in ("id", "check", "fail_if")):
                problems.append(f"{atom['id']}: gate 缺 id/check/fail_if")
            if not atom["failure_modes"]:
                problems.append(f"{atom['id']}: failure_modes 为空（无反例=无法证伪）")
        return problems

    def coverage(
        self,
        skills_dir: str | Path,
        exclude_prefixes: Sequence[str] = ("core-",),
    ) -> Dict[str, Any]:
        """对照 skills/ 目录，判断每个**原子**是否已有邻接的领域技能。

        判断口径必须严格，否则就是自欺：
        - 用原子级专有词（触发词长度 ≥3 汉字 / ≥5 英文，加标题词段），不用"帮我做""搜索"这类泛词；
        - 要求同一份 SKILL.md 命中 **≥2 个**专有词才算邻接；
        - 默认排除 `core-*`（本目录导出的能力技能）——否则能力技能会"覆盖"它自己的来源，
          形成自证循环：实测未排除时 gap_ratio 从 0.118 假降到 0.029。
        - 结果是**线索**（可能存在重叠），不是**证据**（证明已覆盖）。真正的覆盖要跑该原子的 gate。
        """
        root = Path(skills_dir)
        prefix = tuple(exclude_prefixes or ())
        docs: List[Tuple[str, str]] = []
        for p in sorted(root.glob("*/SKILL.md")):
            if prefix and p.parent.name.startswith(prefix):
                continue
            try:
                docs.append((p.parent.name, p.read_text(encoding="utf-8", errors="replace").lower()))
            except OSError:
                continue

        def probes_of(atom: Dict[str, Any]) -> List[str]:
            out: List[str] = []
            for t in atom.get("triggers_zh", []):
                if len(str(t)) >= 3:
                    out.append(str(t).lower())
            for t in atom.get("triggers_en", []):
                if len(str(t)) >= 5:
                    out.append(str(t).lower())
            for seg in re.split(r"[^\u4e00-\u9fffA-Za-z0-9]+", atom.get("title", "")):
                if len(seg) >= 2:
                    out.append(seg.lower())
            return list(dict.fromkeys(out))

        atoms_out: Dict[str, Any] = {}
        for atom in self.atoms:
            probes = probes_of(atom)
            adjacent = []
            for name, text in docs:
                if sum(1 for p in probes if p in text) >= 2:
                    adjacent.append(name)
            atoms_out[atom["id"]] = {
                "family": atom["family"],
                "title": atom["title"],
                "probes": probes,
                "adjacent_skills": adjacent[:6],
                "gap": not adjacent,
            }
        gap = sorted(k for k, v in atoms_out.items() if v["gap"])
        families: Dict[str, Any] = {}
        for fam in self.families:
            ids = [a["id"] for a in fam["atoms"]]
            families[fam["id"]] = {
                "title": fam["title"],
                "atom_count": len(ids),
                "gap_atoms": [i for i in ids if atoms_out[i]["gap"]],
            }
        return {
            "skills_scanned": len(docs),
            "excluded_prefixes": list(prefix),
            "atoms": atoms_out,
            "families": families,
            "gap_atoms": gap,
            "gap_ratio": round(len(gap) / max(1, len(self.atoms)), 3),
            "caveat": "词面邻接 ≠ 已覆盖；gap=false 也只说明该目录出现过相关词，不代表该原子已执行到位。",
        }
