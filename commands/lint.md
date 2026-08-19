---
description: Report where a skill and the tool it drives have drifted apart. Read-only — reports findings, never edits.
argument-hint: "[path to the plugin or skill, default: cwd]"
allowed-tools: Bash, Read, Glob, Grep
---

Report drift between the prose and the tool of the agent app at `$1` (default:
the current directory).

Use the `agent-app` skill, `/agent-app:lint` workflow.

**This command changes nothing that belongs to the app it inspects.** Not its
SKILL.md, not its commands or scripts, not its `.agent-app-allow`, however
obvious the fix looks. A linter that edits is not a linter, and a check that
silently rewrites the thing it was checking cannot be run on a repository you do
not own or trusted in CI. It has no `Edit` or `Write` tool for exactly this
reason. If a finding is worth fixing, say so and stop.

That constraint is about the user's material, not about writing as such — the
linter emitting its own findings file is output, and theirs to keep or discard.

1. `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lint_agent_app.py" --root <path> --json --emit`

   `--emit` writes the findings to `.agent-app-findings.json` in that root,
   with a content hash of every file the run read. It is what lets a later fix
   step act on this analysis instead of running its own, and tell that the tree
   has moved since. Your report is the same either way; say at the end that the
   file is there.

   **Do not pass `--init-allow`.** Not because it writes a file, but because
   `.agent-app-allow` records which findings were deliberately accepted, and
   that is the user's decision to make rather than yours to make for them.
   Recommend it if a baseline is what they need; let them run it.

2. **Say what you are looking at, from `classification`, before anything
   else.** If its `warning` is set, lead with that: the target has no entry
   point, so it is a guidance skill rather than an app, and the useful reply
   names what it is instead of reporting it as a deficient app. An app with
   `tools` empty is implemented in prose — one line, not a defect.

3. **Relay `coverage.checks_skipped` next.** A check that did not run is not a
   check that passed, and a report that leads with "clean" while two checks
   were skipped is the failure this app exists to prevent. Each entry carries a
   `kind` — `not-run`, `partial`, `note`, `not-applicable` — and the four do
   not license the same sentence. The last one is not a gap: it means the check
   presupposes something this artifact does not have, and it must not colour
   the verdict.

4. Report the findings grouped by kind — `unread`, `stale-ref`, `rederive`,
   `xref`, `exit-code`, `command`, `frontmatter` — quoting each finding's
   `code` the first time its kind appears, since that is what the user can
   filter and refer back to. The skill's workflow section says what each kind
   implies. For each, give the location, what is wrong, and what the fix would
   be. Naming the fix is the job; applying it is not.

5. For `unread` findings, state the **teach-or-justify** decision each one
   needs — teach the field in the skill, or record in `.agent-app-allow` why
   the model has no use for it — without making the decision or writing either
   file. A long `unread` list on a first run is normal: roll it up by `subject`
   per file rather than repeating one sentence per key, say that
   `--init-allow` would baseline it, and leave that call to the user.

6. `rederive` findings are candidates for a misplaced partition, not defects.
   Say which look like genuine judgment and which do not, then point at
   `/agent-app:partition`. On an app with no tool at all, this is the report:
   every one of them is a fact its prose re-establishes on each run.

7. Close with the counts by severity, then one line: where the findings file
   was written, and that it is theirs to commit or ignore. Then stop. Do not
   apply anything here, and do not offer to "just quickly fix" one. If the user
   reads the report and asks for the fixes, that is a fresh instruction and can
   be acted on then.
