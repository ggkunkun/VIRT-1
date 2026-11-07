# -*- coding: utf-8 -*-
"""STEP 语料编码归一化：GBK → UTF-8（消除领域模型训练/推理时的乱码锚点）。

背景：SolidWorks 2021 中文版导出的 STEP(AP203) 直接把中文零件名写成 GBK 字节，
不符合 STEP 字符串应为 Latin-1 / \\X2\\ 转义的规范。UTF-8 分词器读这些字节会
产生乱码 token，导致 13.63B 模型连零件名都识别不了。

两种输出模式：
  * utf8   (默认)：GBK 字节直接解码后重新编码为 UTF-8 文本。对 LLM 最友好，
                    但严格说不符合 ISO-10303-21 字符串规范（多数解析器仍能读）。
  * x2      (合规)：把非 ASCII 字符转成 STEP 标准 \\X2\\HHHH\\X0\\ 转义，
                    文件保持纯 ASCII，任何合规 STEP 解析器都能读。

安全约束：默认【不覆盖原文件】，产物写到独立输出目录；支持 --dry-run 只报告。
用法:
  python3 bridges/step_normalize.py --dir assets --out-dir data/step_utf8 --dry-run
  python3 bridges/step_normalize.py --dir assets --out-dir data/step_utf8 --mode utf8
  python3 bridges/step_normalize.py --file "xxx.step" --out-dir data/step_utf8 --mode x2
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from typing import Any, Dict, List

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from step_bom import detect_encoding  # noqa: E402


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()[:16]


def to_x2_escapes(text: str) -> str:
    """把非 ASCII 字符转成 ISO-10303-21 的 \\X2\\HHHH\\X0\\ 转义（UTF-16BE）。"""
    out = []
    buf = []
    for ch in text:
        if ord(ch) < 128:
            if buf:
                out.append("\\X2\\" + "".join(buf) + "\\X0\\")
                buf = []
            out.append(ch)
        else:
            cp = ord(ch)
            if cp <= 0xFFFF:
                buf.append("%04X" % cp)
            else:  # 代理对
                cp -= 0x10000
                buf.append("%04X" % (0xD800 + (cp >> 10)))
                buf.append("%04X" % (0xDC00 + (cp & 0x3FF)))
    if buf:
        out.append("\\X2\\" + "".join(buf) + "\\X0\\")
    return "".join(out)


def normalize_bytes(raw: bytes, mode: str = "utf8") -> bytes:
    """返回归一化后的字节；若已是 UTF-8 且 mode=utf8 则原样返回。"""
    enc = detect_encoding(raw)
    if enc == "latin-1":
        # 无法可靠判定，按 gbk 尽力解码
        text = raw.decode("gbk", errors="replace")
    elif enc == "utf-8":
        text = raw.decode("utf-8")
    else:  # gbk
        text = raw.decode("gbk")
    if mode == "x2":
        return to_x2_escapes(text).encode("ascii")
    return text.encode("utf-8")


def find_steps(dirs: List[str], files: List[str]) -> List[str]:
    out = list(files)
    for d in dirs:
        if os.path.isfile(d):
            out.append(d)
            continue
        for base, _sub, fns in os.walk(d):
            if any(s in base for s in (".git", "__pycache__", ".venv")):
                continue
            for fn in fns:
                if fn.lower().endswith((".step", ".stp")):
                    out.append(os.path.join(base, fn))
    return sorted(set(out))


def main(argv=None):
    ap = argparse.ArgumentParser(description="STEP GBK→UTF-8 语料归一化")
    ap.add_argument("--dir", action="append", default=[], help="输入目录(可多次)")
    ap.add_argument("--file", action="append", default=[], help="单个输入文件(可多次)")
    ap.add_argument("--out-dir", default="data/step_utf8", help="输出目录(不覆盖源文件)")
    ap.add_argument("--mode", choices=["utf8", "x2"], default="utf8")
    ap.add_argument("--dry-run", action="store_true", help="只报告不写文件")
    ap.add_argument("--report", default="", help="写出 JSON 报告路径")
    a = ap.parse_args(argv)

    if not a.dir and not a.file:
        a.dir = ["assets"]
    paths = find_steps(a.dir, a.file)
    if not paths:
        print("[!] 未找到 .step 文件")
        return 1

    records: List[Dict[str, Any]] = []
    for p in paths:
        raw = open(p, "rb").read()
        enc = detect_encoding(raw)
        rec: Dict[str, Any] = {
            "path": p.replace("\\", "/"),
            "file": os.path.basename(p),
            "src_bytes": len(raw),
            "src_sha256": sha256_bytes(raw),
            "src_encoding": enc,
            "needed": enc != "utf-8",
        }
        try:
            out = normalize_bytes(raw, a.mode)
            rec["out_bytes"] = len(out)
            rec["out_sha256"] = sha256_bytes(out)
            if not a.dry_run:
                # 保持相对目录结构，避免同名覆盖
                rel = os.path.basename(p)
                if a.dir:
                    for d in a.dir:
                        if os.path.isdir(d) and os.path.abspath(p).startswith(
                                os.path.abspath(d) + os.sep):
                            rel = os.path.relpath(p, d)
                            break
                dst = os.path.join(a.out_dir, rel)
                os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)
                with open(dst, "wb") as f:
                    f.write(out)
                rec["output_path"] = dst.replace("\\", "/")
            rec["status"] = "ok"
        except Exception as exc:  # noqa: BLE001
            rec["status"] = "error"
            rec["error"] = "%s: %s" % (type(exc).__name__, exc)
        records.append(rec)

    need = sum(1 for r in records if r["needed"])
    ok = sum(1 for r in records if r["status"] == "ok")
    report = {
        "tool": "bridges.step_normalize",
        "basis": "measured",
        "mode": a.mode,
        "dry_run": a.dry_run,
        "out_dir": a.out_dir,
        "sample_size_n": len(records),
        "need_conversion": need,
        "ok_count": ok,
        "error_count": len(records) - ok,
        "records": records,
    }
    print("[step_normalize] mode=%s dry_run=%s n=%d 需转换=%d 成功=%d 失败=%d" %
          (a.mode, a.dry_run, len(records), need, ok, len(records) - ok))
    for r in records:
        flag = "GBK→%s" % a.mode if r["needed"] else "已是UTF-8(跳过内容变化)"
        print("  %-38s %-8s %-22s %s" % (
            r["file"][:38], r["src_encoding"], flag,
            r.get("output_path", "(dry-run)") if r["status"] == "ok" else r.get("error")))
    if a.report:
        os.makedirs(os.path.dirname(os.path.abspath(a.report)), exist_ok=True)
        with open(a.report, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print("[+] 写出报告: %s" % a.report)
    return 0 if report["error_count"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
