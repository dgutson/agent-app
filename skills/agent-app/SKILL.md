---
name: agent-app
description: Build and maintain agent apps — console apps whose main() is a skill, where a bundled tool establishes the facts and the model supplies only the judgment a script cannot. Use when the user runs /agent-app:create, /agent-app:lint or /agent-app:partition, or asks to build a new skill or plugin that wraps a CLI, to decide what belongs in a script versus in the prose, to design a tool's JSON output for an agent to read, to check whether a skill and its tool have drifted apart, to work out whether something is an agent app at all rather than a guidance skill or a harness extension, or says things like "should this be a script or a prompt", "my skill keeps re-deriving things", "the tool grew a field and the skill never learned it", or "review my SKILL.md".
---

# Agent apps

> **An agent app is a console app whose `main()` is a skill.**

That is the whole of it. A user runs it by name, it does the job, it hands back
a result — and from where they stand, `deptool review` should be the same kind
of thing as `ls -l`. Ideally they never learn that a model ran the last mile.

Most agent apps have two halves, and the good ones divide the work the same
way: the bundled tool establishes every fact that is mechanically
establishable, and the prose supplies the one thing a script cannot — judgment,
and honesty about how far the evidence supports it. `deptool check` will tell
you a dependency is four versions behind, which symbols you consume, and
whether the header diff could be read at all. It will not tell you whether to
upgrade. That is the shape to aim for.

## Is this an agent app?

Three cuts, in order, answered about the artifact in front of you. An agent app
is yes to all three.

1. **Is there a `main()` — something a user invokes by name?** A command, a
   slash command the skill names as its own, an executable on `PATH`. If
   instead it fires on context to change how the model works — "use uv, not
   pip", "write tests this way" — then nobody runs it; it runs on them. That is
   a **guidance skill**, and almost none of what follows applies to it.
2. **Is the result the user's?** An app delivers something they asked for: a
   file, a report, a verdict, a change to their repository. If running it
   instead reconfigures the harness or the model's own setup, it is a **harness
   extension** — a hook, an MCP server, a statusline, an installer.
3. **Does the last step need judgment?** If every step is computable, the
   honest advice is to ship a plain CLI and skip the skill. An agent app
   wrapped around a complete tool is pure overhead, and saying so is more
   useful than building one.

**What is deliberately not a cut: whether it ships a script.** That is
implementation, and the user never sees it. `roadmap` is implemented entirely
in prose and `check-chat` in sixteen Python modules; both are apps, and a
definition that flipped when you refactored prose into Python would be a
definition about internals rather than about kind. The partition below is
advice on how to *implement* an app well — not a membership test. Confusing the
two is how a linter ends up telling a guidance skill that a script owes it an
answer.

The cuts are also why the partition matters at all, and the reason is not
tidiness: **every fact you move into the script is one less place the model
shows through.** The part of the illusion that cannot hold yet is
repeatability — same input, same output — which is exactly the pressure to push
everything determinable down into the tool.

### Where it sits among plugins and skills

Three words that name different things, and only one of them is a shape:

- A **plugin** is a *distribution format* — a manifest plus any of commands,
  skills, hooks, MCP servers. It answers "how is this installed".
- A **skill** is a *unit of instruction* the model loads. It answers "what does
  the model know here".
- An **agent app** is a *kind of program*. It answers "what is this for".

They are orthogonal, and the containment runs one way only: an agent app is
usually implemented as a plugin, and almost no plugin is an agent app. An agent
app can equally ship as a personal or project skill directory with no manifest
at all. "Every agent app is a plugin" is false; "implemented as a plugin" is
the accurate relation.

Building one well is then mostly one decision made repeatedly: **what goes in
the script, and what stays in the prose.** Everything below is in service of
that.

