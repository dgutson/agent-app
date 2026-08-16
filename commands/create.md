---
description: Design and build a new agent app — a skill whose tool establishes the facts and whose prose supplies the judgment
argument-hint: "[what the app should answer]"
allowed-tools: Bash, Read, Edit, Write, Glob, Grep
---

Build a new agent app$1.

Use the `agent-app` skill, `/agent-app:create` workflow.

Start with the partition, not the scaffold. In order:

1. **Establish the question.** What does the app answer, and is its final step
   genuinely judgment? Two ways to fail before writing anything:
   - the answer is fully computable — the user wants a plain CLI, and an agent
     app wrapped around a complete tool is pure overhead. Say so.
   - the answer needs no established facts — the user wants an ordinary skill,
     with no script at all.
2. **Enumerate the steps and partition each one** with the skill's three
   questions. Determinable → script. Must-be-identical → script. What is left
   is the prose.
3. **Show the user the partition and get their reaction before writing code.**
   This is the design; the layout is not. A partition the user disagrees with
   is cheap to fix now and expensive to fix after the tool exists.
4. **Design the evidence contract next** — payload fields, the uncertainty
   field riding along with each claim, the exit codes, the dry-run verb. This
   is the interface between the halves. Changing it later means changing both.
5. Write the tool. It emits evidence and stops short of the verdict.
6. Write the SKILL.md: how to invoke the tool, how to read each field, the
   rubric, the output shape, the honesty rules. If it comes out as mostly
   numbered steps rather than policy, the tool is unfinished — go back to 5.
7. Write one command per workflow, each pointing at the skill rather than
   restating it. **Split them into commands that inspect and commands that
   change, and give the inspecting ones no `Edit` and no `Write` in
   `allowed-tools`.** The grant is the enforcement; prose saying "read-only"
   next to an `Edit` grant does not survive the first obvious-looking fix.
8. **Give it a command line** with `/agent-app:update-ag`, so what you built is
   a program and not only something typed into a REPL. Do not hand-write the
   `.ag`, and do not teach its format here — the format is specified once, in
   `launcher/ag-format.md`, and the command is what reads it.
9. Run `/agent-app:lint` on the result and fix what it reports.

Ask before creating files outside the directory the user named.
