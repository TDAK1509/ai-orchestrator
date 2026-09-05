---
name: self-documenting-names
description: Write code that explains itself through names instead of comments. Use when adding or reviewing comments, when a comment explains what code does, when naming variables, functions, classes or files, when writing or trimming a docstring, when a hook reports a comment or an over-long name, or when the user asks to clean up comments or improve naming.
---

# Self-documenting names

Never comment on code. A comment that explains code is evidence that the code
does not explain itself. Rename until the code says what the comment said, then
delete the comment.

## Not optional

This rule is required. It is not a style preference and not a default you may
weigh against convenience.

When the hook blocks you, load this skill and do what it asks. Then decide.
Reaching for `allow-comment` before you have tried the rename is not a
judgement call; it is a skipped step. The escape hatch needs a written reason,
and "it matches the file's existing style" is not one. House style is how the
file got this way.

## The rule

1. You want to write a comment. Stop.
2. Read the comment. It describes what the code does or why it exists.
3. Move that meaning into a name: the variable, the function, the class, or a new
   extracted function whose name is the sentence you were about to write.
4. Delete the comment.

## Naming

Long names beat comments. Do not fear a long name.

- `retryCountAfterRateLimit` beats `n` plus a comment.
- `isEligibleForVipDiscount` beats `flag` plus a comment.

But long is not unlimited. **Ten words is the maximum.** Count words in
`snake_case`, `camelCase` and `PascalCase` alike. A name that needs eleven words
is not a naming problem; it is a function doing two things. Split it — see the
`oversized-function` skill.

The only exception: Python test functions. `test_user_cannot_delete_another_users_draft_order`
is a specification, not a name. Let those run long.

## Docstrings

Only when a repository rule requires them. Then keep them minimal: **one or two
sentences.** No parameter tables, no restating the signature, no usage essays.

When you add to a docstring that is already long, add one or two sentences at
most. Do not extend the existing style.

A docstring that restates the signature is worse than no docstring: it is length
without information. Write the one rule the reader cannot see in the code. See
`references/examples.md` for a worked before and after.

## What is not a comment on code

These stay, because they do not explain what code does:

- Directives the tools need: `# type:`, `# noqa`, `// @ts-expect-error`, `// eslint-disable-next-line`.
- Licence and copyright headers.
- `TODO` and `FIXME` markers that record work, not meaning.

## When a comment survives

Rarely, meaning cannot live in a name: a non-obvious external constraint, a
workaround for a third-party bug, a link to a specification. Write it as *why*,
never as *what*, and keep it to one line.

**One line is the limit for a why-comment too.** A paragraph explaining a race
condition or a design tradeoff is not a comment; it is a design note. It belongs
in the pull request, the commit message, or a document you link to in one line.
Code the reader must not break is guarded by a test, not by prose above it.

"Every other function in this file has one" is not a reason. That is the file
telling you how it got this way.

## New code only

The rule binds the lines you write. It does not bind the file you write them in.

Old comments and old names in the same file are not your task. Leave them. A
rename that spreads across call sites is a separate task — say it exists, then
move on. See the `minimal-scope-plan` skill.

Two cases where you fix the legacy code now:

- The rename is confined to the lines you already touched.
- The old name is now wrong because of your change. A stale name is worse than
  no name.

## Generated files are out of scope

Do not apply this rule to generated code: `openapi.json`, generated API clients
and type definitions, `*.gen.ts`, `*.d.ts`, protobuf output, migrations, and any
file whose header says it was generated.

Never hand-edit that output. Change the schema, the template or the generator,
then regenerate. The hooks skip these paths for the same reason.

## Applying this

- Before writing any comment, try three names first.
- When you delete a comment, say which name absorbed it.
- Never leave commented-out code. Delete it; the history keeps it.
- Read `references/examples.md` when a name or a docstring is hard to cut.