## The tool

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lint_agent_app.py" --root <plugin-dir> [--json]
```

| Flag | What it does |
|---|---|
| `--root` | Plugin directory to check. Defaults to cwd. |
| `--json` | Machine-readable findings plus a `coverage` block. Use this when you intend to reason over the result. |
| `--init-allow` | Write `.agent-app-allow` as a baseline of every currently unread evidence key, then exit. Adoption step for an existing app. |
| `--wide` | Extract evidence keys from every module, not only the one that writes the payload. Higher recall, much more noise. |
| `--only CHECK` | Report one check — `unread`, `stale-ref`, `rederive`, `xref`, `exit-code`, `command`, `frontmatter` — or one rule code, `AA301`. An unknown value is a usage error, not an empty report: a typo must never read as a clean run. |
| `--verbose` | Print every finding. Without it, a rule that fires more than six times in one file collapses to a list of its subjects. Console only. |

Exit codes: `0` clean, `1` findings, `2` usage error.

The two output channels are not the same report. The console is written for a
person — one line per finding, paths relative to the root, each rule's fix
stated once rather than once per finding. `--json` is written for you, and it
is the one to run. Never reconstruct from the console what the payload already
carries.

### `classification` — what it found to lint, before it says anything about it

The tool establishes the two facts about an artifact's shape that a script can
establish honestly, and stops. It does **not** decide whether the thing is an
agent app: that turns on cuts #2 and #3, which are about what running it
delivers and to whom, and a script that guessed at them would be doing the
exact thing this plugin tells everyone else not to do. Finish the decision
yourself, from these:

| Field | What it is | How to treat it |
|---|---|---|
| `entry_points` | Commands, and skills that name their own slash command. | Cut #1, mechanised. Empty means nobody invokes this: it is guidance, not an app, and saying "your agent app has no findings" about it is wrong twice over. |
| `invocable` | Whether `entry_points` is non-empty. | The gate on the `rederive` check. |
| `tools` | First-party executables, **minus** anything the harness runs. | Their absence is not a defect. A prose-only app is an app; the partition is advice about it, not a verdict on it. |
| `harness_wired` | Executables reachable from `hooks`, `mcpServers` or `statusLine`, transitively. | Evidence for cut #2. A plugin whose every executable is here delivers to the harness, not to the user. |
| `emits_payload` | Which tools write JSON to stdout. | Where the evidence contract actually lives. If this is empty and `tools` is not, the tool talks to a person, not to a model. |
| `has_tool_half` | Whether `tools` is non-empty. | The gate on `unread`, `stale-ref` and `exit-code`. |
| `warning` | Set when the artifact has no entry point at all. | Addressed to whoever aimed the linter, not to the artifact. Relay it, and do not convert it into a finding — it does not fail the run, because there is nothing here for its author to fix. |

**Checks are tiered by what they presuppose**, never by what the artifact is:

| Tier | Runs when | Checks |
|---|---|---|
| any skill | always | `frontmatter`, `xref`, `command` |
| an app | `invocable` | `rederive` |
| a tool half | `has_tool_half` | `unread`, `stale-ref`, `exit-code` |

Tiering on a measurement precondition rather than on a classification is what
keeps a recommendation ("this wants a script") from quietly becoming a verdict
("this is not an agent app"). Naming a check with `--only` overrides its tier —
a question asked directly gets answered — and the run says so in `coverage`.

Each entry in `findings` carries:

| Field | What it is | How to treat it |
|---|---|---|
| `code` | Stable rule id, `AA301`. Fixes the check and the severity between them. | Quote it. It is what makes a finding referable — in a commit message, in a `--only` filter, in the next run. |
| `check` | Which check fired. | Decides the fix; see the triage list under `/agent-app:lint`. |
| `severity` | `error` or `warn`. | An `error` is a defect in the app. A `warn` is a judgement call — `xref` and `command` findings can be deliberate. |
| `file`, `line`, `col` | Where it is, relative to the root. `line` and `col` are `null` where the finding is about a whole file, or about something absent. | Quote what is there. A `null` is the tool declining to guess a position, not a zero. |
| `subject` | The identifier the finding is about: the evidence key, the cited token, the exit status, the command slug. | Group on it. It is what lets you say "17 keys: a, b, c" without parsing `message` back apart. |
| `message` | The defect in one line. | Relay it. Do not embellish it into a bigger claim. |
| `hint` | The usual fix, when there is one. | A suggestion, not a verdict. Identical for every finding of a code — state it once. |

Codes are grouped by cause: `AA0` structure, `AA1` partition, `AA2` references,
`AA3` evidence, `AA4` navigation, `AA5` control flow, `AA6` commands.

And `coverage` carries `prose_files` (what was read), `source_files_read`
(how many), and `checks_skipped` — each entry a `check`, a `reason`, and a
`kind`:

| `kind` | Means |
|---|---|
| `not-run` | The check never executed. Nothing whatever is known about it. |
| `partial` | It ran over less than the whole app. What it did not reach is unchecked, not clean. |
| `note` | It ran in full, but how to read its findings needs saying — a first run with no `.agent-app-allow` reports long-standing keys alongside new ones. |
| `not-applicable` | It presupposes something this artifact does not have. Nothing is missing and nothing went unmeasured. |

**Read the `coverage` block before you say anything reassuring.** For the first
three kinds, `checks_skipped` lists what could not be run and why — no source
files found, non-Python tool, keys outside the payload-assembling module. A
skipped check is not a passing one, and reporting a clean run without
mentioning the skips is the exact error this whole discipline exists to
prevent.

`not-applicable` is the one kind that carries no such warning, and conflating
it with the other three is its own dishonesty in the opposite direction. A
prose-only app has no second half for `unread` to read; that is a fact about
how it is built, not a gap in what was measured. Say "does not apply", never
"was not checked", and never let it colour the verdict — an artifact with four
inapplicable checks and no findings is clean.

## The partition

Everything from here down is about **implementing** an app, and applies once
the three cuts have said you are building one. None of it decides whether
something is an agent app — an app whose every step is prose is still an app,
and this is the argument for giving it a tool, not for withdrawing the name.

For every step the app performs, ask in order:

1. **Is the answer determinable?** If a program can compute it — parse it, <!-- agent-app: ok -->
   diff it, hash it, query it, count it — then a program must. Not "could in <!-- agent-app: ok -->
   principle": if you would trust a script's answer over the model's, it goes
   in the script. Nothing determinable belongs in the prose, ever.
2. **Must it be identical every run?** Anything another step branches on,
   anything written to disk, anything that has to survive being run in CI. Put
   it in the script even when the model could do it, because "usually the same"
   is not the same.
3. **What is left?** Weighing, ranking, deciding what matters to *this* user,
   saying "no", and stating how much the evidence actually supports the
   conclusion. That is the skill's job, and it is the whole of the skill's job.

The corollary is a standing rule worth writing into every agent app's SKILL.md
in these words: **never re-derive what the tool already provides.** A skill that
recomputes what its own tool just handed it is slower, non-deterministic, and
wrong more often — and the failure is invisible, because the answer usually
looks fine.

### The two failure modes

Agent apps fail in exactly two directions, and they need different fixes.

**Re-derivation** — the prose is doing work a script should do. Symptoms: the
skill tells the model to grep, count, compare versions, parse a file format, or <!-- agent-app: ok -->
"check whether". Every one of those is a script that was never written. Fixed
by `/agent-app:partition`.

**Unread evidence** — the tool computes something and no prose teaches the
model to read it. This is the one that actually happens, because it happens
*by inaction*: someone adds a field, and nobody revisits four hundred lines of
policy prose. The evidence is produced, paid for, and thrown away at the
judgment layer. Fixed by `/agent-app:lint`.

The direction matters. Prose-referencing-code stays clean on its own, because
prose gets written with the code in view. Code-emitting-unread-fields rots
silently and forever. Weight your attention accordingly.

## The evidence contract

This is the part that most skills get wrong, and it is what makes the
difference between a tool an agent can reason over and one it can only quote.

**A tool for a model returns facts with their provenance and their limits
attached, not answers.** Concretely, every payload field that carries a claim
should be able to say how it was obtained and how far to trust it:

- **Provenance.** Where did this come from? `confidence: declared` (an upstream
  declaration) versus `confidence: notes` (prose in a changelog) are different
  claims, and the model must be able to tell them apart without guessing.
- **Coverage limits.** `truncated`, `not_located`, `headers_read` — what the
  run did *not* reach. Without these, an empty result is indistinguishable
  from a clean one.
- **Self-check.** Does the same extraction reproduce a value already known to
  be correct? `reproduced` / `diverged` / `unavailable` tells the model whether
  the mechanism works *for this input*, which is worth more than any single
  reading it produces.
- **Floors, not counts.** When the source cannot give an exact number, say so
  in the field name or a sibling flag (`behind_by_is_floor`) rather than
  emitting a number that reads as exact.

Then the prose's job is largely to be **a manual for reading those fields** —
which ones outrank which, and what each one means for the conclusion. The
single most important sentence to write, in whatever form fits the domain:

> **Unmeasured is not the same as clean.** An empty result with an unrun or
> truncated check behind it says nothing. Report it as unknown, never as fine.

If you write only one rule into a new agent app, write that one.

### Control flow belongs in the process, not the paragraph

- **Exit codes, not prose.** Distinct statuses for the outcomes the skill must
  branch on: refused-on-purpose, verified-and-failed, and plain error should
  not be the same number. The prose then branches on an integer instead of
  parsing English. Document every code the tool can raise; a status the model
  was not told about is a status it will mishandle.
- **A dry-run verb before every writing verb.** `plan` before `apply`. It
  makes "show the user what will change, then get confirmation" enforceable
  rather than aspirational, and it is what lets the skill promise that a
  refusal wrote nothing.
- **Refusals that refuse.** When the tool cannot establish something a safe
  edit depends on, it should exit non-zero and write nothing, rather than
  proceeding with a warning. A warning in a long transcript is not a control
  flow mechanism.
- **A command that reports does not change the user's work — enforce it in
  `allowed-tools`.** Split every app's commands into those that inspect and
  those that change, and give the inspecting ones no `Edit` and no `Write`. Not
  a convention in the prose: the tool grant, because prose that says
  "read-only" alongside an `Edit` grant will lose that argument the moment a
  fix looks obvious. A command that rewrites what it was asked to inspect
  cannot be run against a repository the user does not own, cannot run
  unattended, and turns "show me the state of this" into an unrequested change
  to a working tree.

  The constraint is on **the user's material**, not on writing as such. A
  reporting command may still produce its own artifact — a findings file, a
  report, a cache — because that is output rather than a change to anything
  they wrote, and they decide whether to keep it. Have the script emit it,
  invoked through `Bash`, so the grant stays off the agent. What it must never
  do is edit the thing under inspection, or write the app's own configuration
  and thereby decide something on the user's behalf. Fixing is a separate,
  separately invoked command, run after the user has seen the report.
- **Escape hatches ship with a policy.** Any flag that bypasses a refusal must
  be documented in the prose alongside the circumstances in which the model
  should *not* reach for it. Otherwise the model will use it to make the
  refusal go away, which converts a designed safeguard into an inconvenience.

### State outside the context window

An agent app that runs more than once should write what it concluded somewhere
durable — a profile file, an assessment block, a cache. Two rules make that
work:

- **Regeneration preserves judgment.** The routine refresh rewrites the
  machine-derived fields and leaves the model-written prose alone. Only an
  explicit, confirmed `--force` discards accumulated judgment, and the skill
  must warn before running it.
- **Staleness is a computed fact, not a vibe.** A `status` verb that content-
  hashes the inputs lets the skill say "current" in one line and stop, instead
  of re-analysing an unchanged repository every invocation.

## What to run, and when

The three commands are not three views of one review. They answer different
questions, at different points in an app's life, at very different cost.

| | `create` | `lint` | `partition` |
|---|---|---|---|
| Question | what should this app be? | do the halves still agree? | is the line in the right place? |
| Kind | judgment | mechanical | judgment |
| Cost | a session | seconds | a careful read of both halves |
| Cadence | once | every change, and in CI | at design time, then rarely |
| Output | a new app | fixes | a proposed redesign |

The lifecycle:

1. **`/agent-app:create`** — once, at the start. It ends by running `lint`.
2. **`/agent-app:lint`** — from then on, whenever either half changes, and in
   CI. This is the one that runs constantly. It is a script precisely so that
   it can.
3. **`/agent-app:partition`** — when `lint` reports `rederive` findings you
   cannot dismiss, when the app feels wrong ("the skill is doing too much"),
   or before a significant extension. Not on a schedule.

**Why `partition` is not simply part of `lint`.** Lint is cheap, deterministic,
and safe to run on every commit; partition costs a full read of the tool and
the prose together, and it proposes a *redesign* rather than a fix. Folding a
session-length judgement into the check you want in CI would mean either
running the expensive thing constantly or never running it at all.

But they are not independent either, and the seam between them is itself an
instance of the rule this skill teaches: **finding the lines worth judging is
mechanical, and judging them is not.** So the mechanical half lives in the
linter as the `rederive` check, which flags prose that asks the model to
*establish* something, and `partition` starts from that list rather than
re-reading the app from scratch. Lint hands partition its evidence, exactly as
a tool hands its skill evidence.

If you only ever run one, run `lint`. It is the one whose findings accumulate
silently.

## Workflows

### `/agent-app:create` — build a new one

Do not scaffold first. The layout is the easy part and getting it right early
is worth nothing; the partition is the whole design.

1. **Establish the question the app answers**, then run the three cuts on it
   before agreeing to build anything. Is there something the user will invoke
   by name, or are they describing standing guidance? Is the result theirs, or
   is it a change to their harness? Is the last step judgment, or is it
   computable — in which case say so and offer them a plain CLI, which is
   cheaper to build, cheaper to run, and testable.
2. **Enumerate the steps**, and partition each with the three questions above.
   Write the partition down and show it to the user before writing any code.
   This is the artifact they should push back on.
3. **Design the evidence contract** for the script half: the payload's fields,
   which uncertainty fields ride along with each claim, the exit codes, and
   which verb is the dry run. Do this before implementing, because it is the
   interface between the halves and it is expensive to change later.
4. **Write the tool.** It must produce evidence and stop short of the verdict.
   If you find yourself writing the ranking in Python, you have mis-partitioned
   — either the ranking is mechanical (in which case keep it, and the app is
   smaller than you thought) or it is judgment (in which case emit its inputs).
5. **Write the SKILL.md**, in this order: what the tool is and how to invoke
   it; how to read each evidence field, weakest to strongest; the rubric; the
   output shape; the honesty rules. Policy, not sequencing — if the prose is
   mostly numbered steps, step 4 is unfinished.
6. **Write the commands**, one per workflow, each naming the skill and its
   workflow rather than restating it. Commands are entry points; duplicating
   the policy into them creates two copies that will disagree.
7. **Run `/agent-app:lint`** and fix what it finds before shipping.

### `/agent-app:lint` — has it drifted?

**Read-only with respect to the app under inspection. It reports; it does not
fix.** It does not touch that app's SKILL.md, its commands, its scripts, or its
`.agent-app-allow` — the last one because that file records decisions, and
making a decision on the user's behalf is the same overreach as rewriting their
prose. No `--init-allow` on their behalf, however obvious the fix looks.

The line is **whose work is being changed**, not whether a byte was written.
Emitting the run's own findings to a file is output, not a modification of
anyone's source, and the user decides whether it gets committed or ignored. So
a reporting command still holds no `Edit` and no `Write`; where it needs to
produce an artifact, its script writes it, invoked through `Bash`.

Report, then stop. If the user reads the report and asks for the fixes, apply
them as an ordinary request — but that is a second instruction from them, never
a continuation of this one.

1. Run the tool with `--json` against the plugin root, with no other flags.
2. **Read `classification` first, and say what you are looking at.** If
   `warning` is set, lead with it: they have pointed an agent-app linter at
   something that is not an app, and the useful reply names what it is —
   guidance skill, harness extension — rather than reporting on it as though
   it had fallen short. If `tools` is empty on a real app, that is a prose-only
   implementation and worth one line; it is not a defect, and the `rederive`
   findings are the interesting part of that report.
3. **Read `coverage.checks_skipped` next** and relay it. A clean report with
   two skipped checks is not a clean app — but keep `not-applicable` entries
   out of that sentence, since nothing about them went unmeasured.
4. Report the findings by kind, because they mean different things. For each,
   name the location, the defect, and the fix that would resolve it — naming
   the fix is the job here, applying it is not. Quote the `code` with the kind
   the first time each appears, so the user can filter on it afterwards:
   - `unread` (`AA301`) — the tool emits it, no prose teaches it. Each one needs a
     **teach-or-justify** decision: write the field into the skill (saying what
     it means for the conclusion, not merely that it exists), or record in
     `.agent-app-allow` why the model has no use for it. State which each one
     needs; do not make the call or write either file.
   - `stale-ref` (`AA201`) — the prose asserts a symbol the code does not have.
     Always a real bug; the model is being instructed to look for something absent.
   - `rederive` (`AA101` verb, `AA102` threshold) — a **candidate**, not a
     defect: prose that asks the model to
     establish something a script might owe. Dismiss the ones that are really
     judgment (they are common — "check whether the recorded reason still
     holds" is not a script's work). If any survive that, do not fix them
     here; hand them to `/agent-app:partition`, which is where a change to the
     partition gets designed and approved.
   - `xref` (`AA401`) — a cross-reference to a section that is not there.
   - `exit-code` (`AA501` documented, `AA502` raised) — a status raised but
     undocumented, or documented but never raised. The first makes the model
     mishandle it; the second makes it branch on a case that cannot occur.
   - `command` (`AA601`, `AA602`) / `frontmatter` (`AA001`–`AA005`) — structural.
5. On an app being linted for the first time, expect a large `unread` list.
   Roll it up by `subject` — the keys, comma-separated, per file — rather than
   restating the same sentence per key; the console does the same past six in
   one file, and for the same reason. Say that `--init-allow` would baseline
   it, and what that does: it makes the app green *now* so that every field
   added *later* must be classified. The baseline is a to-do list, not an
   absolution. **Recommend it; do not run it** — it writes a file into the
   user's repository.
6. Close with the counts by severity, and stop. If the user then asks for the
   fixes, that is a fresh instruction and you can act on it — but do not offer
   to "just quickly fix" one as part of this report.

### `/agent-app:partition` — is the split in the right place?

Lint checks whether the two halves agree. This checks whether the line between
them is drawn correctly, and it is judgment, so it cannot be a script.

An app with `tools` empty is the strongest case for running this, not a reason
to skip it: the whole implementation is prose, so every fact it establishes is
one the model re-establishes on every run. The output is then the design of the
tool that does not exist yet — which fields it would return, and which of the
prose's current steps stop being prose once it does.

1. **Start from the linter's candidates**, not from a blank page:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lint_agent_app.py" --root <path> --only rederive --json
   ```

   Never re-derive what the tool already provides — that rule applies to this
   skill too. The `rederive` check has already found the lines that ask the
   model to establish something; your job is to judge them.
