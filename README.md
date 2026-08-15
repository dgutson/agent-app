# agent-app

> **An agent app is a console app whose `main()` is a skill.**

You run it by name, it does the job, it hands back a result. `deptool review`
should be the same kind of thing as `ls -l` — and ideally you never find out
that a model ran the last mile.

Most agent apps have two halves, and this plugin is about dividing them well:
the bundled tool establishes every fact that is mechanically establishable, and
the prose supplies the one thing a script cannot — judgment, and honesty about
how far the evidence supports it. That division is not tidiness. **Every fact
you move into the script is one less place the model shows through.** The part
of the illusion that cannot hold yet is repeatability — same input, same
output — which is exactly the pressure to push everything determinable down
into the tool.

## Skill, plugin, agent app

Three words for different things, and only one of them names a shape.

| | What it is | Question it answers |
|---|---|---|
| **skill** | a unit of instruction the model loads | what does the model know here? |
| **plugin** | a distribution format: a manifest, plus any of commands, skills, hooks, MCP servers | how do I install this? |
| **agent app** | a kind of program | what is this *for*? |

They are orthogonal. An agent app is usually *implemented as* a plugin and its
`main()` *is* a skill — but almost no plugin is an agent app, and an agent app
can ship as a personal or project skill directory with no manifest at all. "An
agent app is a plugin" is a category error in the same way "a program is a
`.deb`" is.

**Is a given artifact an agent app?** Three cuts, in order — yes to all three:

1. **Is there a `main()` — something you invoke by name?** If it instead fires
   on context to change how the model works ("use uv, not pip"), nobody runs
   it; it runs on you. That is a **guidance skill**.
2. **Is the result yours?** An app delivers something you asked for. If running
   it reconfigures the harness instead, it is a **harness extension** — a hook,
   an MCP server, a statusline, an installer.
3. **Does the last step need judgment?** If everything is computable, the
   honest answer is a plain CLI, and this plugin will tell you so.

**Whether it ships a script is not one of the cuts.** That is implementation,
and the user never sees it. `roadmap` is an agent app implemented entirely in
prose; `check-chat` is one implemented in sixteen Python modules. The partition
rule below is advice on how to build an app well — not a test of whether
something is one.

This plugin is itself an agent app. `create` and `partition` are judgment and
live in prose; `lint` is mechanical, must be identical every run, and needs to
work in CI, so it is a script. A plugin that preached the partition and then
did its own lint in prose would be advertising against itself.

## Install

```
/plugin marketplace add dgutson/agent-app
/plugin install agent-app@agent-app-marketplace
```

## Commands

| | `create` | `lint` | `partition` |
|---|---|---|---|
| Question | what should this app be? | do the halves still agree? | is the line in the right place? |
| Kind | judgment | mechanical | judgment |
| Cost | a session | seconds | a careful read of both halves |
| Cadence | once | every change, and in CI | at design time, then rarely |
| Output | a new app | fixes | a proposed redesign |

**The order:** `create` once, at the start — it ends by running `lint`. Then
`lint` forever, on every change and in CI. Then `partition` only when lint
reports `rederive` findings you cannot dismiss, when the app feels wrong, or
before a significant extension.

If you only ever run one, run `lint`. It is the one whose findings accumulate
silently.

### The fourth entry is not a command

Typing `/agent-app:` shows a fourth entry, `agent-app`. **It is not a command
and you never need to type it.** There are three commands; that entry is the
shared rulebook they all load — the partition rules, the evidence contract, the
workflows — and it appears in the list only because Claude Code surfaces every
skill as `/<plugin>:<skill>`. Think of it as the library, not an entry point.

