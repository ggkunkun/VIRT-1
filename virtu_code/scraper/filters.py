"""Three-level auditable repository filter for code LLM training compliance.

Level 1: License Type Filter (OSI-approved permissive only, strict Copyleft block).
Level 2: Activity Filter (Commit activity, star range, contributor count, issue response).
Level 3: Quality & Structure Filter (Structural integrity, LOC threshold, empty repo exclusion).
"""

from __future__ import annotations
from typing import Dict, Any, Tuple
from virtu_code.config import ScraperConfig


class ThreeLevelRepositoryFilter:
    """Configurable and auditable 3-level repository screening engine."""

    def __init__(self, config: ScraperConfig) -> None:
        self.config = config

    def evaluate_level_1_license(self, repo_info: Dict[str, Any]) -> Tuple[bool, str]:
        """Level 1: Validate open-source license allows commercial and model pretraining."""
        spdx_id = repo_info.get("license_spdx", "").strip()
        license_name = repo_info.get("license_name", "").strip()

        # Check prohibited Copyleft / Restricted licenses first
        for prohibited in self.config.prohibited_licenses:
            if prohibited.lower() in spdx_id.lower() or prohibited.lower() in license_name.lower():
                return False, f"REJECTED_L1_COPYLEFT_OR_RESTRICTED: License '{spdx_id or license_name}' is copyleft"

        # Check permitted OSI permissive licenses
        for allowed in self.config.allowed_licenses:
            if allowed.lower() == spdx_id.lower() or allowed.lower() in license_name.lower():
                return True, f"PASSED_L1_LICENSE: '{allowed}' is OSI permissive certified"

        return False, (
            f"REJECTED_L1_UNKNOWN_OR_MISSING: License '{spdx_id or license_name}' is not in approved allowlist"
        )

    def evaluate_level_2_activity(self, repo_info: Dict[str, Any]) -> Tuple[bool, str]:
        """Level 2: Validate project activity and community maintenance health."""
        stars = repo_info.get("stars", 0)
        days_since_commit = repo_info.get("days_since_last_commit", 9999)
        contributors = repo_info.get("contributors_count", 0)
        issue_turnaround_days = repo_info.get("avg_issue_resolution_days", 999)

        if not (self.config.min_stars <= stars <= self.config.max_stars):
            return False, (
                f"REJECTED_L2_STARS: Star count {stars} out of bounds "
                f"[{self.config.min_stars}, {self.config.max_stars}]"
            )

        if days_since_commit > self.config.max_days_since_last_commit:
            return False, (
                f"REJECTED_L2_INACTIVE: Last commit {days_since_commit}d ago "
                f"exceeds {self.config.max_days_since_last_commit}d"
            )

        if contributors < self.config.min_contributors:
            return False, (
                f"REJECTED_L2_CONTRIBUTORS: Contributor count {contributors} "
                f"below min {self.config.min_contributors}"
            )

        if issue_turnaround_days > self.config.max_issue_resolution_days:
            return False, (
                f"REJECTED_L2_ISSUE_LATENCY: Issue turnaround {issue_turnaround_days}d "
                f"exceeds max {self.config.max_issue_resolution_days}d"
            )

        return True, "PASSED_L2_ACTIVITY: Project demonstrates sustained community maintenance"

    def evaluate_level_3_quality(self, repo_info: Dict[str, Any]) -> Tuple[bool, str]:
        """Level 3: Validate code structure, test completeness, and business LOC."""
        loc = repo_info.get("business_loc", 0)
        structures = repo_info.get("structure_tree", [])
        is_fork = repo_info.get("is_fork", False)
        fork_delta_commits = repo_info.get("fork_delta_commits", 0)

        if loc < self.config.min_business_loc:
            return False, (
                f"REJECTED_L3_EMPTY_OR_LOW_LOC: Business code LOC {loc} "
                f"below minimum {self.config.min_business_loc}"
            )

        if is_fork and self.config.exclude_forks_with_zero_delta and fork_delta_commits == 0:
            return False, "REJECTED_L3_ZERO_DELTA_FORK: Unmodified fork detected"

        # Check required structural presence
        has_structural_marker = False
        for marker in self.config.required_structural_markers:
            if any(marker.lower() in item.lower() for item in structures):
                has_structural_marker = True
                break

        if not has_structural_marker:
            return False, "REJECTED_L3_IRREGULAR_STRUCTURE: Missing standard directories (src/lib/test/README)"

        return True, "PASSED_L3_QUALITY: Meets code quality, LOC, and structural standards"

    def evaluate(self, repo_info: Dict[str, Any]) -> Dict[str, Any]:
        """Execute full 3-level evaluation sequence, logging decision chain."""
        repo_name = repo_info.get("full_name", "unknown/unknown")

        # Step 1
        l1_pass, l1_reason = self.evaluate_level_1_license(repo_info)
        if not l1_pass:
            return {
                "repo_name": repo_name,
                "overall_verdict": "REJECTED",
                "stage": "LEVEL_1_LICENSE",
                "reason": l1_reason,
            }

        # Step 2
        l2_pass, l2_reason = self.evaluate_level_2_activity(repo_info)
        if not l2_pass:
            return {
                "repo_name": repo_name,
                "overall_verdict": "REJECTED",
                "stage": "LEVEL_2_ACTIVITY",
                "reason": l2_reason,
            }

        # Step 3
        l3_pass, l3_reason = self.evaluate_level_3_quality(repo_info)
        if not l3_pass:
            return {
                "repo_name": repo_name,
                "overall_verdict": "REJECTED",
                "stage": "LEVEL_3_QUALITY",
                "reason": l3_reason,
            }

        return {
            "repo_name": repo_name,
            "overall_verdict": "APPROVED",
            "stage": "COMPLETED",
            "reason": "All 3-level filters satisfied with full compliance.",
            "metadata": repo_info,
        }
