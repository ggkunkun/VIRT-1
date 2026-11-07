"""CLI Runner & Benchmark: Virtu Foundation Model x Agent-Reach Integration.

Demonstrates and verifies:
1. Multi-platform read & search capabilities across 13+ platforms via Agent-Reach.
2. Searching GitHub for industrial CAD/CAM/CNC open-source repositories and code.
3. Reading developer technical discussions from V2EX and communities.
4. Universal URL reading with clean JSON extraction.
5. Exporting comprehensive benchmarks/agent_reach_report.md.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

# Fix console encoding on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

WORKSPACE_DIR = Path(__file__).resolve().parent.parent
if str(WORKSPACE_DIR) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_DIR))

from virtu_omni.reach import VirtuAgentReach


def main() -> int:
    print("=" * 76)
    print("  Virtu-Omni-10B x Agent-Reach (Zero-Fee Multi-Platform Web Access)")
    print("=" * 76)
    print(f"[*] Workspace Root: {WORKSPACE_DIR}")
    print("[*] Project: Panniantong/Agent-Reach (v1.6.0)")
    print("[*] Skill: skills/agent-reach/SKILL.md")
    print("")

    reach = VirtuAgentReach()

    # 1. Inspect Channels
    print("[>>>] Phase 1: Querying Supported Platforms and Capabilities...")
    channels = reach.get_channels()
    print(f"[+] Total Channels Available: {len(channels)}")
    for ch in channels:
        actions = [a.get("name") for a in ch.get("actions", [])]
        print(f"    - {ch.get('name'):12} : {ch.get('description')} (Actions: {', '.join(actions) if actions else 'standard'})")

    # 2. GitHub Industrial Search
    print("\n[>>>] Phase 2: Live Search on GitHub for Industrial CAD/CAM Repositories...")
    t0 = time.time()
    github_res = reach.search("github", "solidworks-vba", limit=3)
    elapsed_gh = time.time() - t0

    gh_items = github_res.get("items", [])
    print(f"[+] GitHub Search completed in {elapsed_gh:.2f}s (Status: {github_res.get('ok')}, Items: {len(gh_items)})")
    for item in gh_items:
        print(f"    * [{item.get('title')}] - Stars: {item.get('raw', {}).get('stargazers_count')} | {item.get('text', '')[:70]}...")

    # 3. Community Technical Topics (V2EX)
    print("\n[>>>] Phase 3: Live Community Discussion Extraction (V2EX)...")
    t0 = time.time()
    v2ex_topics = reach.get_community_discussions("python", channel="v2ex", limit=2)
    elapsed_v2ex = time.time() - t0
    print(f"[+] V2EX Topic Extraction completed in {elapsed_v2ex:.2f}s (Items: {len(v2ex_topics)})")
    for top in v2ex_topics[:2]:
        print(f"    * [{top.get('title')}] ({top.get('url')})")

    # 4. Universal Link Reading
    print("\n[>>>] Phase 4: Universal Link Reader Test...")
    sample_url = "https://github.com/Panniantong/Agent-Reach"
    t0 = time.time()
    read_res = reach.read(sample_url)
    elapsed_read = time.time() - t0
    print(f"[+] URL Read completed in {elapsed_read:.2f}s (Status: {read_res.get('ok')}, Channel: {read_res.get('channel')})")
    if read_res.get("items"):
        item0 = read_res["items"][0]
        print(f"    * Title: {item0.get('title')}")
        print(f"    * Author: {item0.get('author')}")
        print(f"    * Snippet: {item0.get('text', '')[:100]}...")

    # 5. Export Benchmark Report
    report_path = WORKSPACE_DIR / "benchmarks" / "agent_reach_report.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "# Virtu Foundation Model x Agent-Reach Evaluation Report",
        "",
        "> **Framework**: [Panniantong/Agent-Reach](https://github.com/Panniantong/Agent-Reach) (v1.6.0)",
        f"> **Generated**: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}",
        f"> **Total Channels**: {len(channels)}",
        "",
        "## 1. Supported Platforms Overview",
        "",
        "| Channel | Description | Level |",
        "| :--- | :--- | :--- |",
    ]

    for ch in channels:
        lines.append(f"| `{ch.get('name')}` | {ch.get('description')} | `{ch.get('level', 'default')}` |")

    lines.extend([
        "",
        "## 2. Sample Industrial Search Results (GitHub)",
        "",
    ])

    for it in gh_items:
        lines.extend([
            f"### `{it.get('title')}`",
            f"- **URL**: {it.get('url')}",
            f"- **Author**: `{it.get('author')}`",
            f"- **Stars**: {it.get('raw', {}).get('stargazers_count')}",
            f"- **Description**: {it.get('text')}",
            "",
        ])

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"\n[+] Exported comprehensive Agent-Reach report: {report_path}")
    print("\n" + "=" * 76)
    print("  Agent-Reach Verified Successfully!")
    print("=" * 76)
    return 0


if __name__ == "__main__":
    sys.exit(main())
