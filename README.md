# agent-app

> **An agent app is a console app whose `main()` is a skill.**

You run it by name, it does the job, it hands back a result. **From the outside
it is indistinguishable from any other program on the system** — `deptool
review` is the same kind of thing as `ls -l`. How you invoke it, what it prints,
what its exit status means, whether you can pipe it: none of that reveals that a
model ran the last mile, and ideally you never find out.

That holds at the call site too. An agent app is meant to be invoked **both
interactively at a terminal and non-interactively from a script** — a bash
script, a Makefile rule, a git hook, a cron job, a CI step — with nobody in the
loop to read a transcript. The caller passes arguments, reads stdout and branches
on the exit status, exactly as it would with any other program.

**Where that stands today:** both work. Interactively an agent app is a slash
command in a Claude Code session. From a script it is an executable file — a
`#!/usr/bin/env agent-app-launcher` shebang over a short YAML body naming the
app — which resolves the app, runs it headless, and exits on what it concluded:
`0` clean, `1` findings, `2` usage, `3` refused, `4` failed, `5` no verdict.
`claude -p` cannot do that last part on its own, since it exits 0 for any
session that completed whatever the session decided, so the launcher owns the
status. `--help` is answered from the app's own declaration with no model
started at all. See [the `.ag` format](launcher/ag-format.md) — though until
there is an installer, the launcher needs one symlink onto `PATH`.

Most agent apps have two halves. The bundled tool establishes every fact that is
mechanically establishable; the prose supplies the one thing a script cannot —
judgment, and honesty about how far the evidence supports it. Dividing them well
is what this plugin is for, and the reason is not tidiness: **every fact you move
into the script is one less place the model shows through.** The part of the
illusion that cannot hold yet is repeatability — same input, same output — which
is exactly the pressure to push everything determinable down into the tool.

## Skill, plugin, agent app

Three words that get used interchangeably and name different things. Only one of
them names a shape.

| | What it is | How it relates |
|---|---|---|
| **agent app** | a kind of program | the thing being built |
| **plugin** | a distribution format: a manifest plus any of commands, skills, hooks, MCP servers | how an agent app is usually shipped |
| **skill** | a unit of instruction the model loads | what an agent app's `main()` is |

Both relations run one way only, and that is the whole of the confusion:

- **An agent app is usually implemented as a plugin, and almost no plugin is an
  agent app.** Most plugins ship hooks, MCP servers or standing guidance; nobody
  runs those, they run on you. An agent app can equally ship as a personal or
  project skill directory with no manifest at all. "An agent app is a plugin" is
  a category error in the same way "a program is a `.deb`" is.
