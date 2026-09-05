---
name: clean-code-implementation
description: The rules that bind every line of code you write in this codebase - verb function names, functions under the line limit, names instead of comments, helpers defined below their caller, and the wider maintainability habits. Use whenever you write, edit or review code, before you start an implementation, when a hook blocks an edit, or when you are about to open a pull request.
---

# Clean code implementation

Five rules bind every line you write. They are one habit, not five checklists.

| Rule | Skill | Enforced by |
| --- | --- | --- |
| A function name is a verb | `function-names-are-verbs` | nothing — you |
| A function is short | `oversized-function` | `oversized_function.py` |
| A name replaces a comment | `self-documenting-names` | `comment_smell.py` |
| A helper sits below its caller | `helper-functions-ordering` | `helper_order.py` |
| The code stays maintainable | `maintainable-coding-principles` | nothing — you |

Load the skill itself when a rule bites. This page is the index, not the
content.

## Not optional

These are required rules. They are not style preferences.

Three of them block your turn. The verb rule and the maintainability rule do
not, which makes them the ones you will drop first. They are not weaker.

## They are the same rule

Each one pushes meaning into a name.

- The verb says what the function does.
- The line limit says it does only that.
- The absent comment says the name was enough.
- The position says which function it serves.

A failure in one shows up as a failure in the others. A function you cannot name
with one verb is a function doing two things, and it is the function you were
about to write a comment above.

## The order to apply them

1. **Name it first.** Write the verb before the body. `chargeOrder`, not
   `orderProcessing`. If no single verb fits, you have two functions — stop and
   split before you write either.
2. **Write the body.** Watch the length. Passing 12 effective lines is a signal
   to name the responsibilities, not a signal to extract `helperA`.
3. **Delete the comments.** Every comment you wanted is a name you did not pick.
   Move the meaning, then remove the comment.
4. **Place it under its caller.** A new helper goes directly below the line that
   calls it, never at the top or the bottom of the file.
5. **Check the wider habits.** Guard clauses, meaningful names, contained
   dependencies, unrepresentable invalid states, decisions separate from side
   effects, useful errors, focused changes — see `maintainable-coding-principles`.

## Before you finish

Read your diff and ask five questions.

- Does every new function name start with a verb that is true?
- Is any new function over the limit without a written reason?
- Does any new comment say what the code does?
- Is any new helper defined above the function that calls it?
- Does this design make the code easier for the next engineer to understand,
  safely change, test, and trust?

Five "no" answers and you are done.

## The escape hatches

`allow-long-function: <reason>`, `allow-comment: <reason>` and
`allow-helper-order: <reason>` all need a written reason. A bare marker is
reported.

Reaching for a marker before you have tried the rename is a skipped step, not a
judgement. "The rest of the file does it this way" is not a reason.

## Legacy code you touch

The three name-and-length rules bind the lines you write. Old lines around them
stay — a rename spreads across call sites, and that is a new task.

Ordering is the exception. It is pure movement, so when you open a file, put its
helpers under their callers. Commit that move on its own.

## What this does not cover

Scope. How much to change is a separate decision — see the `minimal-scope-plan`
skill. Generated and vendored files are outside all five rules; change the
generator, not the output.
