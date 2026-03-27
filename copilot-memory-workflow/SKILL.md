---
name: copilot-memory-workflow
description: Organizes durable knowledge across VS Code memory scopes and Copilot Memory, helping the agent retain repository facts, recurring workflows, and validated findings without storing secrets.
---

# Copilot Memory Workflow Skill

Use this skill when the agent should remember information that will make future work materially better.

This skill is based on the official VS Code memory tool and Copilot Memory guidance:

- VS Code local memory has three scopes: user, repository, and session.
- Copilot Memory is repository-scoped, cross-agent, GitHub-hosted, validated before use, and automatically expires after 28 days.

## What to store where

### User memory (`/memories/`)

Store stable personal preferences that apply across workspaces.

Examples:

- preferred coding style
- preferred commit style
- preferred test/debug workflow
- frequently used local commands

### Repository memory (`/memories/repo/`)

Store facts about the current codebase that future tasks will benefit from.

Examples:

- auth endpoints and non-secret login flow details
- seed account usernames or role names
- stable browser selectors for login and navigation
- location of reusable storage-state files
- design system conventions
- screenshot baseline locations
- important file synchronization rules
- build, run, and validation commands

### Session memory (`/memories/session/`)

Store temporary plans and work-in-progress notes for the current conversation only.

Examples:

- multi-step task plans
- current hypothesis while debugging
- temporary selector experiments

## What must never be stored

Do **not** store secrets or impersonation material in memory files.

Never store:

- passwords
- API keys
- bearer tokens
- cookies
- Playwright or browser storage-state contents
- private personal data

If a workflow needs secrets, store only the **reference pattern**, such as the environment variable name or the auth file path.

## When to remember something

Store information only when it is likely to be reused and would save real effort later.

Strong candidates:

- a login flow that was hard to discover
- stable selectors for a protected app
- recurring design constraints for a product
- a repo rule that caused bugs when forgotten
- a reliable seed-user workflow for auth simulation

Weak candidates:

- one-off outputs
- transient errors
- secrets
- noisy logs
- facts already obvious from a single filename

## How this works with Copilot Memory

If Copilot Memory is enabled, Copilot can also build repository-scoped cross-agent memory that is shared across supported Copilot surfaces such as coding agent, code review, and CLI.

Key behavior:

- repository-scoped only
- verified against citations before use
- shared across supported Copilot agents
- automatically expires after 28 days

Use the local VS Code memory tool for immediate, explicit memory management in chat. Use Copilot Memory for validated repository knowledge that should improve future agent work across surfaces.

## Recommended practice

After a successful task, remember only the smallest durable fact that would help next time.

Good examples:

- "Remember that admin login for this repo uses `/auth/login`, username field `email`, and success is confirmed by `nav[aria-label=main]`."
- "Remember that visual homepage captures should use a 1440x900 viewport and hide the cookie banner selector `.cookie-banner`."
- "Remember that the seeded admin browser state is stored at `.auth/seed-admin.json`, but do not store the cookies or file contents."
