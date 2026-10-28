"""Executable runner for compliant GitHub crawler and 3-level filtering pipeline."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from virtu_code.config import ScraperConfig  # noqa: E402
from virtu_code.scraper.crawler import CompliantGitHubCrawler  # noqa: E402


def get_curated_seed_repositories() -> list[dict]:
    """Curated seed candidates representing diverse licenses, activities, and structures."""
    return [
        {
            "full_name": "psf/requests",
            "url": "https://github.com/psf/requests",
            "license_spdx": "Apache-2.0",
            "license_name": "Apache License 2.0",
            "stars": 52000,
            "days_since_last_commit": 12,
            "contributors_count": 850,
            "avg_issue_resolution_days": 4,
            "business_loc": 28400,
            "structure_tree": ["src", "tests", "README.md", "setup.py"],
            "is_fork": False,
            "primary_language": "Python",
        },
        {
            "full_name": "spring-projects/spring-boot",
            "url": "https://github.com/spring-projects/spring-boot",
            "license_spdx": "Apache-2.0",
            "license_name": "Apache License 2.0",
            "stars": 74000,
            "days_since_last_commit": 2,
            "contributors_count": 1200,
            "avg_issue_resolution_days": 3,
            "business_loc": 450000,
            "structure_tree": ["src", "test", "README.md", "pom.xml"],
            "is_fork": False,
            "primary_language": "Java",
        },
        {
            "full_name": "tokio-rs/tokio",
            "url": "https://github.com/tokio-rs/tokio",
            "license_spdx": "MIT",
            "license_name": "MIT License",
            "stars": 28000,
            "days_since_last_commit": 5,
            "contributors_count": 480,
            "avg_issue_resolution_days": 6,
            "business_loc": 85000,
            "structure_tree": ["tokio/src", "tests", "README.md", "Cargo.toml"],
            "is_fork": False,
            "primary_language": "Rust",
        },
        {
            "full_name": "golang/tools",
            "url": "https://github.com/golang/tools",
            "license_spdx": "BSD-3-Clause",
            "license_name": "BSD 3-Clause License",
            "stars": 12000,
            "days_since_last_commit": 8,
            "contributors_count": 320,
            "avg_issue_resolution_days": 7,
            "business_loc": 120000,
            "structure_tree": ["go/src", "testdata", "README.md", "go.mod"],
            "is_fork": False,
            "primary_language": "Go",
        },
        {
            "full_name": "expressjs/express",
            "url": "https://github.com/expressjs/express",
            "license_spdx": "MIT",
            "license_name": "MIT License",
            "stars": 64000,
            "days_since_last_commit": 20,
            "contributors_count": 310,
            "avg_issue_resolution_days": 10,
            "business_loc": 18000,
            "structure_tree": ["lib", "test", "README.md", "package.json"],
            "is_fork": False,
            "primary_language": "JavaScript",
        },
        # Candidate to be filtered out by Level 1 (GPL Copyleft)
        {
            "full_name": "torvalds/linux",
            "url": "https://github.com/torvalds/linux",
            "license_spdx": "GPL-2.0",
            "license_name": "GNU General Public License v2.0",
            "stars": 180000,
            "days_since_last_commit": 1,
            "contributors_count": 15000,
            "avg_issue_resolution_days": 5,
            "business_loc": 32000000,
            "structure_tree": ["kernel", "include", "README"],
            "is_fork": False,
            "primary_language": "C",
        },
        # Candidate to be filtered out by Level 2 (Stale / Inactive > 180 days)
        {
            "full_name": "stale-org/abandoned-project",
            "url": "https://github.com/stale-org/abandoned-project",
            "license_spdx": "MIT",
            "license_name": "MIT License",
            "stars": 120,
            "days_since_last_commit": 360,
            "contributors_count": 4,
            "avg_issue_resolution_days": 60,
            "business_loc": 3200,
            "structure_tree": ["src", "test", "README.md"],
            "is_fork": False,
            "primary_language": "Python",
        },
        # Candidate to be filtered out by Level 3 (Empty / No LOC)
        {
            "full_name": "placeholder/empty-repo",
            "url": "https://github.com/placeholder/empty-repo",
            "license_spdx": "MIT",
            "license_name": "MIT License",
            "stars": 80,
            "days_since_last_commit": 10,
            "contributors_count": 3,
            "avg_issue_resolution_days": 2,
            "business_loc": 45,
            "structure_tree": ["README.md"],
            "is_fork": False,
            "primary_language": "Python",
        },
    ]


def main() -> None:
    print("================================================================")
    print("  VirtuCode: GitHub Crawler & 3-Level Auditable Screening Engine")
    print("================================================================")

    config = ScraperConfig()
    crawler = CompliantGitHubCrawler(config)

    candidates = get_curated_seed_repositories()
    approved = crawler.process_candidate_repositories(candidates)

    print("\n[Execution Summary]")
    print(f"- Total Candidate Repositories Screened: {len(candidates)}")
    print(f"- Approved Compliant Repositories: {len(approved)}")
    print(f"- Audit Trail Appended to: {config.audit_log_path}")
    print("- Compliant Repositories List Saved to: data/raw/compliant_repositories.json")


if __name__ == "__main__":
    main()
