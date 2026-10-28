"""Executable runner for distributed Code LLM pretraining."""

import os
import sys
import torch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from virtu_code.config import CodeTrainingConfig  # noqa: E402
from virtu_code.training.trainer import DistributedCodeTrainer  # noqa: E402
from virtu_code.training.model import CodeTransformerLM  # noqa: E402


def synthetic_batch_stream(batch_size: int = 4, seq_len: int = 128, vocab_size: int = 1000):
    """Infinite batch generator for pretraining verification."""
    while True:
        input_ids = torch.randint(0, vocab_size, (batch_size, seq_len))
        labels = input_ids.clone()
        yield {"input_ids": input_ids, "labels": labels}


def main() -> None:
    print("================================================================")
    print("  VirtuCode: Distributed Code LLM Pretraining Engine")
    print("================================================================")

    # Scaled profile for reliable local execution verification
    config = CodeTrainingConfig(
        hidden_dim=256,
        intermediate_dim=512,
        num_layers=2,
        num_attention_heads=4,
        num_kv_heads=2,
        learning_rate=3e-4,
        checkpoint_dir=os.path.join("checkpoints", "code_llm"),
        training_log_path=os.path.join("logs", "code_training.jsonl"),
    )

    model = CodeTransformerLM(config, vocab_size=1000)
    trainer = DistributedCodeTrainer(config=config, model=model)

    print(f"Model Parameters: {sum(p.numel() for p in model.parameters()):,}")
    print(f"Device: {trainer.device}")

    stream = synthetic_batch_stream(batch_size=4, seq_len=64, vocab_size=1000)
    print("Running training loop with periodic checkpointing...")
    results = trainer.train_steps(stream, total_steps=20, checkpoint_interval=10)

    report_path = os.path.join("benchmarks", "training_metrics_report.md")
    trainer.monitor.export_report(results["checkpoints"], report_path)

    print("\n[Pretraining Execution Complete]")
    print(f"- Steps Completed: {results['completed_steps']}")
    print(f"- Final Train Loss: {results['final_loss']}")
    print(f"- Saved Checkpoints: {len(results['checkpoints'])}")
    print(f"- Metrics Report Generated at: {report_path}")


if __name__ == "__main__":
    main()
