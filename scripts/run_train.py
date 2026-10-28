"""Script to execute distributed training simulation with real-time health guard."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from virtu_omni.config import VirtuOmniConfig
from virtu_omni.data.pipeline import StreamingMultimodalDataPipeline
from virtu_omni.training.trainer import Distributed3DTrainer
from virtu_omni.training.monitor import TrainingHealthMonitor


def main() -> None:
    print("================================================================")
    print("  Virtu-Omni-10B: Distributed Training & Monitoring Pipeline")
    print("================================================================")
    config = VirtuOmniConfig()

    # Hardware profile detection: dev machine vs multi-GPU cluster
    try:
        if sys.platform == "win32":
            import ctypes

            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]
            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
            ram_gb = stat.ullTotalPhys / (1024 ** 3)
        else:
            with open("/proc/meminfo") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        ram_gb = int(line.split()[1]) / (1024 * 1024)
                        break
    except Exception:
        ram_gb = 16.0

    if ram_gb < 48.0 and "--full" not in sys.argv:
        print(f"[Notice] Host RAM = {ram_gb:.1f}GB (< 48GB required for unpartitioned 10B).")
        print("[Notice] Using fast scalable profile to verify 3D training loop, EMA loss monitor & checkpointing.")
        config.model.num_layers = 2
        config.model.hidden_dim = 1024
        config.model.intermediate_dim = 2048
        config.model.num_attention_heads = 8
        config.model.num_key_value_heads = 2

    pipeline = StreamingMultimodalDataPipeline(config.data)
    monitor = TrainingHealthMonitor(config.monitor)
    trainer = Distributed3DTrainer(config=config, monitor=monitor)

    # Generate streaming training batches
    batch_stream = pipeline.generate_streaming_batches(num_samples=200, batch_size=4)
    results = trainer.train_loop(data_iterator=batch_stream, num_steps=20)

    print("\n[Done] Training pipeline executed successfully.")
    print(f"Final Step: {results['completed_steps']} | Final Loss: {results['final_loss']}")


if __name__ == "__main__":
    main()
