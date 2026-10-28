"""Unit tests for Code Capability Benchmark."""

import os
import tempfile
from virtu_code.config import EvaluationConfig
from virtu_code.evaluation.benchmark import CodeCapabilityBenchmark


def test_standard_dataset_synthesis() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        ds_path = os.path.join(tmp_dir, "eval.json")
        rep_path = os.path.join(tmp_dir, "rep.md")
        cfg = EvaluationConfig(benchmark_dataset_path=ds_path, report_output_path=rep_path)
        evaluator = CodeCapabilityBenchmark(cfg)

        dataset = evaluator.generate_standard_benchmark_dataset()
        assert len(dataset["test_cases"]) == 10
        assert len(dataset["languages_covered"]) == 10
        assert os.path.exists(ds_path)


def test_evaluation_scoring_and_report() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        ds_path = os.path.join(tmp_dir, "eval.json")
        rep_path = os.path.join(tmp_dir, "rep.md")
        cfg = EvaluationConfig(
            passing_threshold_score=75.0,
            benchmark_dataset_path=ds_path,
            report_output_path=rep_path,
        )
        evaluator = CodeCapabilityBenchmark(cfg)
        dataset = evaluator.generate_standard_benchmark_dataset()

        summary = evaluator.run_evaluation(dataset)
        assert summary["overall_mean_score"] > 80.0
        assert summary["verdict"] == "APPROVED"
        assert len(summary["language_results"]) == 10

        evaluator.export_report(summary, rep_path)
        assert os.path.exists(rep_path)

        release_dir = os.path.join(tmp_dir, "release")
        manifest = evaluator.archive_qualified_release(summary, release_dir=release_dir)
        assert os.path.exists(manifest)
