---
name: increments-plan
description: Plan a task as a sequence of small, single-responsibility PRs, each one a working, testable, revertible step toward an outcome. Use when planning or scoping multi-step work, when a task looks too big for one PR, when the user asks for a phased or incremental plan, or when the user asks how to break work into pull requests.
---

# Increments plan

A plan is a sequence of PRs, not a design document. State the outcome you want,
not the solution you have already decided on. Let the steps discover the
solution.

## Not optional

Every step in the plan is a PR. Every PR ships something that works. A step
that only sets up for a later step, with nothing observable on its own, is not
a step — merge it into the step that makes it real.

## Start from the outcome, not the solution

Write one sentence: what should be true when this is done. Not how it will be
built.

- "Users can export their data as CSV" is an outcome.
- "Add an `ExportService` with a `CsvFormatter` strategy" is a solution you
  have not tested yet. Do not write this in the plan.

A detailed upfront design is a guess about code you have not changed yet. The
PRs are how you find out if the guess holds. If step 2 reveals step 4 was
wrong, that is the plan working, not the plan failing.

## Each PR is a real step, not a fragment

For every PR in the plan, answer:

- **What can a reviewer see work?** A passing test, a new path a user can hit,
  a flag they can flip, a script they can run. "Trust me, step 4 uses this" is
  not an answer.
- **What breaks if this ships alone and nothing after it ever lands?** The
  answer must be "nothing in production." A half-built abstraction with no
  caller is not safe to stop at.
- **How does someone revert just this PR?** If reverting it requires also
  reverting a later PR, they are not two PRs — merge them or reorder them.

## Order steps so production never breaks

- Land the parts that do nothing yet before the parts that turn them on.
  Behind a flag, behind a branch never taken, behind a caller that does not
  exist yet — all fine, as long as the PR itself is inert until wired up.
- Do the risky or uncertain part early, in its smallest form, so a wrong
  guess is cheap to find and cheap to revert. Do not save the riskiest step
  for last.
- Never write a step that depends on a later step to be correct. Each step
  depends only on the ones before it.

## Size each PR down

- One responsibility per PR. If describing a step needs "and", it is two
  steps.
- Prefer more, smaller PRs over fewer, larger ones. A PR too small to review
  is rare; a PR too large to review is common.
- A step that touches many files for one mechanical reason (a rename, a
  type change propagating outward) can stay one PR — the risk is the reason
  it exists, not its size in lines.

## Write the plan

For each PR, state:

1. **Outcome** — one sentence, what becomes true after this PR merges.
2. **Proof** — how a reviewer or a test confirms it, without reading the next
   PR.
3. **Revert cost** — what reverting this PR alone does to production: nothing,
   or name the one thing.

Do not write implementation detail beyond what the outcome requires. If a step
needs a design decision you have not made, say "decide: X" instead of guessing
an answer.

## Before you finish

- Does every step ship something true in production, not just true in the
  repo?
- Can you stop after any step and leave production working?
- Can you revert any single step without touching the others?
- Is any step describable only with "and"? Split it.

Three "yes" and one "no unsplit step" and the plan is ready.