2. Then read the SKILL.md and the tool's entry point in full, because the
   check has a known blind spot: it finds instructions phrased as commands,
   and misses re-derivation phrased as description ("the version in the
   manifest is usually the older one"). Treat its list as a floor.
3. For each candidate, say what the script should return instead — the field
   name and what it would carry. A finding without a proposed field is not
   actionable. Dismiss the ones that are genuinely judgment, out loud, so the
   next reader does not re-open them.
4. Flag the reverse too, though it is rarer: a script making a *judgment* call
   the user should own — a hardcoded ranking, a silently applied threshold, a
   default that decides something contestable. Those belong in the prose, or
   as an emitted input to it.
5. Check the evidence contract against the section above: does each claim carry
   its provenance and its coverage limits? A payload of bare answers is the
   most common finding here, and the most expensive one.
6. Report as a table: instruction → verdict (script / prose / already right) →
   proposed field. Then say which one to do first.

## Honesty rules

- Report what the linter could not check as prominently as what it found. This
  skill has no standing to preach coverage honesty and then bury its own.
- The extractors are regex, not parsers. A `stale-ref` finding is strong
  evidence, not proof; an empty `unread` list under a skipped check is not
  evidence at all.
- Do not recommend an agent app for a problem that does not need one. The
  overhead is real: two halves to keep in agreement, a contract to maintain,
  and a linter in CI. If the tool is complete, ship the tool.
- When `/agent-app:partition` finds nothing, say so plainly. A review that
  manufactures findings to look thorough is worse than no review, because the
  next one will be believed less.
