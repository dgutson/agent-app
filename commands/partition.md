---
description: Review an existing skill for work the prose is doing that a script should be doing, and vice versa
argument-hint: "[path to the plugin or skill, default: cwd]"
allowed-tools: Bash, Read, Glob, Grep
---

Review the agent app at `$1` (default: the current directory) for whether the
line between its script and its prose is drawn in the right place.

Use the `agent-app` skill, `/agent-app:partition` workflow.

This is judgment, not a lint. `/agent-app:lint` checks whether the two halves
**agree**; this checks whether the split between them is **correct**. Run both
— they find different things.

1. **Get the candidate list from the linter first** — do not re-derive what the
   tool already provides:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lint_agent_app.py" --root <path> --only rederive --json
   ```

2. Then read the SKILL.md, the tool's entry point, and the commands in full.
   The check finds re-derivation phrased as an instruction and misses it
   phrased as description, so its list is a floor, not the answer. Policy
   duplicated into a command file is its own finding.
3. For each, name the field the script should return instead, and what it
   would carry. A finding with no proposed field is not actionable — it is a
   complaint.
4. Flag the reverse, which is rarer and more damaging: a script making a
   judgment the user should own. A hardcoded ranking, a silently applied
   threshold, a default that settles something contestable. Those belong in
   the prose, or as an emitted input to it.
5. Audit the evidence contract against the skill's section on it. Does each
   claim carry its provenance and its coverage limits, or is the payload bare
   answers? That is the most common finding here and the most expensive to fix
   later, so raise it even when nothing else turns up.
6. Report as a table — instruction → verdict (script / prose / already right)
   → proposed field — then say which one to do first and why.

**Read-only.** Propose the changes; do not apply them. The partition is the
design of the app, and the user should approve a redesign rather than discover
it. If they ask you to apply a specific finding afterwards, that is fine.

If nothing is misplaced, say so in a line and stop. A review that manufactures
findings to look thorough makes the next one less believable.
