# Virtu Foundation Model x Context-Mode Optimization Benchmark Report

> **Framework**: [mksglu/context-mode](https://github.com/mksglu/context-mode)
> **Generated**: 2026-10-29 18:15:14
> **Health Status**: `HEALTHY` | **FTS5 Full-Text Search**: `ACTIVE`

## 1. Executive Summary

Context Mode solves the critical problem of context window bloat and compaction amnesia in AI coding agents. By executing heavy tool operations in sandboxed subprocesses and filtering raw text before passing it back into the model context, it achieves token savings of up to **98%**, while preserving session milestones in SQLite FTS5 for zero-loss recovery across compactions.

## 2. Benchmark Compression Results

| Operation / Scenario | Raw Size | Filtered Size | Lines Reduction | Token Savings (%) | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Large Build / Log Output** | `21,047 bytes` | `940 bytes` | `503 -> 22` | **95.53%** | PASS |
| **Custom In-Sandbox Script** | `21,047 bytes` | `156 bytes` | `503 -> 3` | **99.26%** | PASS |
| **Large NC G-Code File (5-Axis)** | `31,977 bytes` | `482 bytes` | `1208 -> 22` | **98.49%** | PASS |

## 3. Session Continuity & Compaction Survival (SQLite FTS5)

| Test Query | Target Milestone | Recall Score (BM25) | Result | Status |
| :--- | :--- | :--- | :--- | :--- |
| `"hydraulic punch"` | Cr12MoV Hydraulic Punch Sleeve | Rank: `-1.82` | Recalled: `Cr12MoV Hydraulic Punch Sleeve Dimensions` | PASS |
| `"roughing cycle"` | FANUC 0i-TF Turning Macro | Rank: `-1.77` | Recalled: `FANUC 0i-TF Turning Macro G71 Cycle` | PASS |

## 4. Cumulative Context Savings Telemetry

- **Cumulative Raw Data Processed**: 74,071 bytes
- **Cumulative Filtered Context Delivered**: 1,578 bytes
- **Total Bytes Intercepted from Context**: **72,493 bytes**
- **Overall Context Token Savings**: **97.87%**
- **Estimated Context Tokens Conserved**: **18,123 tokens**

## 5. WorkBuddy Bridge REST API Endpoints

| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `/v1/context-mode/dashboard` | `GET` | Retrieve cumulative savings telemetry and session continuity metrics |
| `/v1/context-mode/doctor` | `GET` | Check health of subprocess sandboxes and SQLite FTS5 database |
| `/v1/context-mode/execute` | `POST` | Execute shell/CLI command in sandboxed subprocess with output filtering |
| `/v1/context-mode/file/filter` | `POST` | Parse and compress large files out of core context |
| `/v1/context-mode/session/event` | `POST` | Record critical milestone or file edit into SQLite continuity store |
| `/v1/context-mode/session/search`| `POST` | Query historical milestones using FTS5 BM25 search |
