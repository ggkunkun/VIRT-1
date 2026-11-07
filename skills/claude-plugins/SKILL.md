---
name: claude-plugins
description: Discover, install, and execute official Anthropic Claude Code plugins, slash commands (/code-review, /feature-dev, /commit-commands), LSP servers, subagent swarms, and external integrations (GitHub, Playwright, Firebase, Linear).
metadata:
  catalog_total: 316
  local_plugins: 54
  commands_count: 18
---

# Claude Code Official Plugins (anthropics/claude-plugins-official)

Provides the Virtu Foundation Model with direct access to the official Anthropic Claude Code plugin marketplace and ecosystem.

## Capabilities

1. **Marketplace Discovery & Catalog Indexing**:
   - Query across 316 official Anthropic and verified third-party partner plugins.
   - Filter by categories: LSP (`clangd-lsp`, `pyright-lsp`, `rust-analyzer-lsp`, `typescript-lsp`), Security (`claude-security`, `security-guidance`), Code Quality (`code-review`, `code-simplifier`, `code-modernization`), Workflow Automation (`commit-commands`, `feature-dev`, `project-artifact`).
2. **Slash Command Execution**:
   - `/code-review`: Multi-agent code review for pull requests with confidence scoring.
   - `/feature-dev`: End-to-end feature development lifecycle and task decomposition.
   - `/commit`: Intelligent atomic git commit message synthesis.
   - `/commit-push-pr`: Autonomous commit, remote push, and GitHub PR creation.
   - `/modernize-assess` / `/modernize-harden`: Automated legacy codebase modernizer.
   - `/new-sdk-app`: Scaffold full-stack Claude Agent SDK applications.
3. **Model Context Protocol (MCP) Integration**:
   - Dynamically load verified MCP server definitions from `.mcp.json` (Playwright browser automation, GitHub repository management, GitLab CI/CD, Firebase, Discord, Telegram, Linear, Asana).
4. **Specialized Subagents**:
   - Subagent role definitions in `agents/*.md` for automated patching, security scanning, and test verification.

## Usage in Virtu Agent Team

Agents invoke `virtu_omni.claude_plugins.VirtuClaudePlugins`:
```python
from virtu_omni.claude_plugins import VirtuClaudePlugins

plugins = VirtuClaudePlugins.get_instance()
# Search marketplace
hits = plugins.search_marketplace("review")

# Execute slash command
res = plugins.execute_command("/code-review", context="Pull Request #42 changes")
```
