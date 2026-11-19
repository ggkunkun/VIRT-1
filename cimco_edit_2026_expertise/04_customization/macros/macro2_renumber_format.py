#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""宏脚本工具 2：NC 程序批量重编号 + 规范化格式化工具。

复现 CIMCO Edit 的 "Block Numbers / Renumbering" + "Load/Save 规范化" 能力（工程等价实现）。
规则对齐官方 .MAC 的 [RENUM] 段默认：START=100, INTERVAL=1(此处可配), PRECEEDESTR=N,
SKIP=%,O（跳过程序起始符与程序号行）。

用法：
  python macro2_renumber_format.py --in a.nc --out b.nc --start 100 --step 10
  python macro2_renumber_format.py --dir <目录> --inplace --start 1000 --step 10
注意：本工具只处理"ISO G-code 行首块号"，不解析宏表达式语义；复杂程序上线前仍需 CIMCO GUI 复核。
"""
import re, os, sys, argparse, glob, time

SKIP_PREFIX = ("%", "O")  # 对齐 .MAC [RENUM] SKIP=%,O

def is_skippable(stripped):
    if not stripped:
        return True
    if stripped.startswith(SKIP_PREFIX):
        return True
    if stripped.startswith("("):  # 纯注释行
        return True
    return False

def renumber(text, start=100, step=10):
    out = []
    n = start
    for line in text.splitlines():
        s = line.strip()
        if is_skippable(s):
            out.append(line.rstrip())
            continue
        # 去掉已有行首 Nxxx（含可能的前导空格）
        body = re.sub(r"^N\d+\s*", "", s)
        out.append(f"N{n}{body}")
        n += step
    # 保留 ISO 结束符与末尾换行
    return "\n".join(out).rstrip() + "\n"

def process(args):
    t0 = time.time()
    files = []
    if args.dir:
        pat = os.path.join(args.dir, "**", "*") if args.recursive else os.path.join(args.dir, "*")
        files = [p for p in glob.glob(pat, recursive=args.recursive)
                 if p.lower().endswith((".nc", ".tap", ".txt"))]
    elif args.input:
        files = [args.input]
    done = []
    for p in sorted(files):
        code = open(p, encoding="utf-8", errors="ignore").read()
        new = renumber(code, args.start, args.step)
        if args.inplace:
            dst = p
        elif args.out:
            dst = args.out if len(files) == 1 else os.path.join(os.path.dirname(args.out), os.path.basename(p))
        else:
            dst = p + ".renum"
        with open(dst, "w", encoding="utf-8", newline="\n") as f:
            f.write(new)
        done.append({"src": p, "dst": dst, "blocks": sum(1 for l in new.splitlines() if re.match(r"^\s*N\d+", l))})
    return {"tool": "macro2_renumber_format", "run_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "start": args.start, "step": args.step, "count": len(done),
            "elapsed_sec": round(time.time() - t0, 3), "files": done,
            "honest_note": "工程等价实现，对齐CIMCO .MAC [RENUM] 规则；复杂程序需GUI复核"}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input")
    ap.add_argument("--dir")
    ap.add_argument("--out")
    ap.add_argument("--inplace", action="store_true")
    ap.add_argument("--recursive", action="store_true")
    ap.add_argument("--start", type=int, default=100)
    ap.add_argument("--step", type=int, default=10)
    ap.add_argument("--report", default=None)
    a = ap.parse_args()
    if not a.input and not a.dir:
        ap.error("需要 --input 或 --dir")
    r = process(a)
    if a.report:
        with open(a.report, "w", encoding="utf-8") as f:
            import json; json.dump(r, f, ensure_ascii=False, indent=2)
    print(f"[macro2] processed={r['count']} start={r['start']} step={r['step']}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
