"""Unit tests for GitHub Scraper and 3-Level Auditable Filter."""

import os
import json
import tempfile
from virtu_code.config import ScraperConfig
from virtu_code.scraper.rate_limiter import TokenBucketRateLimiter, CircuitBreaker
from virtu_code.scraper.filters import ThreeLevelRepositoryFilter
from virtu_code.scraper.crawler import CompliantGitHubCrawler


def test_token_bucket_rate_limiter() -> None:
    limiter = TokenBucketRateLimiter(max_per_minute=600)  # 10 req/s for fast test
    # Should acquire without blocking when full
    for _ in range(5):
        limiter.acquire()
    assert limiter.tokens < 600.0


def test_circuit_breaker_resilience() -> None:
    breaker = CircuitBreaker(failure_threshold=2, cooldown_seconds=0.1, max_retries=2)
    attempts = 0

    def fail_twice_then_succeed() -> str:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise ValueError("Transient network timeout")
        return "SUCCESS"

    result = breaker.execute_with_resilience(fail_twice_then_succeed)
    assert result == "SUCCESS"
    assert attempts == 3
    assert breaker.state == "CLOSED"


def test_three_level_filter_level_1_license() -> None:
    cfg = ScraperConfig()
    filter_engine = ThreeLevelRepositoryFilter(cfg)

    # MIT -> Approved
    res, msg = filter_engine.evaluate_level_1_license({"license_spdx": "MIT"})
    assert res is True
    assert "PASSED" in msg

    # Apache-2.0 -> Approved
    res, msg = filter_engine.evaluate_level_1_license({"license_spdx": "Apache-2.0"})
    assert res is True

    # GPL-3.0 -> Strictly Rejected
    res, msg = filter_engine.evaluate_level_1_license({"license_spdx": "GPL-3.0"})
    assert res is False
    assert "REJECTED_L1_COPYLEFT" in msg

    # AGPL-3.0 -> Strictly Rejected
    res, msg = filter_engine.evaluate_level_1_license({"license_spdx": "AGPL-3.0"})
    assert res is False


def test_three_level_filter_level_2_activity() -> None:
    cfg = ScraperConfig(min_stars=50, max_days_since_last_commit=180)
    filter_engine = ThreeLevelRepositoryFilter(cfg)

    # Active repo
    active_repo = {
        "stars": 500,
        "days_since_last_commit": 30,
        "contributors_count": 10,
        "avg_issue_resolution_days": 5,
    }
    res, _ = filter_engine.evaluate_level_2_activity(active_repo)
    assert res is True

    # Stale repo (>180 days)
    stale_repo = {
        "stars": 500,
        "days_since_last_commit": 200,
        "contributors_count": 10,
        "avg_issue_resolution_days": 5,
    }
    res, msg = filter_engine.evaluate_level_2_activity(stale_repo)
    assert res is False
    assert "REJECTED_L2_INACTIVE" in msg


def test_three_level_filter_level_3_quality() -> None:
    cfg = ScraperConfig(min_business_loc=500)
    filter_engine = ThreeLevelRepositoryFilter(cfg)

    # Good structure
    good_repo = {
        "business_loc": 2500,
        "structure_tree": ["src", "test", "README.md"],
        "is_fork": False,
    }
    res, _ = filter_engine.evaluate_level_3_quality(good_repo)
    assert res is True

    # Low LOC / empty repo
    empty_repo = {
        "business_loc": 20,
        "structure_tree": ["README.md"],
        "is_fork": False,
    }
    res, msg = filter_engine.evaluate_level_3_quality(empty_repo)
    assert res is False
    assert "LOW_LOC" in msg


def test_crawler_audit_hash_chaining() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        audit_path = os.path.join(tmp_dir, "test_audit.jsonl")
        cfg = ScraperConfig(output_dir=tmp_dir, audit_log_path=audit_path)
        crawler = CompliantGitHubCrawler(cfg)

        sample = [
            {
                "full_name": "test/repo1",
                "license_spdx": "MIT",
                "stars": 100,
                "days_since_last_commit": 10,
                "contributors_count": 5,
                "avg_issue_resolution_days": 3,
                "business_loc": 1000,
                "structure_tree": ["src", "README.md"],
            },
            {
                "full_name": "test/repo2",
                "license_spdx": "GPL-3.0",
                "stars": 200,
                "days_since_last_commit": 10,
                "contributors_count": 5,
                "avg_issue_resolution_days": 3,
                "business_loc": 1000,
                "structure_tree": ["src", "README.md"],
            },
        ]

        approved = crawler.process_candidate_repositories(sample)
        assert len(approved) == 1

        # Check audit log entries
        with open(audit_path, "r", encoding="utf-8") as f:
            lines = [json.loads(line) for line in f]

        assert len(lines) == 2
        # Check hash chaining
        assert lines[0]["previous_hash"] == "GENESIS_ROOT_HASH_0000000000000000000000000000000000000000"
        assert lines[1]["previous_hash"] == lines[0]["current_hash"]
