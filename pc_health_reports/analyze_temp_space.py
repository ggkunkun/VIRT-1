#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
只读空间分布分析：回答「白名单缓存/临时目录的体积到底堆在哪」。

Invariants: 只 os.walk + os.lstat；唯一写入是 --out-dir 下的 MD + JSON。
不删除/移动/重命名任何文件，不改注册表/服务/进程/网络配置，不独占打开任何句柄。
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import stat
import sys
from pathlib import Path

FILE_ATTRIBUTE_REPARSE_POINT = 0x0400


def human(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{int(n)} B"
        n /= 1024
    return f"{n:.1f} TB"


def iso(ts: float) -> str:
    try:
        return dt.datetime.fromtimestamp(ts).astimezone().isoformat(timespec="seconds")
    except (OSError, OverflowError, ValueError):
        return "时间戳异常"


def age_bucket(days: float) -> str:
    if days <= 7:
        return "0-7 天"
    if days <= 30:
        return "8-30 天"
    if days <= 90:
        return "31-90 天"
    if days <= 365:
        return "91-365 天"
    return "> 365 天"


def roots() -> list[str]:
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
    out = []
    for r in raw:
        if not r:
            continue
        n = os.path.normcase(os.path.realpath(os.path.abspath(r)))
        if n not in out:
            out.append(n)
    return out


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    ap = argparse.ArgumentParser(description="只读分析缓存/临时目录空间分布")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--top", type=int, default=20)
    args = ap.parse_args()

    out_dir = Path(args.out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    now = dt.datetime.now().astimezone().timestamp()

    by_group: dict[str, dict] = {}
    by_age: dict[str, dict] = {}
    by_ext: dict[str, dict] = {}
    big_files: list[dict] = []
    total_files = 0
    total_bytes = 0
    skipped_reparse = 0
    unreadable = 0

    for root in roots():
        if not os.path.isdir(root):
            continue
        for dirpath, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
            dirnames[:] = [d for d in dirnames
                           if not os.path.islink(os.path.join(dirpath, d))]
            for name in filenames:
                full = os.path.join(dirpath, name)
                try:
                    st = os.lstat(full)
                except OSError:
                    unreadable += 1
                    continue
                if getattr(st, "st_file_attributes", 0) & FILE_ATTRIBUTE_REPARSE_POINT:
                    skipped_reparse += 1
                    continue
                if not stat.S_ISREG(st.st_mode):
                    continue
                total_files += 1
                total_bytes += st.st_size
                days = max(0.0, (now - st.st_mtime) / 86400.0)
                rel = os.path.relpath(full, root)
                group = rel.split(os.sep)[0] if os.sep in rel else "(根目录)"
                key_group = f"{os.path.basename(root.rstrip(os.sep))}/{group}"
                ext = os.path.splitext(name)[1].lower() or "(无扩展名)"
                bucket = age_bucket(days)
                for table, key in ((by_group, key_group), (by_age, bucket), (by_ext, ext)):
                    row = table.setdefault(key, {"count": 0, "bytes": 0,
                                                 "newest": st.st_mtime, "oldest": st.st_mtime})
                    row["count"] += 1
                    row["bytes"] += st.st_size
                    row["newest"] = max(row["newest"], st.st_mtime)
                    row["oldest"] = min(row["oldest"], st.st_mtime)
                big_files.append({
                    "path": os.path.abspath(full), "size_bytes": st.st_size,
                    "mtime": iso(st.st_mtime), "age_days": round(days, 1),
                    "group": key_group, "ext": ext,
                })

    big_files.sort(key=lambda x: x["size_bytes"], reverse=True)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    json_name = f"pc-temp-space-{stamp}.json"
    md_name = f"pc-temp-space-{stamp}.md"

    def sorted_rows(table):
        return sorted(table.items(), key=lambda kv: kv[1]["bytes"], reverse=True)

    payload = {
        "generated_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "read_only": True,
        "scope": "仅 safe_cleanup.py allow_prefixes() 白名单目录（不含 Windows 更新缓存/回收站/私人目录）",
        "totals": {"files": total_files, "bytes": total_bytes,
                   "skipped_reparse": skipped_reparse, "unreadable": unreadable},
        "by_group": dict(sorted_rows(by_group)),
        "by_age": dict(sorted_rows(by_age)),
        "by_ext": dict(sorted_rows(by_ext)),
        "top_files": big_files[:args.top],
    }
    (out_dir / json_name).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    L = [
        "# 缓存 / 临时目录空间分布（只读分析）",
        "",
        f"- 生成时间：{payload['generated_at']}",
        "- 扫描模式：**READ-ONLY** —— 仅 `os.walk` + `os.lstat`，未删除/移动/重命名任何文件，未独占打开任何句柄",
        f"- 统计口径：普通文件 {total_files} 个 / {human(total_bytes)}；跳过重解析点 {skipped_reparse}、不可读 {unreadable}",
        "",
        "> 本文件只回答「空间在哪」，**不构成清理授权**；不会对下列任何文件采取行动，除非用户逐项确认具体路径。",
        "",
        "## 1. 按一级子目录（体积 TOP 15）",
        "",
        "| 目录 | 文件数 | 体积 | 最旧修改 | 最新修改 |",
        "| :--- | ---: | ---: | :--- | :--- |",
    ]
    for k, v in sorted_rows(by_group)[:15]:
        L.append(f"| `{k}` | {v['count']} | {human(v['bytes'])} | "
                 f"{iso(v['oldest'])[:10]} | {iso(v['newest'])[:10]} |")
    L += [
        "",
        "## 2. 按文件年龄分桶",
        "",
        "| 年龄（按最后修改） | 文件数 | 体积 | 占比 |",
        "| :--- | ---: | ---: | ---: |",
    ]
    for k, v in sorted_rows(by_age):
        pct = 100.0 * v["bytes"] / total_bytes if total_bytes else 0
        L.append(f"| {k} | {v['count']} | {human(v['bytes'])} | {pct:.1f}% |")
    L += [
        "",
        "## 3. 按扩展名（体积 TOP 10）",
        "",
        "| 扩展名 | 文件数 | 体积 |",
        "| :--- | ---: | ---: |",
    ]
    for k, v in sorted_rows(by_ext)[:10]:
        L.append(f"| `{k}` | {v['count']} | {human(v['bytes'])} |")
    L += [
        "",
        f"## 4. 单文件体积 TOP {args.top}",
        "",
        "| # | 完整绝对路径 | 大小 | 最后修改 | 年龄(天) |",
        "| ---: | :--- | ---: | :--- | ---: |",
    ]
    for i, f in enumerate(big_files[:args.top], 1):
        L.append(f"| {i} | `{f['path']}` | {human(f['size_bytes'])} | "
                 f"{f['mtime']} | {f['age_days']} |")
    L += [
        "",
        "## 5. 结论口径",
        "",
        "- 体积大不等于可安全清理：近 30 天内修改的文件多为活跃程序产物，"
        "删除可能打断正在运行的程序/服务，应优先用程序自带清理或系统「存储感知」由用户 GUI 处理。",
        "- 本报告不把「可回收空间」写成「性能提升」，未测的性能数字一律不写。",
        "",
        "---",
        f"原始数据：`{json_name}`",
    ]
    (out_dir / md_name).write_text("\n".join(L) + "\n", encoding="utf-8")

    print(f"[READ-ONLY] 空间分布分析完成，未改动任何被扫描对象")
    print(f"  普通文件 {total_files} / {human(total_bytes)}")
    print(f"  体积最大目录：{sorted_rows(by_group)[0][0]} = {human(sorted_rows(by_group)[0][1]['bytes'])}")
    print(f"  MD : {out_dir / md_name}")
    print(f"  JSON: {out_dir / json_name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
