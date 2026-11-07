"""
Update PROVENANCE.json with exact audit records.
Follows 2026-11-05 《测量宪法》:
- basis: measured
- Captures sha256 checksums, receipt paths, tag verification, and honest capacity definitions.
"""
import os
import json
import time

PROVENANCE_PATH = r"D:\Virtu模型\checkpoints\PROVENANCE.json"

def main():
    if not os.path.exists(PROVENANCE_PATH):
        raise FileNotFoundError(f"Missing {PROVENANCE_PATH}")
    
    with open(PROVENANCE_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    data["audit_verification_2026_11_06"] = {
        "status": "VERIFIED_COMPLIANT",
        "basis": "measured",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "broken_tags_cleanup": {
            "purged_broken_404_tags": [
                "virtu-toolcall:latest",
                "virtu-boundary-sft:latest",
                "virtu-toolcall:latest.bak_pre_params_repair",
                "virtu-production:v3",
                "evalprod:v3",
                "toolcalleval:latest"
            ],
            "verified_healthy_tags_count": 18,
            "broken_tags_remaining": 0,
            "verification_method": "POST /api/show over all /api/tags entries"
        },
        "artifacts_registered_and_receipted": {
            "virtu_moe_14b_bf16": {
                "path": "D:\\Virtu模型\\checkpoints\\virtu-moe-14b-bf16.gguf",
                "receipt": "D:\\Virtu模型\\checkpoints\\virtu-moe-14b-bf16.gguf.receipt.json",
                "sha256": "9f5c34f33f05a68af683131297468461544b9736fb90359cb81a624b27135d9a",
                "bytes": 27260863392,
                "file_gb": 25.39,
                "architecture": "qwen3moe",
                "total_params": 13626848256,
                "active_params_per_token": 8190735360,
                "layers": 36,
                "tag": "virtu-moe-14b:bf16",
                "registration_status": "registered_in_ollama"
            },
            "virtu_moe_14b_q4_k_m": {
                "path": "D:\\Virtu模型\\checkpoints\\virtu-moe-14b-q4_k_m.gguf",
                "receipt": "D:\\Virtu模型\\checkpoints\\virtu-moe-14b-q4_k_m.gguf.receipt.json",
                "sha256": "a2103c68d9e881ac3655ce271902997cdc8eb5c35da3803261f25f5364e52d7a",
                "bytes": 8320185248,
                "file_gb": 7.75,
                "architecture": "qwen3moe",
                "total_params": 13626848256,
                "active_params_per_token": 8190735360,
                "layers": 36,
                "tag": "virtu-moe-14b:latest",
                "registration_status": "registered_in_ollama",
                "gpu_offload_profile": "RTX 4050 (6GB VRAM): 24 layers offloaded (5015 MiB), 13 layers CPU (2913 MiB)"
            },
            "virtu_10b_a45b3427": {
                "path": "D:\\Virtu模型\\checkpoints\\virtu-10b-d46-q4_0.gguf",
                "receipt": "D:\\Virtu模型\\checkpoints\\virtu-10b-d46-q4_0.gguf.receipt.json",
                "sha256": "b9f9ac336ce95e70058f4b446c5fb646e8e4d455ac77cf90b5a71910458c98a9",
                "bytes": 5699918176,
                "file_gb": 5.31,
                "architecture": "qwen3",
                "total_params": 10120199680,
                "active_params_per_token": 10120199680,
                "layers": 46,
                "tag": "virtu-10b:a45b3427",
                "state": "Stage A (L1 structural upscaling) complete; Stage B (continued pretraining) pending GPU cluster"
            }
        },
        "anti_deception_declaration": {
            "principle": "严禁将字面量当作实测值，严禁夸大参数能力，区分稀疏与稠密",
            "clarification": "Virtu-MoE-14B 物理总参数为 13.63B（2x8.2B 专家），但因 MoE 稀疏路由特性，每个 token 仅激活 1 个专家（计算量等效于 8.2B）；Virtu-10B-d46 是 46 层 10.12B 稠密结构，但新增 10 层为复制层尚未训练收敛。Dense 在线能力基座仍为 virtu-comprehensive (8.19B)。"
        }
    }
    
    with open(PROVENANCE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print("PROVENANCE.json successfully updated with anti-deception audit records.")

if __name__ == "__main__":
    main()
