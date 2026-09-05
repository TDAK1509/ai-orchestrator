---
name: planning
description: The rules that bind every plan you write - smallest scope that reaches the goal, and steps sized as small, working, revertible PRs. Use whenever you write an implementation plan, before you start a multi-step task, or when the user asks how to scope or break up work.
---

# Planning

Two rules bind every plan. They are one habit, not two checklists.

| Rule | Skill |
| --- | --- |
| The plan touches only what the goal needs | `minimal-scope-plan` |
| The plan ships as small, working, revertible PRs | `increments-plan` |

Load the skill itself when a rule bites. This page is the index, not the
content.

## Not optional

Both are required rules. Neither is a style preference.

No hook enforces either, so nothing stops you from skipping them. That makes
them easier to drop under time pressure, not less binding.

## They are the same rule

Each one is scope discipline, applied on a different axis.

- Minimal scope says: touch only the files the goal needs, this PR.
- Increments say: split the goal into PRs, each one a minimal, working step.

A plan that fails one usually fails the other. A plan that touches
out-of-scope files to "set up for later" is also a plan with a fragment step
that ships nothing on its own.

## The order to apply them

1. **Write the goal in one sentence.** Not the solution — the outcome. If you
   cannot say it in one sentence, you have more than one task.
2. **List the smallest set of files a first working step needs.** Read them
   before you claim anything about how they behave.
3. **Split the goal into steps.** Each step is a PR: something true in
   production when it merges, provable without reading a later PR, revertible
   on its own.
4. **Recheck scope per step.** A step's file list is itself a minimal-scope
   question — apply the three widen reasons per step, not once for the whole
   plan.

## Before you finish

Read the plan and ask:

- Does every named file trace back to the goal sentence, or one of the three
  widen reasons?
- Can production stop safely after any single step?
- Can any single step be reverted without touching the others?
- Is any step only describable with "and"? Split it.

Four clean answers and the plan is ready.

## What this does not cover

Whether the code you write for each step is clean — see
`clean-code-implementation`. Planning decides what ships and in what order;
implementation decides how each piece is written.
