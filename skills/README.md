# Global Skill Catalog

A global skill is a subdirectory of this directory containing a `SKILL.md`
file and, optionally, a `metadata.json` file:

```text
skills/
  <slug>/
    SKILL.md          # the instructions text, inlined verbatim into an
                       # assigned agent's first message
    metadata.json      # optional: {"name": "...", "description": "..."}
```

The directory name is the skill's slug and its identity. `metadata.json`'s
`name` and `description` fields are optional; when absent, the slug is used
as the name and the description is left empty.

## Read-only, mirrored at startup

This directory is committed to the `ai-orchestrator` repository. A global
skill is authored and versioned here, by a normal commit — not through the
web UI.

At backend startup, every subdirectory here that contains a `SKILL.md` is
mirrored into the `skills` database table as a row with `source = "global"`.
The UI can assign a global skill to an agent, or inspect its instructions,
but it cannot edit or delete it. Editing `SKILL.md` or `metadata.json` here
needs a backend restart to take effect — the mirror only runs at startup.

A custom skill, created from the UI, lives entirely in the database and has
no file here.

## Renaming

The directory name is the skill's identity. Renaming a directory does not
rename the skill: it creates a new one under the new slug with no
assignments, and leaves the old row in place if any agent still holds it. To
change a global skill's display name, edit `metadata.json` and leave the
directory name alone.
