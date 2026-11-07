#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pc-safe-optimizer / 阶段 C 候选清单枚举器（纯只读）

Invariants:
  * 只遍历 safe_cleanup.py allow_prefixes() 白名单目录中的具体文件。
  * 不删除、不移动、不重命名、不修改任何被扫描对象；唯一写入是 --out-dir 下的清单 JSON + MD。
  * 不做任何注册表写入、服务变更、进程终止、网络配置变更。
  * 生成的清单 confirmed_by_user=false / approved=false —— 仅为「待批准」，不可直接执行。

判定标准（默认，可由 --days / --min-size / --top 调整）：
  具体文件 + 最后修改超过 30 天 + 单文件 >= 1 MiB + 非重解析点 + 可被独占打开（不在使用中）。
"""
from __future__ import annotations

import argparse
import ctypes
import datetime as dt
import json
import os
import stat
import sys
from ctypes import wintypes
from pathlib import Path

FILE_ATTRIBUTE_REPARSE_POINT = 0x0400
GENERIC_READ = 0x80000000
OPEN_EXISTING = 3
FILE_ATTRIBUTE_NORMAL = 0x80
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

CAUTION_KEYWORDS = (
    "gguf", "model", "checkpoint", "safetensors", ".pt", ".bin", ".onnx",
    "ollama", "virtu", "installer", "setup", ".msi", ".zip", ".7z",
    "backup", ".bak", "dump", ".dmp", "log", "dataset", "corpus",
)

_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_kernel32.CreateFileW.argtypes = [
    wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
    wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
]
_kernel32.CreateFileW.restype = wintypes.HANDLE
_kernel32.CloseHandle.argtypes = [wintypes.HANDLE]


def norm(p: str) -> str:
    return os.path.normcase(os.path.realpath(os.path.normpath(os.path.abspath(p))))


def allow_roots() -> list[str]:
    la = os.environ.get("LOCALAPPDATA", "")
    wd = os.environ.get("WINDIR", r"C:\Windows")
    raw = [
        os.environ.get("TEMP", ""),
        os.path.join(la, "Temp"),
        os.path.join(wd, "Temp"),
        os.path.join(la, "Microsoft", "Windows", "INetCache"),
        os.path.join(la, "Google", "Chrome", "User Data", "Default", "Cache"),
        os.path.join(la, "Microsoft", "Edge", "User Data", "Default", "Cache"),
        os.path.join(la, "CrashDumps"),
        os.path.join(la, "Microsoft", "Windows", "WER"),
        os.path.join(la, "Microsoft", "Windows", "Explorer"),
    ]
    out: list[str] = []
    for r in raw:
        if not r:
            continue
        n = norm(r)
        if n not in out:
            out.append(n)
    # 排除需要额外确认的 Windows 更新缓存，本清单不纳入
    return out


def in_use(path: str) -> bool:
    """独占打开检测：任何打不开的情况一律视为「不可安全处理」并排除。只读探测。"""
    h = _kernel32.CreateFileW(path, GENERIC_READ, 0, None,
                              OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, None)
    if h is None or h == INVALID_HANDLE_VALUE:
        return True
    _kernel32.CloseHandle(h)
    return False


def human(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{int(n)} B"
        n /= 1024
    return f"{n:.1f} TB"


def iso(ts: float) -> str:
    return dt.datetime.fromtimestamp(ts).astimezone().isoformat(timespec="seconds")


def caution_of(path: str) -> str:
    low = path.lower()
    hits = [k for k in CAUTION_KEYWORDS if k in low]
    if not hits:
        return ""
    return "名称含 " + "/".join(hits[:3]) + "，可能是模型权重/安装包/备份/日志，需人工重点复核"


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    ap = argparse.ArgumentParser(description="阶段 C：只读枚举待批准清理候选")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--min-size", type=int, default=1024 * 1024)
    ap.add_argument("--top", type=int, default=30)
    args = ap.parse_args()

    out_dir = Path(args.out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    cutoff = (dt.datetime.now().astimezone() - dt.timedelta(days=args.days)).timestamp()

    roots = allow_roots()
    stats = {
        "scanned_files": 0, "skipped_recent": 0, "skipped_small": 0,
        "skipped_reparse": 0, "skipped_in_use": 0, "unreadable": 0,
    }
    candidates: list[dict] = []

    for root in roots:
        if not os.path.isdir(root):
            continue
        for dirpath, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
            dirnames[:] = [d for d in dirnames
                           if not (os.path.islink(os.path.join(dirpath, d)))]
            for name in filenames:
                full = os.path.join(dirpath, name)
                try:
                    st = os.lstat(full)
                except OSError:
                    stats["unreadable"] += 1
                    continue
                stats["scanned_files"] += 1
                if getattr(st, "st_file_attributes", 0) & FILE_ATTRIBUTE_REPARSE_POINT:
                    stats["skipped_reparse"] += 1
                    continue
                if not stat.S_ISREG(st.st_mode):
                    continue
                if st.st_mtime >= cutoff:
                    stats["skipped_recent"] += 1
                    continue
                if st.st_size < args.min_size:
                    stats["skipped_small"] += 1
                    continue
                if in_use(full):
                    stats["skipped_in_use"] += 1
                    continue
                rel = os.path.relpath(full, root)
                group = rel.split(os.sep)[0] if os.sep in rel else "(根目录)"
                candidates.append({
                    "path": os.path.abspath(full),
                    "action": "recycle",
                    "approved": False,
                    "reason": f"白名单缓存/临时文件；最后修改超过 {args.days} 天；单文件 >= {human(args.min_size)}；未被独占占用",
                    "size_bytes": st.st_size,
                    "mtime": iso(st.st_mtime),
                    "atime": iso(st.st_atime),
                    "group": group,
                    "root": root,
                    "in_use": False,
                    "caution": caution_of(full),
                    "risk": "少数程序把临时文件当会话状态；移除后该程序可能需重启重建缓存。已排除正被占用/近期修改/重解析点文件。",
                })

    candidates.sort(key=lambda x: x["size_bytes"], reverse=True)
    all_count = len(candidates)
    all_bytes = sum(c["size_bytes"] for c in candidates)
    selected = candidates[:args.top]
    sel_bytes = sum(c["size_bytes"] for c in selected)

    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    json_name = f"pc-cleanup-candidates-{stamp}.json"
    md_name = f"pc-cleanup-candidates-{stamp}.md"

    plan = {
        "generated_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "read_only": True,
        "stage": "C — 待用户逐项书面确认（本清单不可直接执行）",
        "criteria": {
            "max_age_days_unmodified": args.days,
            "min_size_bytes": args.min_size,
            "exclude_in_use": True,
            "exclude_reparse_points": True,
            "scope": "仅 safe_cleanup.py allow_prefixes() 白名单内的具体文件；不含 Windows 更新缓存/回收站/用户私人目录",
            "top_n": args.top,
        },
        "confirmed_by_user": False,
        "items": selected,
        "summary": {
            "qualifying_total": all_count,
            "qualifying_total_bytes": all_bytes,
            "selected": len(selected),
            "selected_bytes": sel_bytes,
            "selected_batches_of_10": (len(selected) + 9) // 10,
            **stats,
        },
        "execution_note": "仅在用户逐项确认并把 confirmed_by_user 与每项 approved 置为 true 后，才可进入 D/E/F；执行必须先 dry-run。",
    }
    (out_dir / json_name).write_text(
        json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# 阶段 C：待批准清理清单（尚未执行）",
        "",
        f"- 生成时间：{plan['generated_at']}",
        "- 扫描模式：**READ-ONLY** —— 未删除、未移动、未重命名任何文件；未改注册表/服务/进程/网络配置",
        "- 清单状态：`confirmed_by_user = false`，每项 `approved = false` → **不可执行**",
        f"- 判定标准：白名单内具体文件、最后修改 > {args.days} 天、单文件 >= {human(args.min_size)}、非重解析点、未被独占占用",
        "- 范围不含：Windows 更新下载缓存（需额外确认）、回收站、桌面/下载/文档等私人目录",
        "",
        "> **⚠️ 此操作非常危险，可能导致不可逆的数据丢失！**",
        "> 下表每一项都必须经你逐项书面确认，才会进入备份 → dry-run → 回收站流程。本轮**未对任何文件采取行动**。",
        "",
        f"## 逐项清单（{len(selected)} 项，合计 {human(sel_bytes)}）",
        "",
        f"全部合格候选共 {all_count} 项 / {human(all_bytes)}；本清单按体积降序取前 {args.top} 项，分 {(len(selected) + 9) // 10} 批（每批 ≤10）执行。",
        "",
        "| # | 批次 | 完整绝对路径 | 大小 | 最后修改 | 分组 | 重点复核 |",
        "| ---: | ---: | :--- | ---: | :--- | :--- | :--- |",
    ]
    for i, c in enumerate(selected, 1):
        flag = "⚠ " + c["caution"] if c["caution"] else "—"
        lines.append(
            f"| {i} | {(i - 1) // 10 + 1} | `{c['path']}` | {human(c['size_bytes'])} | "
            f"{c['mtime']} | {c['group']} | {flag} |"
        )
    lines += [
        "",
        "## 统一风险说明",
        "",
        "- 每项共同风险：少数程序把临时文件当会话状态；移除后可能需重启该程序重建缓存。",
        "- 已排除：正被独占占用的文件、近 30 天修改过的文件、符号链接/重解析点、不可读项。",
        "- 执行时仍会先做 SHA-256 备份校验，再经回收站（`FOF_ALLOWUNDO`）移入，可还原；不会永久删除。",
        "",
        "## 排除统计（可核验）",
        "",
        "| 项 | 数量 |",
        "| :--- | ---: |",
        f"| 扫描到的文件 | {stats['scanned_files']} |",
        f"| 近 {args.days} 天内修改（跳过） | {stats['skipped_recent']} |",
        f"| 小于 {human(args.min_size)}（跳过） | {stats['skipped_small']} |",
        f"| 重解析点（跳过） | {stats['skipped_reparse']} |",
        f"| 占用/无法独占打开（跳过） | {stats['skipped_in_use']} |",
        f"| 不可读（跳过） | {stats['unreadable']} |",
        f"| 合格候选合计 | {all_count} / {human(all_bytes)} |",
        "",
        "## 确认方式",
        "",
        "1. 逐项核对上表完整路径；告诉我保留/剔除哪些编号（或回复「确认全部 N 项」）。",
        "2. 我把清单的 `confirmed_by_user` 与对应项 `approved` 置为 true，展示给你复核。",
        "3. 阶段 D：独立备份目录 + SHA-256 校验；阶段 E：先 dry-run 展示校验结果，再次确认后 `--execute`（回收站，每批 ≤10，JSONL 审计）；阶段 F：复核与回滚说明。",
        "4. 任何阶段失败即停止，保留备份与日志。",
        "",
        "---",
        f"原始清单：`{json_name}`；执行日志仅在确认后产生。",
    ]
    (out_dir / md_name).write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"[READ-ONLY] 候选枚举完成，未改动任何被扫描对象")
    print(f"  扫描文件 {stats['scanned_files']}，合格候选 {all_count} / {human(all_bytes)}")
    print(f"  入选 {len(selected)} 项 / {human(sel_bytes)}，分 {(len(selected) + 9) // 10} 批")
    print(f"  JSON : {out_dir / json_name}")
    print(f"  清单 : {out_dir / md_name}")
    print(f"  状态 : confirmed_by_user=false / approved=false —— 等待用户逐项确认")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
