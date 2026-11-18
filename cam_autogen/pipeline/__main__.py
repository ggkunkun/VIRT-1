"""CLI 入口：`python -m cam_autogen.pipeline [--serve | --example shaft | --input part.json]`。"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from cam_autogen.common import serve
from cam_autogen.contracts import WorkpieceSpec
from cam_autogen.examples import EXAMPLES
from cam_autogen.pipeline.orchestrator import PipelineRequest, run_pipeline


def main() -> None:
    ap = argparse.ArgumentParser(description="CAM 自动化加工程序端到端生成")
    ap.add_argument("--serve", action="store_true", help="以 REST API 服务运行 (:8100)")
    ap.add_argument("--port", type=int, default=8100)
    ap.add_argument("--example", choices=sorted(EXAMPLES), default="shaft")
    ap.add_argument("--input", type=str, help="工件 JSON 文件路径")
    ap.add_argument("--dialect", choices=["FANUC", "SIEMENS", "HUAZHONG"], default="FANUC")
    ap.add_argument("--machine", type=str, default=None)
    ap.add_argument("--out", type=str, default=None)
    ap.add_argument("--web-lookup", action="store_true")
    args = ap.parse_args()

    if args.serve:
        serve("cam_autogen.pipeline.api:app", args.port)
        return

    wp_raw = json.loads(Path(args.input).read_text(encoding="utf-8")) if args.input else EXAMPLES[args.example]
    req = PipelineRequest(
        workpiece=WorkpieceSpec.model_validate(wp_raw),
        preferred_dialect=args.dialect,
        preferred_machine=args.machine,
        output_dir=args.out,
        enable_web_lookup=args.web_lookup,
    )
    res = run_pipeline(req)
    print(json.dumps({
        "trace_id": res.trace_id,
        "status": res.status,
        "process_type": res.recognition.process_type.value if res.recognition else None,
        "confidence": res.recognition.confidence if res.recognition else None,
        "machine": res.machine_setup.machine.model if res.machine_setup else None,
        "verification_passed": res.verification.passed if res.verification else None,
        "timings_ms": res.stage_timings_ms,
        "output_files": res.output_files,
        "errors": res.errors,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
