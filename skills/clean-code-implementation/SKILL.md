# Clean code implementation

Four rules bind every line you write. They are one habit, not four checklists.

| Rule | Enforced by |
| --- | --- |
| A function name is a verb | nothing — you |
| A function is short | code review |
| A name replaces a comment | code review |
| A helper sits below its caller | code review |

## Not optional

These are required rules. They are not style preferences.

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
2. **Write the body.** Watch the length. Passing roughly 12 effective lines is a
   signal to name the responsibilities, not a signal to extract `helperA`.
3. **Delete the comments.** Every comment you wanted is a name you did not pick.
   Move the meaning, then remove the comment.
4. **Place it under its caller.** A new helper goes directly below the line that
   calls it, never at the top or the bottom of the file.

## Before you finish

Read your diff and ask four questions.

- Does every new function name start with a verb that is true?
- Is any new function over the limit without a written reason?
- Does any new comment say what the code does?
- Is any new helper defined above the function that calls it?

Four "no" answers and you are done.

## Legacy code you touch

The three name-and-length rules bind the lines you write. Old lines around them
stay — a rename spreads across call sites, and that is a new task.

Ordering is the exception. It is pure movement, so when you open a file, put its
helpers under their callers. Commit that move on its own.

## What this does not cover

Scope. How much to change is a separate decision. Generated and vendored files
are outside all four rules; change the generator, not the output.
