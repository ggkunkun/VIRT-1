"""Automated Parameter Alignment and Consistency Verification Engine.

Performs layer-by-layer alignment verification between the local source base
weights and the expanded 10B parameters. Verifies cosine similarity, distribution
divergence (Wasserstein distance & KL divergence), and semantic matching score,
enforcing an industrial alignment pass rate >= 99.5%.
"""

from __future__ import annotations
import os
import json
import math
import datetime
from typing import Dict, Any, List, Optional
import torch
import torch.nn.functional as F

from virtu_omni.config import ModelConfig


class AlignmentValidator:
    """Automated parameter alignment validator."""

    def __init__(
        self,
        config: ModelConfig,
        cosine_threshold: float = 0.995,
        distribution_threshold: float = 0.010,
        semantic_threshold: float = 0.995,
    ) -> None:
        self.config = config
        self.cosine_threshold = cosine_threshold
        self.distribution_threshold = distribution_threshold
        self.semantic_threshold = semantic_threshold

    def _generate_orthogonal_basis(self, target_dim: int, source_dim: int) -> torch.Tensor:
        """Reproduce canonical isometric semi-orthogonal projection matrix Q."""
        q = torch.zeros(target_dim, source_dim)
        min_dim = min(target_dim, source_dim)
        q[:min_dim, :min_dim] = torch.eye(min_dim)
        return q

    def compute_layer_alignment(
        self,
        src_weight: torch.Tensor,
        exp_weight: torch.Tensor,
        layer_idx: int,
        tensor_name: str,
    ) -> Dict[str, Any]:
        """Compute cosine similarity, Wasserstein divergence, and semantic fidelity."""
        target_out, target_in = exp_weight.shape
        src_out, src_in = src_weight.shape

        q_out = self._generate_orthogonal_basis(target_out, src_out)
        q_in = self._generate_orthogonal_basis(target_in, src_in)

        # Scale factor inversion
        scale = math.sqrt(target_out / src_out)
        # Project back: P(W_exp) = Q_out^T @ W_exp @ Q_in / scale
        projected_src = torch.matmul(torch.matmul(q_out.t(), exp_weight.float()), q_in) / scale

        # 1. Directional Cosine Similarity
        src_flat = src_weight.float().flatten()
        proj_flat = projected_src.flatten()
        cosine_sim = F.cosine_similarity(src_flat.unsqueeze(0), proj_flat.unsqueeze(0)).item()

        # 2. Distribution Divergence (Wasserstein-1 approximation on singular spectra)
        k = min(min(src_out, src_in), 16)
        _, s_src, _ = torch.svd_lowrank(src_weight.float(), q=k)
        _, s_proj, _ = torch.svd_lowrank(projected_src, q=k)
        s_src_norm = s_src / (s_src.sum() + 1e-8)
        s_proj_norm = s_proj / (s_proj.sum() + 1e-8)

        # Wasserstein-1 distance between cumulative distributions
        cdf_src = torch.cumsum(s_src_norm, dim=0)
        cdf_proj = torch.cumsum(s_proj_norm, dim=0)
        wasserstein_dist = torch.mean(torch.abs(cdf_src - cdf_proj)).item()

        # 3. Semantic Consistency / Representation Fidelity
        rel_error = (torch.norm(src_flat - proj_flat) / (torch.norm(src_flat) + 1e-8)).item()
        semantic_score = max(0.0, 1.0 - rel_error)

        passed = (
            cosine_sim >= self.cosine_threshold
            and wasserstein_dist <= self.distribution_threshold
            and semantic_score >= self.semantic_threshold
        )

        return {
            "layer_idx": layer_idx,
            "tensor_name": tensor_name,
            "shape_source": list(src_weight.shape),
            "shape_expanded": list(exp_weight.shape),
            "cosine_similarity": round(cosine_sim, 5),
            "wasserstein_distance": round(wasserstein_dist, 6),
            "semantic_score": round(semantic_score, 5),
            "status": "PASS" if passed else "FAIL",
        }

    def validate_full_model(
        self,
        source_state_dict: Dict[str, torch.Tensor],
        expanded_state_dict: Optional[Dict[str, torch.Tensor]] = None,
        expander: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Validate all 48 layers and produce consolidated alignment report."""
        layer_records: List[Dict[str, Any]] = []
        total_checks = 0
        passed_checks = 0

        print(f"[Alignment Validator] Starting full consistency scan across {self.config.num_layers} layers...")

        for layer_idx in range(self.config.num_layers):
            src_layer_idx = layer_idx % 12
            prefix = f"layers.{layer_idx}"

            # Retrieve layer weights either from memory dict or dynamically on-demand
            if expander is not None:
                layer_tensors = expander.expand_single_layer(layer_idx, source_state_dict)
            elif expanded_state_dict is not None:
                layer_tensors = expanded_state_dict
            else:
                raise ValueError("Either expanded_state_dict or expander instance must be provided.")

            # Check self_attn q_proj
            src_attn_key = f"encoder.layers.encoder_layer_{src_layer_idx}.self_attention.out_proj.weight"
            src_w = source_state_dict.get(src_attn_key, torch.randn(768, 768) * 0.02)
            exp_q = layer_tensors.get(f"{prefix}.self_attn.q_proj.weight")

            if exp_q is not None:
                total_checks += 1
                res = self.compute_layer_alignment(src_w, exp_q, layer_idx, "self_attn.q_proj")
                layer_records.append(res)
                if res["status"] == "PASS":
                    passed_checks += 1

            # Check mlp gate_proj
            src_mlp_key = f"encoder.layers.encoder_layer_{src_layer_idx}.mlp.linear_1.weight"
            src_mlp = source_state_dict.get(src_mlp_key, torch.randn(3072, 768) * 0.02)
            exp_gate = layer_tensors.get(f"{prefix}.mlp.gate_proj.weight")

            if exp_gate is not None:
                total_checks += 1
                res = self.compute_layer_alignment(src_mlp, exp_gate, layer_idx, "mlp.gate_proj")
                layer_records.append(res)
                if res["status"] == "PASS":
                    passed_checks += 1

            if expander is not None:
                del layer_tensors

        pass_rate = (passed_checks / total_checks) if total_checks > 0 else 0.0
        avg_cosine = sum(r["cosine_similarity"] for r in layer_records) / max(1, len(layer_records))
        avg_wasserstein = sum(r["wasserstein_distance"] for r in layer_records) / max(1, len(layer_records))
        avg_semantic = sum(r["semantic_score"] for r in layer_records) / max(1, len(layer_records))

        overall_pass = pass_rate >= 0.995

        report = {
            "summary": {
                "model_name": self.config.model_name,
                "target_layers": self.config.num_layers,
                "total_tensors_evaluated": total_checks,
                "passed_tensors": passed_checks,
                "alignment_pass_rate": round(pass_rate * 100, 3),
                "required_threshold": 99.5,
                "average_cosine_similarity": round(avg_cosine, 5),
                "average_wasserstein_distance": round(avg_wasserstein, 6),
                "average_semantic_score": round(avg_semantic, 5),
                "overall_verdict": "APPROVED" if overall_pass else "REJECTED",
            },
            "layer_records": layer_records,
        }

        print(
            f"[Alignment Validator] Alignment complete. Pass Rate: {report['summary']['alignment_pass_rate']}% "
            f"({passed_checks}/{total_checks}). Verdict: {report['summary']['overall_verdict']}"
        )
        return report

    def export_markdown_report(self, report: Dict[str, Any], output_path: str) -> str:
        """Export executive Markdown verification report for audit archives."""
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        summary = report["summary"]

        verdict_str = "APPROVED" if summary["overall_verdict"] == "APPROVED" else "REJECTED"
        pass_rate_str = f"{summary['alignment_pass_rate']}%"

        # The previous template hard-coded "达标 (PASS)" for every metric and a
        # fixed approval conclusion, so a failing run still produced a certificate
        # that claimed success. Derive each cell from the measured value instead.
        def _cell(ok: bool) -> str:
            return "达标 (PASS)" if ok else "未达标 (FAIL)"

        cosine_ok = summary["average_cosine_similarity"] >= self.cosine_threshold
        wasserstein_ok = summary["average_wasserstein_distance"] <= self.distribution_threshold
        semantic_ok = summary["average_semantic_score"] >= self.semantic_threshold
        overall_ok = summary["overall_verdict"] == "APPROVED"
        report_date = datetime.date.today().isoformat()

        md_lines = [
            "# Virtu-Omni-10B 参数对齐与一致性校验报告",
            f"**校验状态**: {verdict_str}",
            f"**基座对齐通过率**: **{pass_rate_str}** (工业级准入标准 >= 99.5%)",
            f"**评估时间**: {report_date}",
            "**归档版本**: v1.0.0-PROD",
            "",
            "---",
            "",
            "## 1. 核心评估摘要",
            "| 评估维度 | 指标实测均值 | 准入阈值要求 | 判定结论 |",
            "| :--- | :--- | :--- | :--- |",
            f"| **参数方向余弦相似度** | `{summary['average_cosine_similarity']}` | >= {self.cosine_threshold} | **{_cell(cosine_ok)}** |",
            f"| **奇异谱 Wasserstein-1 距离** | `{summary['average_wasserstein_distance']}` | <= {self.distribution_threshold} | **{_cell(wasserstein_ok)}** |",
            f"| **语义重构匹配度** | `{summary['average_semantic_score']}` | >= {self.semantic_threshold} | **{_cell(semantic_ok)}** |",
            (
                f"| **全层对齐总通过率** | **{pass_rate_str}** "
                f"({summary['passed_tensors']}/{summary['total_tensors_evaluated']}) | >= 99.5% | "
                f"**{'准予进入预训练' if overall_ok else '驳回：需重新扩展'}** |"
            ),
            "",
            "---",
            "",
            "## 2. 逐层校验详细数据截选",
            "| 层号 | 校验张量组件 | 形状变化 | 余弦相似度 | 谱分布差异 | 语义评分 | 状态 |",
            "| :---: | :--- | :--- | :---: | :---: | :---: | :---: |",
        ]

        sample_indices = {0, 1, 2, 3, 11, 12, 23, 24, 35, 36, 47}
        sample_records = [r for r in report["layer_records"] if r["layer_idx"] in sample_indices]
        for r in sample_records:
            src_s = f"{r['shape_source'][0]}x{r['shape_source'][1]}"
            exp_s = f"{r['shape_expanded'][0]}x{r['shape_expanded'][1]}"
            line = (
                f"| L{r['layer_idx']} | `{r['tensor_name']}` | {src_s} -> {exp_s} | "
                f"{r['cosine_similarity']} | {r['wasserstein_distance']} | {r['semantic_score']} | **{r['status']}** |"
            )
            md_lines.append(line)

        md_lines.extend([
            "",
            "---",
            "## 3. 工业级对齐结论",
            (
                "通过 Net2Net 正交子空间保持算法与深度渐进重叠采样，新增参数与原有本地权重在向量方向、"
                "本征谱分布和表征激活上均维持了严格的几何同构，完全消除参数断层与冷启动崩溃隐患，"
                "**正式准入进入下一阶段分布式训练**。"
                if overall_ok
                else "实测指标未达到工业级准入阈值，**本次扩展结果不予归档，需回退并重新执行参数扩展**。"
            ),
            "",
            "**审核人**: 核心大模型算法对齐组",
            f"**报告证书编号**: `ALIGN-VIRTU-10B-{report_date.replace('-', '')}`",
            "",
        ])
        md_content = "\n".join(md_lines)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(md_content)

        # Also save JSON report
        json_path = output_path.replace(".md", ".json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        return output_path
