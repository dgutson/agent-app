---
description: Design and build a new agent app — a skill whose tool establishes the facts and whose prose supplies the judgment
argument-hint: "[a description of the app to build]"
allowed-tools: Bash, Read, Edit, Write, Glob, Grep
---

Build a new agent app$1.

Use the `agent-app` skill, `/agent-app:create` workflow.

**This is a conversation, not a form.** A brief is a starting position, never a
specification: it says what the user pictured, and the parts they did not
picture are exactly the parts that decide what gets built. Ask about those
before writing anything. What you finish with is a directory that installs and
runs, not a design the user has to build themselves.

The layout, which is the same for every app and is not worth deciding twice:

```
<app>/
├── .claude-plugin/plugin.json    name, description, version
├── skills/<app>/SKILL.md         the judgment: how to read the evidence
├── commands/<verb>.md            one per workflow, each naming the skill
├── scripts/<tool>.py             the evidence half, if it has one
└── <app>.ag                      the command line, written by update-ag
```

Start with the partition, not the scaffold. In order:

1. **Interrogate the brief.** Separate what you can decide from what you
   cannot: a default output path is yours to choose, but *which* logs are in
   scope, or what the app should say when nothing is wrong, changes what gets
   built. Ask only the second kind, all at once rather than one message at a
   time, and say plainly what you are assuming for everything you did not ask
   about. If a
   stated requirement is mechanical — a `--format json` that asks the model to
   emit JSON, when the script could serialise it — say so here; that is the
   partition argument arriving early, which is the cheapest time for it.

   **If there is nobody to ask** — the app is running headless, with no user on
   the other end — do not guess. Refuse, and put the questions in the output.

2. **Establish the question.** What does the app answer, and is its final step
   genuinely judgment? Two ways to fail before writing anything:
   - the answer is fully computable — the user wants a plain CLI, and an agent
     app wrapped around a complete tool is pure overhead. Say so.
   - the answer needs no established facts — the user wants an ordinary skill,
     with no script at all.
3. **Enumerate the steps and partition each one** with the skill's three
   questions. Determinable → script. Must-be-identical → script. What is left
   is the prose.
4. **Show the user the partition and get their reaction before writing code.**
   This is the design; the layout is not. A partition the user disagrees with
   is cheap to fix now and expensive to fix after the tool exists.
5. **Design the evidence contract next** — payload fields, the uncertainty
   field riding along with each claim, the exit codes, the dry-run verb. This
   is the interface between the halves. Changing it later means changing both.
6. **Scaffold it**, so the directories and the manifest are right by
   construction rather than by recollection:

   `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/scaffold_app.py" --root <dir> --name <app> --description <one line> [--tool] --write`

   It reports the files that remain and what each needs. Re-run it whenever you
   want that list again; it never overwrites a manifest that already exists.
7. Write the tool. It emits evidence and stops short of the verdict.
8. Write the SKILL.md: how to invoke the tool, how to read each field, the
   rubric, the output shape, the honesty rules. If it comes out as mostly
   numbered steps rather than policy, the tool is unfinished — go back to 7.
9. Write one command per workflow, each pointing at the skill rather than
   restating it. **Split them into commands that inspect and commands that
   change, and give the inspecting ones no `Edit` and no `Write` in
   `allowed-tools`.** The grant is the enforcement; prose saying "read-only"
   next to an `Edit` grant does not survive the first obvious-looking fix.
10. **Give it a command line** with `/agent-app:update-ag`, so what you built is
    a program and not only something typed into a REPL. Do not hand-write the
    `.ag`, and do not teach its format here — the format is specified once, in
    `launcher/ag-format.md`, and that command is what reads it.
11. **Run `/agent-app:lint` and fix what it reports**, then
    `claude plugin validate <dir>` to confirm the thing actually installs. A
    clean lint says the halves agree; only validate says it is a plugin.

Ask before creating files outside the directory the user named.
