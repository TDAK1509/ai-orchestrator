---
name: code-review-full
description: Full review of the current branch against main — runs the claim-check and the security/performance-leak review together. Use when the user asks for a full code review, a combined review, or just "review this branch" without specifying which kind.
---

# Code review: full

Run both reviews of the current branch against `main`, then combine the
results. This is the index skill; it does not duplicate their checks.

## Steps

1. Load and run `code-review-do-what-it-claims` — does the diff do what it
   claims.
2. Load and run `code-review-leaks` — security and performance leaks in the
   changed files.
3. Both skills scope themselves to `git diff --name-only main...HEAD`. Do not
   widen or narrow that scope between the two.

## Report

Two sections, one per skill, each in that skill's own report format. End with
one line: overall verdict (ship / fix first / needs discussion).