It also loads on its own when you ask a question it covers ("should this be a
script or a prompt?") with no command typed, which is why it stays a skill
rather than becoming an ordinary file.

Invoking it directly is harmless — you get the rulebook with no task attached.
It is documented rather than hidden because the harness has no setting for
this: `skillOverrides` in `settings.json` offers `user-invocable-only` (hides
it from the model, keeps the slash command) and `off` (hides it from both,
which would break the three commands that load it), but nothing that hides it
from you while keeping it available to the model.

### Why `partition` is not part of `lint`

Lint is cheap, deterministic, and safe on every commit. Partition costs a full
read of both halves and proposes a *redesign* rather than a fix. Folding a
session-length judgement into the check you want in CI means either running the
expensive thing constantly or never running it at all.

They are not disconnected, though, and the seam between them is the same rule
this plugin teaches: **finding the lines worth judging is mechanical; judging
them is not.** So the mechanical half lives in the linter as the `rederive`
check, and `partition` starts from that list rather than re-reading the app
from scratch. Lint hands partition its evidence, exactly as a tool hands its
skill evidence.

## The two failure modes

**Re-derivation** — the prose is doing work a script should do. The tells:
instructions to grep, count, compare versions, parse a format, or "check
whether". Each is a script nobody wrote. `partition` finds these.

**Unread evidence** — the tool computes something and no prose teaches the
model to read it. This is the one that actually happens, because it happens by
inaction: someone adds a field, and nobody revisits four hundred lines of
policy prose. The evidence is produced, paid for, and discarded at the judgment
layer. `lint` finds these.

The asymmetry is the point. Prose-referencing-code stays clean on its own,
because prose gets written with the code in view. Code-emitting-unread-fields
rots silently and forever.

## What the linter checks

```bash
python3 scripts/lint_agent_app.py --root <plugin-dir> [--json]
```

| Code | Check | Finds |
|---|---|---|
| `AA301` | `unread` | The tool emits a field; no prose tells the model how to read it. |
| `AA201` | `stale-ref` | The prose cites a symbol or flag the code does not have. |
| `AA101` `AA102` | `rederive` | Prose asking the model to *establish* something a script may owe. Candidates for `/agent-app:partition`, not defects. |
| `AA401` | `xref` | A cross-reference pointing at a section that is not there. |
| `AA501` `AA502` | `exit-code` | A status raised but undocumented, or documented but never raised. |
| `AA601` `AA602` | `command` | A command with no workflow, or a workflow with no command. |
| `AA001`–`AA005` | `frontmatter` | Missing or mismatched `name`/`description`. |

Exit `0` clean, `1` findings, `2` usage error. `--only` takes either a check or
a code; an unknown one is a usage error rather than an empty report.

### What it refuses to check

Checks are tiered by what they presuppose, and the tier is settled before
anything runs:

| Tier | Runs when | Checks |
|---|---|---|
| any skill | always | `frontmatter`, `xref`, `command` |
| an app | something is invoked by name | `rederive` |
| a tool half | first-party source exists to compare against | `unread`, `stale-ref`, `exit-code` |

A prose-only app therefore reports three checks as **not applicable** — a
distinct outcome from *not run*, because nothing went unmeasured. `rederive`
still runs, and on that shape it is the whole point of the report: it names the
facts a script should be establishing.

```
shape: 3 entry points, no first-party tool — the prose is the whole implementation
clean: 3 prose files, 0 source files — 3 checks not applicable

NOT APPLICABLE — these presuppose something this artifact does not have
  exit-code  no first-party tool, so there is no second half for the prose to
             disagree with
```

Point it at something with no entry point at all and it says so, instead of
reporting on a guidance skill as though it had fallen short of being an app:

```
shape: no entry point, no first-party tool
warning: nothing here is invoked by name — no commands, and no skill naming
         its own slash command. That is a guidance skill rather than an app,
         and only the checks that hold for any skill were run against it.
```

That warning is addressed to whoever aimed the linter. It is not a finding and
does not fail the run — there is nothing there for its author to fix.

The tiers key on measurement preconditions, never on a verdict. Deciding
whether an artifact *is* an agent app needs cuts #2 and #3, which are judgment;
`--json` carries a `classification` block with the mechanical half —
`entry_points`, `tools`, `harness_wired`, `emits_payload` — and stops there.

The console report is one line per finding, paths relative to the root, and
each rule's fix stated once — a rule that fires more than six times in a file
collapses to its subjects, and `--verbose` expands it again:

```
20 findings (17 errors, 3 warnings) in 6 files — 1 partial check, 1 note

commands/sync.md:6:1: warn AA101 asks the model to "check whether" — a script may owe this answer
deptool/model.py: error AA301 unread ×7
    context, matched_by, raw_pin, source_repo, installed_version,
    blast_radius, stored_fingerprint

fix by rule
  AA301  unread    ×17  teach it in the skill, or record why not in .agent-app-allow
  AA101  rederive  ×2   judge it with /agent-app:partition; if it stays, say why here

NOT CHECKED — a check that did not run in full is not one that passed
  partial  unread-recall  143 further dict-literal key(s) live outside the
                          payload-assembling file and were not examined ...
```

`--json` is the other channel, and the one to reason over: it carries `code`,
`check`, `severity`, `file`, `line`, `col`, `subject`, `message` and `hint` per
finding, so nothing has to be parsed back out of the rendered line, plus the
`classification` block above.

It reports what it **could not** check as prominently as what it found, in
`coverage.checks_skipped` — the evidence-key extractor is Python-only, and by
default it reads the module that assembles the payload rather than every
module, so it says how many keys it did not examine. A skipped check is not a
passing one. Each entry carries a `kind`: `not-run`, `partial`, `note`, or
`not-applicable`, and only the first three are gaps.

### Adopting it on an existing app

```bash
python3 scripts/lint_agent_app.py --root . --init-allow
```

This baselines every currently-unread field into `.agent-app-allow`, so the app
is green *now* and every field added *later* must be classified. Each line
carries a `TODO` until somebody replaces it with a reason. The file is a to-do
list, not an absolution.

The same file also holds identifiers the prose cites without owning — another
app's fields quoted as examples. One flat list, because both are the same act:
recording that somebody looked.

## Reference implementation

[update-tools](https://github.com/dgutson/update-tools) — `deptool` finds the
dependencies, extracts the consumed symbols, diffs the public headers, and
checks the advisories; the `dep-review` skill decides what is worth acting on
and says why. Roughly 6,200 lines of Python under 400 lines of prose `main()`.

## Prior art

The topology has names. [LLM-as-Code](https://arxiv.org/html/2606.15874v1)
calls it *LLM-as-Orchestrator* and argues against it — a critique that lands on
skills where the prose does the sequencing, and much less on ones where the
prose is policy and the sequencing already lives in code and exit statuses.
Anthropic's skill-authoring guidance frames the same split as keeping the
*interpretive surface* separate from the *deterministic* one. Neither names the
whole artifact, which is what this plugin is about.

## License

MIT