- **An agent app's `main()` is a skill, and almost no skill is any app's
  `main()`.** A skill that fires on context to change how the model works ("use
  uv, not pip") is guidance; a skill somebody invokes by name and gets a result
  from is an entry point.

**Is a given artifact an agent app?** Three cuts, in order — yes to all three:

1. **Something is invoked by name.** If it instead fires on context, nobody runs
   it; it runs on you. That is a **guidance skill**.
2. **The result is yours.** If running it reconfigures the harness rather than
   delivering something you asked for, it is a **harness extension** — a hook,
   an MCP server, a statusline, an installer.
3. **The last step needs judgment.** If everything is computable, the honest
   answer is a plain CLI, and this plugin will tell you so.

**Whether it ships a script is not one of the cuts.** That is implementation,
and the user never sees it. `roadmap` is an agent app written entirely in prose;
`check-chat` is one written in sixteen Python modules.

**`agent-app` is itself an agent app — one whose subject is building agent
apps**, and it is built by the rules it teaches. `create` and `partition` are
judgment, so they live in prose; `lint` is mechanical, must be identical every
run and has to work in CI, so it is a script. It also lints itself before any
change ships: a plugin that preached the partition and then failed its own check
would be arguing against itself.

## Install

```
/plugin marketplace add dgutson/agent-app
/plugin install agent-app@agent-app-marketplace
```

## The workflow

Three commands, in the order an app meets them.

1. **`/agent-app:create`** — once, at the start. It settles the partition with
   you before anything is scaffolded, designs the tool's evidence contract, then
   writes both halves. It ends by running `lint`.
2. **`/agent-app:lint`** — from then on, on every change and in CI. Seconds,
   deterministic, and read-only with respect to the app: it reports, it does not
   fix.
3. **`/agent-app:partition`** — when `lint` reports `rederive` findings you
   cannot dismiss, when the app feels wrong, or before a significant extension.
   It reads both halves and proposes a redesign rather than a fix.

| | `create` | `lint` | `partition` |
|---|---|---|---|
| Kind | judgment | mechanical | judgment |
| Cost | a session | seconds | a careful read of both halves |
| Cadence | once | every change, and in CI | at design time, then rarely |
| Output | a new app | findings | a proposed redesign |

If you only ever run one, run `lint`. It is the one whose findings accumulate
silently.

`partition` is deliberately not folded into `lint`: a session-length judgement
inside the check you want on every commit means either running the expensive
thing constantly or never running it at all. They meet at the same rule this
plugin teaches — **finding the lines worth judging is mechanical; judging them is
not** — so the linter's `rederive` check produces the list and `partition` starts
from it. Lint hands partition its evidence, exactly as a tool hands its skill
evidence.

### The fourth entry is not a command

Typing `/agent-app:` shows a fourth entry, `agent-app`. **It is not a command and
you never need to type it.** There are three commands; that entry is the rulebook
they all load, and it appears only because Claude Code surfaces every skill as
`/<plugin>:<skill>`. It also loads on its own when you ask something it covers
("should this be a script or a prompt?") with no command typed, which is why it
stays a skill rather than an ordinary file. Invoking it directly is harmless: you
get the rulebook with no task attached.

## The two failure modes

**Re-derivation** — the prose is doing work a script should do. The tells:
instructions to grep, count, compare versions, parse a format, or "check
whether". Each is a script nobody wrote. `partition` fixes these.

**Unread evidence** — the tool computes something and no prose teaches the model
to read it. This is the one that actually happens, because it happens by
inaction: someone adds a field, nobody revisits four hundred lines of policy
prose, and the evidence is produced, paid for and discarded at the judgment
layer. `lint` finds these.

The asymmetry is the point. Prose gets written with the code in view, so
prose-referencing-code stays clean on its own; code-emitting-unread-fields rots
silently and forever.

## Using the linter

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

| Flag | What it does |
|---|---|
| `--root` | Directory to check. Defaults to cwd. |
| `--json` | Findings plus `classification` and `coverage`. The channel to reason over. |
| `--only` | One check or one rule code. An unknown value is a usage error, not an empty report. |
| `--init-allow` | Baseline every currently-unread field into `.agent-app-allow`, then exit. |
| `--wide` | Extract evidence keys from every module, not just the one writing the payload. |
| `--verbose` | Print every finding; without it, a rule firing more than six times in a file collapses to its subjects. |

Exit `0` clean, `1` findings, `2` usage error. The script has no model in it, so
it is the half that already works from a bash script or a CI step with no Claude
Code session anywhere — non-zero on findings, identical every run.

Checks are tiered by what they presuppose, never by a verdict. `frontmatter`,
`xref` and `command` run against any skill; `rederive` needs an entry point;
`unread`, `stale-ref` and `exit-code` need first-party source to compare against.
So a prose-only app reports three checks **not applicable** — a distinct outcome
from *not run*, because nothing went unmeasured. Aimed at something with no entry
point at all, it says that too, rather than reporting on a guidance skill as
though it had fallen short of being an app.

`--json` carries `code`, `check`, `severity`, `file`, `line`, `col`, `subject`,
`message` and `hint` per finding, so nothing has to be parsed back out of a
rendered line. Alongside them: `classification` — `entry_points`, `tools`,
`harness_wired`, `emits_payload` — which establishes the mechanical half of the
three cuts and stops short of the verdict, since cuts #2 and #3 are judgment; and
`coverage`, which reports what could not be checked as prominently as what was
found. A skipped check is not a passing one.

**Adopting it on an existing app:** `--init-allow` writes every currently-unread
field into `.agent-app-allow`, so the app is green *now* and every field added
*later* must be classified. Each line carries a `TODO` until somebody replaces it
with a reason — the file is a to-do list, not an absolution. It also holds
identifiers the prose cites without owning, since both are the same act:
recording that somebody looked.

## Reference implementation

[update-tools](https://github.com/dgutson/update-tools) — `deptool` finds the
dependencies, extracts the consumed symbols, diffs the public headers and checks
the advisories; the `dep-review` skill decides what is worth acting on and says
why. Roughly 6,200 lines of Python under 400 lines of prose `main()`.

## Prior art

The topology has names. [LLM-as-Code](https://arxiv.org/html/2606.15874v1) calls
it *LLM-as-Orchestrator* and argues against it — a critique aimed at skills where
the prose does the sequencing, much less at ones where the prose is policy and
the sequencing lives in code and exit statuses. Anthropic's skill-authoring
guidance frames the same split as keeping the *interpretive* surface separate
from the *deterministic* one. Neither names the whole artifact, which is what
this plugin is about.

## License

MIT
