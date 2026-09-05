---
name: minimal-scope-plan
description: Plan a task as the smallest change that reaches the goal, and decide when touching an out-of-scope file is justified. Use when planning or scoping work, when writing an implementation plan, when a fix seems to need edits across many files, when tempted to refactor or clean up code the task did not ask about, when reasoning about how existing code behaves without having read it, or when the user asks how large a change should be. Every claim in a plan must come from code you read, never from a comment, a docstring or a name.
---

# Minimal scope plan

Reach the goal with as little work as possible. Every file you open that the
goal did not name is a cost: more review, more risk, more to revert.

## Not optional

This rule is required. It is not a style preference.

No hook enforces it, so nothing will stop you from skipping it. That makes it
easier to drop under time pressure, not less binding.

## Read the code first

A plan is a claim about code that already exists. Every claim in it must come
from a file you opened in this session. Nothing else counts.

- Not what the function name suggests.
- Not what the docstring says it returns.
- Not what the comment above it says it guards against.
- Not what a similar codebase did.
- Not what you remember from earlier in this session, once the file has changed.

**Read the body.** A comment is what someone believed on the day they wrote it.
The code is what runs. When they disagree, the code wins, and the comment is a
finding to report — see the `self-documenting-names` skill.

The same holds for names. `validateOrder` may also charge the card. Open it.

## Say what you have not read

You will plan before you have read everything. That is normal. Mark it.

Write "unread" next to any file you are reasoning about but did not open, and
say what you assumed. An assumption you declared is a question. An assumption
you buried is a bug.

Never write a plan step for a function you have not seen. Read it, or make
reading it step one.

## Start from the goal

Write the goal in one sentence before you plan. Then list the smallest set of
files that can satisfy that sentence. That list is the scope.

If you cannot write the goal in one sentence, you have more than one task. Split
them and plan the first.

## The default is: do not touch it

A file outside the scope stays untouched. This holds even when the file is ugly,
even when the fix is obvious, even when you are already reading it.

Bad code you did not cause is not this task.

## The three reasons to widen the scope

Touch an out-of-scope file only when one of these is true.

1. **Your change alters how that file behaves.** A caller, a subclass, a test, a
   type, a schema consumer. If leaving it alone changes a feature the user did
   not ask to change, it is in scope. Silent behaviour change is the failure to
   avoid.
2. **Your solution opens a security hole.** A new input path, a widened
   permission, a leaked secret, a bypassed check. Fix it inside this task.
3. **Your solution creates a performance leak.** An unbounded query, a loop over
   a network call, an unreleased handle, a cache that never evicts. Fix it inside
   this task.

Nothing else qualifies. Not style, not naming in untouched code, not a refactor
you would enjoy, not an unrelated bug.

## A file you open is different from a file you widen into

The scope rules above are about which **files** you touch. Inside a file you are
already editing, one kind of cleanup is always in scope: **pure movement.**

Reordering functions so each helper sits below its caller changes no behaviour,
so it carries none of the risk the three reasons guard against. Do it — see the
`helper-functions-ordering` skill. Commit the move separately from the change,
or the diff becomes unreadable.

Everything else stays out. A rename that reaches other files, a signature
change, a logic tidy — those are new tasks, not opportunities.

## When you find something else

You will find unrelated problems. Report them; do not fix them.

State the file, the problem, and the risk in one line each. The user decides
whether it becomes the next task.

## Before you write the plan

Ask, for each step:

- Does this step move the goal sentence forward? If not, delete it.
- Does a smaller version of this step work? Prefer it.
- What breaks if I skip this step? If nothing, skip it.
- Which line did I read that makes this step necessary? If you cannot point at
  one, the step rests on a guess.

## Applying this

- Name the in-scope files in the plan. Name any out-of-scope file separately,
  with which of the three reasons put it there.
- Prefer changing one function to changing one file. Prefer changing one file to
  changing one module.
- A large diff needs a reason, not an apology.
- Cite the file and line for every claim about how the code behaves today.
- "I assume" is allowed in a plan. "It works like this" without a citation is
  not.
