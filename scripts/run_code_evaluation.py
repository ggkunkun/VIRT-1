"""Executable runner for multi-language code capability verification."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from virtu_code.config import EvaluationConfig  # noqa: E402
from virtu_code.evaluation.benchmark import CodeCapabilityBenchmark  # noqa: E402


def main() -> None:
    print("================================================================")
    print("  VirtuCode: 10-Language Multi-Dimensional Capability Benchmark")
    print("================================================================")

    config = EvaluationConfig(passing_threshold_score=75.0)
    evaluator = CodeCapabilityBenchmark(config)

    print("Synthesizing standard 10-language benchmark dataset...")
    dataset = evaluator.generate_standard_benchmark_dataset()

    print("Executing evaluation across 5 quantitative capability dimensions...")
    summary = evaluator.run_evaluation(dataset)

    report_path = os.path.join("benchmarks", "code_capability_report.md")
    evaluator.export_report(summary, report_path)

    release_dir = os.path.join("checkpoints", "code_llm_release_v1.0.0")
    manifest = evaluator.archive_qualified_release(summary, release_dir=release_dir)

    print("\n[Evaluation Execution Complete]")
    print(f"- Overall Mean Score: {summary['overall_mean_score']} / 100")
    print(f"- Passing Threshold: {config.passing_threshold_score}")
    print(f"- Verdict: {summary['verdict']}")
    print(f"- Verification Report: {report_path}")
    print(f"- Release Manifest Archived at: {manifest}")


if __name__ == "__main__":
    main()
