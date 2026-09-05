---
name: code-review-do-what-it-claims
description: Review the current branch's diff against main and check whether the changes actually do what they claim to do, and whether they overengineer the solution. Use when the user asks to review a PR, review changes, or check if a change matches its description, commit message, or ticket.
---

# Code review: does it do what it claims

Compare the current branch against `main`. Judge two things: does the code
match its own claim, and is the solution no bigger than the claim needs.

## Steps

1. Find the claim. Read the PR title/description if given, else the commit
   messages on this branch, else the ticket the branch references.
2. List changed files only:
   ```bash
   git diff --name-only main...HEAD
   ```
3. Read the full diff for those files:
   ```bash
   git diff main...HEAD -- <file> ...
   ```
   Do not review files outside this list, even if they look related.
4. For each changed file, check the diff against the claim:
   - Does the change implement what the claim says, not something adjacent?
   - Is any part of the claim left undone?
   - Does the diff do something the claim never mentioned (silent scope creep)?
   - If the claim names a bug, does the fix address the root cause shown in the
     diff, or paper over the symptom?
5. Check the diff for overengineering:
   - A new abstraction, layer, config flag, or parameter with only one caller
     or one value, ever.
   - A generic or pluggable solution where the claim needed one fixed case.
   - New dependencies, files, or indirection the claim does not require.
   - Speculative handling for inputs or cases the claim never mentions.
6. Ignore style, naming, and performance here — that is a different skill's job.

## Report

State per file: claim covered / partially covered / not covered, one line why.
List overengineering findings separately, one line each, file:line and what is
unneeded. Then one line overall verdict. Do not propose fixes unless asked.
