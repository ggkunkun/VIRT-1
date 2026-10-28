"""Script to run automated parameter alignment validation across all 48 layers."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from virtu_omni.config import ModelConfig
from virtu_omni.models.expander import BaseParameterExpander
from virtu_omni.alignment.aligner import AlignmentValidator


def main() -> None:
    print("================================================================")
    print("  Virtu-Omni-10B: Automated Parameter Alignment Verification")
    print("================================================================")
    config = ModelConfig()
    expander = BaseParameterExpander(config=config)

    src_weights = expander.load_source_weights()

    validator = AlignmentValidator(
        config=config,
        cosine_threshold=0.995,
        distribution_threshold=0.010,
        semantic_threshold=0.995,
    )

    report = validator.validate_full_model(src_weights, expander=expander)

    out_md = os.path.join("benchmarks", "alignment_report.md")
    validator.export_markdown_report(report, out_md)

    print(f"[Done] Formal Alignment Report generated at: {out_md}")
    if report["summary"]["overall_verdict"] == "APPROVED":
        print(">>> RESULT: [PASS] Parameter Alignment APPROVED (>=99.5% Pass Rate).")
        sys.exit(0)
    else:
        print(">>> RESULT: [FAIL] Parameter Alignment REJECTED.")
        sys.exit(1)


if __name__ == "__main__":
    main()
