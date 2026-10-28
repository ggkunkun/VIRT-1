"""Compliant GitHub repository crawler with rate-limiting and cryptographic audit logging.

Outputs:
1. Approved compliant repository manifest.
2. Cryptographically hash-chained audit log file for compliance verification.
"""

from __future__ import annotations
import os
import json
import time
import hashlib
from typing import List, Dict, Any, Optional

from virtu_code.config import ScraperConfig
from virtu_code.scraper.rate_limiter import TokenBucketRateLimiter, CircuitBreaker
from virtu_code.scraper.filters import ThreeLevelRepositoryFilter


class CompliantGitHubCrawler:
    """Production GitHub repository ingestion and screening service."""

    def __init__(self, config: Optional[ScraperConfig] = None) -> None:
        self.config = config or ScraperConfig()
        self.rate_limiter = TokenBucketRateLimiter(self.config.max_requests_per_minute)
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=self.config.circuit_breaker_failures,
            cooldown_seconds=self.config.circuit_breaker_cooldown_seconds,
            max_retries=self.config.max_retries,
            backoff_factor=self.config.backoff_factor,
        )
        self.filter = ThreeLevelRepositoryFilter(self.config)
        self.last_audit_hash = "GENESIS_ROOT_HASH_0000000000000000000000000000000000000000"

        os.makedirs(self.config.output_dir, exist_ok=True)
        os.makedirs(os.path.dirname(os.path.abspath(self.config.audit_log_path)), exist_ok=True)

    def _log_audit_entry(self, entry: Dict[str, Any]) -> str:
        """Write immutable hash-chained audit record."""
        entry["timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        entry["previous_hash"] = self.last_audit_hash

        serialized = json.dumps(entry, sort_keys=True)
        current_hash = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        entry["current_hash"] = current_hash
        self.last_audit_hash = current_hash

        with open(self.config.audit_log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

        return current_hash

    def process_candidate_repositories(
        self, candidates: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Screen list of candidate repositories through rate-limited 3-level filter."""
        approved_repositories: List[Dict[str, Any]] = []

        for candidate in candidates:
            # Enforce rate limiter
            self.rate_limiter.acquire()

            # Execute evaluation under circuit breaker
            def _action() -> Dict[str, Any]:
                return self.filter.evaluate(candidate)

            verdict = self.circuit_breaker.execute_with_resilience(_action)

            # Log auditable decision
            audit_record = {
                "event": "REPOSITORY_SCREENING",
                "repo_name": candidate.get("full_name"),
                "license_spdx": candidate.get("license_spdx"),
                "stars": candidate.get("stars"),
                "verdict": verdict["overall_verdict"],
                "stage": verdict["stage"],
                "reason": verdict["reason"],
            }
            self._log_audit_entry(audit_record)

            if verdict["overall_verdict"] == "APPROVED":
                approved_repositories.append(candidate)

        # Output manifest
        manifest_path = os.path.join(self.config.output_dir, "compliant_repositories.json")
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "total_candidates": len(candidates),
                    "approved_count": len(approved_repositories),
                    "latest_audit_hash": self.last_audit_hash,
                    "repositories": approved_repositories,
                },
                f,
                indent=2,
            )

        print(
            f"[Scraper] Screened {len(candidates)} repositories. "
            f"Approved: {len(approved_repositories)}. Manifest: {manifest_path}"
        )
        return approved_repositories
