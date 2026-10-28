"""Executable runner for standardized source code preprocessing pipeline."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from virtu_code.config import PreprocessingConfig  # noqa: E402
from virtu_code.preprocessing.pipeline import CodePreprocessingPipeline  # noqa: E402


def generate_curated_raw_corpus() -> list[dict]:
    """Generate representative multi-language source files and non-code/binary artifacts."""
    return [
        {
            "file_path": "src/main/python/auth_service.py",
            "repo_url": "https://github.com/psf/requests",
            "license_spdx": "Apache-2.0",
            "raw_content": (
                "# Authentication Service Implementation\n"
                "# Copyright (c) 2026 Author\n\n\n\n"
                "class AuthService:\n"
                "\tdef __init__(self, token: str):\n"
                "\t\tself.token = token\n\n"
                "\tdef verify_token(self) -> bool:\n"
                "\t\t# Verify validity\n"
                "\t\treturn len(self.token) > 16\n"
            ),
        },
        {
            "file_path": "src/main/java/com/enterprise/Application.java",
            "repo_url": "https://github.com/spring-projects/spring-boot",
            "license_spdx": "Apache-2.0",
            "raw_content": (
                "package com.enterprise;\n\n"
                "/** Enterprise Application Entrypoint */\n"
                "public class Application {\n"
                "\tpublic static void main(String[] args) {\n"
                "\t\t// Boot service\n"
                "\t\tSystem.out.println(\"Application Started\");\n"
                "\t}\n"
                "}\n"
            ),
        },
        {
            "file_path": "tokio/src/runtime.rs",
            "repo_url": "https://github.com/tokio-rs/tokio",
            "license_spdx": "MIT",
            "raw_content": (
                "// Tokio Async Runtime\n"
                "pub struct Runtime {\n"
                "    workers: usize,\n"
                "}\n\n"
                "impl Runtime {\n"
                "    pub fn new(workers: usize) -> Self {\n"
                "        Runtime { workers }\n"
                "    }\n"
                "}\n"
            ),
        },
        {
            "file_path": "pkg/net/router.go",
            "repo_url": "https://github.com/golang/tools",
            "license_spdx": "BSD-3-Clause",
            "raw_content": (
                "package net\n\n"
                "// Router handles incoming requests\n"
                "type Router struct {\n"
                "\troutes map[string]string\n"
                "}\n\n"
                "func NewRouter() *Router {\n"
                "\treturn &Router{routes: make(map[string]string)}\n"
                "}\n"
            ),
        },
        {
            "file_path": "src/server/handler.ts",
            "repo_url": "https://github.com/expressjs/express",
            "license_spdx": "MIT",
            "raw_content": (
                "// Server Request Handler\n"
                "export interface RequestPayload {\n"
                "    id: string;\n"
                "    timestamp: number;\n"
                "}\n\n"
                "export function handle(payload: RequestPayload): boolean {\n"
                "    /* Check timestamp */\n"
                "    return payload.timestamp > 0;\n"
                "}\n"
            ),
        },
        {
            "file_path": "include/math_utils.hpp",
            "repo_url": "https://github.com/example/cpp-math",
            "license_spdx": "MIT",
            "raw_content": (
                "#pragma once\n"
                "// Fast Vector Computations\n"
                "namespace math {\n"
                "    inline double dot_product(double a, double b) {\n"
                "        return a * b;\n"
                "    }\n"
                "}\n"
            ),
        },
        # Duplicate of auth_service.py to test deduplication
        {
            "file_path": "mirror/auth_service_copy.py",
            "repo_url": "https://github.com/example/fork",
            "license_spdx": "MIT",
            "raw_content": (
                "# Authentication Service Implementation\n"
                "# Copyright (c) 2026 Author\n\n\n\n"
                "class AuthService:\n"
                "\tdef __init__(self, token: str):\n"
                "\t\tself.token = token\n\n"
                "\tdef verify_token(self) -> bool:\n"
                "\t\t# Verify validity\n"
                "\t\treturn len(self.token) > 16\n"
            ),
        },
        # Binary artifact to be filtered
        {
            "file_path": "build/target/classes/Application.class",
            "repo_url": "https://github.com/spring-projects/spring-boot",
            "license_spdx": "Apache-2.0",
            "raw_content": b"\xca\xfe\xba\xbe\x00\x00\x00\x34\x00\x10",
        },
        # Vendor dependency to be filtered
        {
            "file_path": "node_modules/lodash/index.js",
            "repo_url": "https://github.com/expressjs/express",
            "license_spdx": "MIT",
            "raw_content": "module.exports = {};",
        },
        # Documentation markdown to be filtered
        {
            "file_path": "docs/architecture.md",
            "repo_url": "https://github.com/psf/requests",
            "license_spdx": "Apache-2.0",
            "raw_content": "# Architecture Guide\nDetails here...",
        },
    ]


def main() -> None:
    print("================================================================")
    print("  VirtuCode: Standardized Source Code Preprocessing Pipeline")
    print("================================================================")

    config = PreprocessingConfig()
    pipeline = CodePreprocessingPipeline(config)

    raw_records = generate_curated_raw_corpus()
    results = pipeline.process_raw_files(raw_records)

    report_path = os.path.join("benchmarks", "preprocessing_report.md")
    pipeline.export_report(results, report_path)

    stats = results["stats"]
    print("\n[Preprocessing Execution Summary]")
    print(f"- Total Files Examined: {stats['total_files_examined']}")
    print(f"- Binaries & Dependencies Filtered: {stats['binary_or_dependency_filtered']}")
    print(f"- Duplicate Files Filtered: {stats['duplicate_files_filtered']}")
    print(f"- Clean Valid Source Code Files: {stats['valid_clean_files']}")
    print(f"- Cleaned Dataset Saved to: {results['corpus_path']}")
    print(f"- Metadata Index Saved to: {results['metadata_index_path']}")
    print(f"- Validation Report Generated at: {report_path}")


if __name__ == "__main__":
    main()
