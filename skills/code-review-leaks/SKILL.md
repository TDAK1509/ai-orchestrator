---
name: code-review-leaks
description: Review the current branch's diff against main for security and performance leaks — only in the changed files. Use when the user asks to review a PR, review changes, check for security issues, or check for performance regressions.
---

# Code review: security and performance leaks

Compare the current branch against `main`. Examine only the changed files.
Look for leaks, not style.

## Steps

1. List changed files only:
   ```bash
   git diff --name-only main...HEAD
   ```
2. Read the full diff for those files:
   ```bash
   git diff main...HEAD -- <file> ...
   ```
   Do not scan files outside this list.
3. Check each changed file for security leaks:
   - Secrets, keys, tokens, or credentials committed in the diff.
   - User input reaching a query, shell command, file path, or template without
     escaping or parameterization (SQLi, command injection, path traversal, XSS).
   - New logging or error output that includes secrets, tokens, PII, or full
     request bodies.
   - Auth or permission checks removed, weakened, or skipped on a code path that
     had one before.
   - New network calls or dependencies with an unvalidated or attacker-controlled
     destination (SSRF).
4. Check each changed file for performance leaks:
   - A resource opened (file, socket, DB connection, lock) with no matching
     close/release on every path, including error paths.
   - A query or loop newly added inside another loop (N+1).
   - An unbounded cache, list, or buffer that grows with request volume and is
     never evicted.
   - A blocking call added on a hot or latency-sensitive path.
5. Ignore correctness-vs-claim and naming/style — that is a different skill's job.

## Report

List each finding as: file:line, one-line description, why it is a leak. If
nothing found, say so plainly. Do not propose fixes unless asked.
