---
description: Write or update the `.ag` file that makes an agent app runnable from a shell, so nobody hand-writes the YAML.
argument-hint: "[path to the app, default: cwd]"
allowed-tools: Bash, Read, Glob, Grep
---

Write or update the `.ag` file for the agent app at `$1` (default: the current
directory).

Use the `agent-app` skill, `/agent-app:update-ag` workflow.

**This command holds no `Edit` and no `Write`.** The file is written by
`scripts/update_ag.py`, invoked through `Bash`, which emits only YAML the
launcher has already accepted. A model composing that YAML itself is a model
inventing keys the format does not have, or copying a declaration the `.ag` is
built never to copy — which is the failure this plugin exists to catch.

1. `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/update_ag.py" --root <path> --json`

   **Run it without `--write` first, always.** Nothing is written without that
   flag, and the `plan` it reports is what you put to the user before anything
   changes.

2. **Lead with `problems` if it is non-empty**, and go no further. Each entry is
   a repair that needs a decision, not a warning to note in passing: a
   `default-command` naming a command that no longer exists can be removed or
   re-pointed, and those are different repairs. State the choice, take the
   user's answer, and pass it back as `--default-command` or
   `--no-default-command`. The script refuses rather than guessing, and so
   should you.

3. **Report the `plan` as it stands**, including its `keep` steps. Those are the
   evidence that nothing the file's author chose was discarded — a timeout they
   set deliberately, a comment they left, the order they wrote the keys in. On a
   file that is already correct there is nothing but `keep` steps and the answer
   is one line: it is current.

4. **The `default-command` is yours to recommend**, and the skill states the
   trade. One command means nothing to mistype into, so a default is close to
   free; several means a typo silently becomes an argument instead of an error.
   Say which way you went and why — do not pass the flag silently.

5. **Raise `resolution.note` if it is set.** The app is installed at one path and
   the user is standing at another, so `plugin:` and `plugin-dir:` would run
   different copies. That is theirs to settle, not yours.

6. Re-run with `--write` once the decisions are made. The script writes the file
   to a temporary name beside the target, has the launcher accept it, and only
   then renames it into place — so a refusal leaves the original untouched.

7. **Check `validated` before reporting success.** `ran: false` means the
   launcher was not found and the file was written but never proved runnable;
   say that plainly instead of reporting a clean write. Unmeasured is not clean
   here either.
