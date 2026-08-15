# Roadmap

> Pending work only — finished items move to HISTORY.md.
> This is the durable record of what's outstanding. Read it instead of reconstructing
> the state of play from git history, old conversations, or a sweep of the code.
> Next thing to work on: the first item under the earliest horizon whose **Blocked-by**
> entries are no longer present in this file.

Format: 1
Next ID: R-021

---

## Now

### R-014 — Agent apps run from a shell: the shebang, and the exit status behind it

- **Category:** Invocation
- **What:** Make an agent app executable. A file whose first line is
  `#!/usr/bin/env agent-app-launcher` — body either the SKILL.md itself or a short
  manifest naming an installed app — becomes a program, so that `roadmap --list` and
  `ls -l` are the same kind of thing to the user and to a script. **Subsumes R-004**
  (headless invocation), which was never a separable deliverable: see **Why**.

  Three parts, in this order, because each decides the next:

  1. **The result channel** — R-004's question, and the one that has to be answered in
     writing before any launcher is written, since it *is* the launcher's exit path.
     Establish whether `claude -p` can propagate a verdict as an exit status; if it
     cannot, define the convention (a JSON verdict on stdout via `--output-format json`,
     or a file the app writes), plus a documented `--max-turns` and timeout. Measured
     previously: `claude -p "Reply with exactly: PONG"` returns in 4s with exit 0, and
     `claude -p "/agent-app:lint"` in `update-tools` was still working at 180s when a
     `timeout` killed it (SIGTERM, rc 143) — so the slash command resolves headless and
     the delay is real judgment work, not a failure to dispatch. Do not conclude from
     that timeout that headless invocation is broken; budget minutes, not seconds.
  2. **The launcher.** Resolve the named app, map the command line onto its verbs, run
     it headless, exit per (1). **stdout carries the app's output only** — no session
     chatter — so it survives a pipe.
  3. **The argument surface.** Which verbs exist and what flags they take has to be
     *declared* — in frontmatter, or by the `commands/` names — not inferred from prose
     at run time. `--help` must answer without invoking the model at all: it is a
     determinable fact, so by this plugin's own partition rule the launcher owes it.

  **Whether the app has a tool half is irrelevant here.** A prose-only app gets a
  command line exactly like a Python-backed one. The caller cannot tell, and that being
  invisible is the whole point.
- **Why:** This is the definition made executable. R-013 (delivered — see HISTORY.md)
  settled that an agent app is a console app whose `main()` is a skill, but today that
  `main()` can only be reached by typing a slash command into a REPL — which leaves the
  claim aspirational and the user aware at every moment that something unusual is
  happening. A shebang makes it literal: agent apps compose with pipes, `cron`,
  Makefiles, git hooks and other programs, and stop being things you can only run inside
  a chat. Today `claude -p` exits 0 for a completed session regardless of what the agent
  concluded, so CI cannot gate on "the lint found errors" — while `lint_agent_app.py`
  alone already exits 1 and is usable in CI now.

  **Why R-004 is not a separate item.** It could otherwise be marked done with a
  documented convention that nothing exercises, and a convention with no caller is a
  guess — which is this plugin's own "unmeasured is not clean" rule turned on its
  roadmap. The launcher is the first thing that must branch on that status, so it is
  also the only thing that can show the answer was right. The dependency is total in one
  direction (no launcher can exist without an exit status) and the standalone value in
  the other is a strictly weaker version of the same goal: a hand-written
  `claude -p "/roadmap:list"` invocation with a convention the user has to remember.
- **Outcome:** `./some-app --verb` runs an agent app from a shell and from a script, its
  exit status is branchable, `--help` answers with no model in the loop, and nothing in
  the invocation reveals whether the app is implemented in prose or in Python. Each app
  `/agent-app:create` generates ships with that invocation.
- **Blocked-by:** —
- **Enables:** —

### R-010 — Say plainly that `/agent-app:agent-app` is not a command

- **Category:** Scaffolding
- **What:** **No rename, and no deletion.** The entry stays and the plugin explains it.
  The README half is written (see *The fourth entry is not a command*); two changes
  remain, both inside the plugin so they ship with it rather than needing per-machine
  setup:
  1. **Front-load the skill's `description`** with what the entry is — "Internal rulebook
     for the agent-app plugin; not a command — use `/agent-app:create`, `:lint` or
     `:partition`" — and keep the existing trigger phrases after it. The completion list
     shows the description beside the slug, so this is the only text that reaches
     somebody at the moment they are typing `/agent-app:`. Do not gut the trigger
     phrases: the same field routes automatic invocation, and losing it would stop the
     skill firing on "should this be a script or prose?" with no command typed.
  2. **Make direct invocation a signpost, not a manual dump.** First instruction in the
     body: if invoked with no task attached, name the three commands and stop.
- **Why:** `/agent-app:agent-app` reads as a typo, and the user never needs to type it —
  it is the rulebook the three commands share, surfaced as an entry only because Claude
  Code makes every skill invocable as `/<plugin>:<skill>`. Three fixes were investigated
  and rejected; record the findings so nobody re-opens them:

  **Renaming** was the original proposal and is explicitly not wanted. A better word
  still reads as a fourth command, which is the actual confusion — the problem is not the
  name, it is that the entry is not a command at all.

  **Hiding it is not possible in the direction required.** `skillOverrides` in
  `settings.json`, keyed by skill name, offers `name-only` (lists it without its
  description), `user-invocable-only` (hides it from the model, keeps the slash command)
  and `off` (hides it from both). There is no mode that hides it from the user while
  keeping it loadable by the model, and `off` would break the three commands that load
  it. It is a user-side setting in any case, so a published plugin cannot ship it. No
  frontmatter flag does this either: across 46 installed skills on this machine the only
  keys in use are `name`, `description`, `disable-model-invocation` and `tools`, and
  `disable-model-invocation` blocks the model while keeping the user's slash command —
  again the wrong direction.

  **Deleting the skill** and copying its content into the three command files was
  rejected earlier: three copies of the partition rules and the evidence contract that
  can disagree with nothing able to detect it, in a plugin whose entire subject is prose
  drifting out of agreement with code. It is also not a token saving — today a command
  loads a short file plus the skill; with copies it loads one long file, at roughly the
  same cost.
- **Outcome:** Somebody typing `/agent-app:` can tell from the completion list which
  entries are commands and which one is the rulebook, and invoking the rulebook directly
  answers with the command list instead of the doctrine.
- **Blocked-by:** —
- **Enables:** —

### R-008 — Persist lint findings so the fix step need not re-run the lint

- **Category:** Commands
- **What:** Add `--emit <path>` to `lint_agent_app.py`: write the findings payload — the
  same structure `--json` prints — to a file, alongside a content hash of every prose
  and source file the run read, so a consumer can tell whether the findings still
  describe the tree. Default the path to the inspected root, since that is where the
  user will look for it. `/agent-app:lint` keeps printing the human report to the
  console exactly as now; the file is the machine channel, the console is the human one.
  **The agent still gets no `Edit` or `Write`** — the script writes its own output when
  invoked through `Bash`, the way `checkchat --emit` already does.
- **Why:** `/agent-app:lint` and the fix step would otherwise each run the linter and
  each pull the full finding set into context — the second time for no new information.
  On `update-tools` that is 18 findings plus a coverage block, paid twice, and the two
  disagree whenever the tree moves between them. The read-only rule is not violated by
  this, because that rule protects **the agent app under inspection** — its SKILL.md,
  its commands, its scripts, its `.agent-app-allow` — and not the filesystem in general.
  A generated findings file is output, not a modification of anyone's source; whether it
  gets committed or gitignored is the user's call.
- **Outcome:** The fix step obtains the findings without re-running the analysis and can
  detect that they are stale before acting. `/agent-app:lint` still cannot alter the app
  it inspects.
- **Blocked-by:** —
- **Enables:** R-007

### R-007 — `/agent-app:fix-findings` command

- **Category:** Commands
- **What:** Add `commands/fix-findings.md`, the writing counterpart to `/agent-app:lint`.
  R-008 makes **lint the producer** of the findings file; **this command is the sole
  consumer** of it, and never re-runs the analysis itself. It reads that file (refusing,
  and saying so, if the recorded hashes no longer match the tree), shows the user what it
  proposes to change, gets confirmation, then applies: teaching an `unread` field into the SKILL.md,
  writing a justified `.agent-app-allow` entry, running `--init-allow` to baseline,
  repairing an `xref`, documenting an undocumented exit code. It gets `Edit` and `Write`;
  `/agent-app:lint` does not. Never touch a `rederive` finding here — moving the
  partition is a redesign and belongs to `/agent-app:partition`.
- **Why:** `/agent-app:lint` shipped with `Edit, Write` in `allowed-tools` and "apply
  the fixes" in its steps, and on its first real run against `update-tools` it rewrote
  `skills/dep-review/SKILL.md` (+237/-8) and created `.agent-app-allow` in a repository
  the user had only asked for a report on. The command is now strictly read-only, which
  leaves the fixing half with nowhere to live. The fixes are still worth applying — they
  just have to be asked for.
- **Outcome:** Applying lint findings is possible in one command, and impossible without
  explicitly invoking it.
- **Blocked-by:** R-008
- **Enables:** —

### R-003 — Conformance marker: an artifact that declares it is an agent app

- **Category:** Scaffolding
- **What:** Make `/agent-app:create` record that what it produced *is* an agent app.
  Decide the carrier and write it into `commands/create.md`: a line in the generated
  `CLAUDE.md`, a key in `.claude-plugin/plugin.json`, or both. Machine-readable beats
  prose, because R-001 has to detect it. Two decisions R-013 already settled, to
  implement rather than re-open:
  - **The marker asserts conformance, not provenance.** "This is an agent app", not
    "this plugin generated it". Provenance is a credit line; conformance is the only
    claim that answers *what is this*, and it is the one a linter and a lister can act
    on. It follows that a hand-written app may carry the marker, and that an app this
    plugin generated may later lose the right to it.
  - **A marked artifact with no tool half is an error**, not a warning. It made a claim
    it does not meet, which is a different situation from someone aiming this linter at
    a guidance skill — that stays an unscored invocation warning. Add the rule to
    `lint_agent_app.py` when the marker exists; today nothing carries one, so the
    linter cannot yet tell the two apart.
- **Why:** R-013 established that structure cannot decide identity: whether something is
  an agent app turns on what running it delivers and to whom, and a prose-only app is as
  much an app as a Python-backed one. The linter's `classification` block therefore stops
  at the mechanical half — `entry_points`, `tools`, `harness_wired`, `emits_payload` —
  and refuses the verdict. That refusal is correct, and it leaves exactly one way to
  learn the answer without re-reading and re-judging every plugin: let the artifact say
  so. The marker is no longer a nicety; it is the only channel the verdict has.
- **Outcome:** Every app produced by `/agent-app:create` carries a marker a script can
  find without parsing prose, `commands/create.md` states which file carries it, and the
  linter reports a marked artifact with no tool half as an error.
- **Blocked-by:** —
- **Enables:** R-001

### R-015 — `/agent-app:list-cmds`, and the local/global naming rule it establishes

- **Category:** Commands
- **What:** Add a command that answers "what can I invoke in *this* app" for the app in
  the current directory (or `$1`): enumerate its `commands/*.md` and its skills, read each
  `description` from frontmatter, print slug and one line each. **Mechanical throughout,
  so it belongs in `lint_agent_app.py` or a sibling script** — the prose does nothing but
  invoke it, which is this plugin's own partition rule applied to itself.

  It also fixes the convention every later command follows:

  > **Local is the default and carries no suffix. A command that reaches outside the
  > current directory says so in its name.**

  `create`, `lint`, `partition` and `list-cmds` all act on the app you are standing in.
  `list-installed` (R-001) is the only one that does not, which is why it is the only one
  that is suffixed. Write the rule into the SKILL.md so a fifth command does not have to
  guess, and check the whole set against it before adding one.
- **Why:** Today nothing tells you what an agent app in front of you can do without
  reading its plugin manifest or its SKILL.md by hand — and `/agent-app:` shows the
  plugin's *own* commands, not the ones belonging to the app under inspection, which is
  precisely the confusion the naming rule exists to end. It is also the cheapest possible
  demonstration that the rule is real: two commands whose names differ by scope, next to
  each other in the same completion list.

  **Overlaps R-002 and R-014 part 3 deliberately, and must not fork from them.** R-002
  makes each *generated* app answer `/<name>:help` about itself; R-014 makes the launcher
  answer `--help` at the shell; this answers about whatever app you are standing in,
  including apps that predate both and will never carry either. Three surfaces, one
  source: the app's declared verbs. Whichever lands first owns that declaration, and the
  others render it.
- **Outcome:** `/agent-app:list-cmds` prints the current app's commands with one line
  each, and the SKILL.md states the local/global naming rule that every command in the
  plugin can be checked against.
- **Blocked-by:** —
- **Enables:** —

## Next

### R-009 — Linter check: a reporting command must not hold write grants

- **Category:** Linting
- **What:** Add a check that cross-reads each `commands/*.md` frontmatter against its
  body: if the description or body presents the command as reporting — report, list,
  show, check, review, audit, inspect, "read-only" — and `allowed-tools` grants `Edit`
  or `Write`, report it. Also the converse: a command whose body says it applies or
  writes but which holds neither grant will fail at runtime.
- **Why:** `/agent-app:lint` shipped with exactly this defect and edited a user's
  repository on its first real run. The grants were fixed by hand, and `commands/*.md`
  now carries a prose rule telling authors to split inspect from change — but prose is
  the mechanism that already failed once. This is a mechanically checkable property, so
  by this plugin's own partition rule it belongs in the script. It also covers commands
  added long after `/agent-app:create` ran, which the create-time instruction cannot.
- **Outcome:** A command that claims to report while holding write grants fails the lint.
- **Blocked-by:** —
- **Enables:** —

### R-012 — SARIF output, so a finding can land in code review

- **Category:** Linting
- **What:** Add `--format sarif` to `lint_agent_app.py`, emitting SARIF 2.1.0:
  `runs[].tool.driver.rules[]` built from the `RULES` registry — `id`, `name`, and `help`
  from the fix hint — and one `result` per finding with `ruleId`, `level` mapped from
  `severity`, and a `physicalLocation` carrying `artifactLocation.uri` (the repo-relative
  `file`) plus `region.startLine` / `startColumn`. Map the coverage gaps to
  `invocations[].toolExecutionNotifications`, so a check that did not run is visible in
  the upload rather than absent from it. Decide at the same time whether `--format`
  subsumes R-008's `--emit`, rather than growing two unrelated file-writing flags.
- **Why:** The two pieces SARIF needs now exist and did not before R-011: stable rule
  codes, and `file` / `line` / `col` as fields rather than a rendered string. SARIF is
  what GitHub code scanning, the VS Code viewer and Azure DevOps already read, so this is
  how a finding reaches a pull request as an annotation instead of a log line somebody
  has to scroll past. It also forces a decision the console dodges: a finding with a
  `null` line or column needs a stated mapping, because inventing a position to satisfy
  the schema is the exact defect this linter reports in other people's tools. R-014 wants
  a CI story for agent apps; this is the half of it that does not wait on `claude -p`
  learning to propagate a verdict.
- **Outcome:** `lint_agent_app.py --format sarif` produces a file GitHub's code-scanning
  upload accepts, each finding carrying its `AAxxx` as `ruleId`, and unrun or partial
  checks appearing as notifications rather than silently not existing.
- **Blocked-by:** —
- **Enables:** —

### R-002 — Generated agent apps ship a `help` command

- **Category:** Scaffolding
- **What:** Make `/agent-app:create` emit a `commands/help.md` for every new app, listing
  its commands with one line each and pointing at the skill. Add a linter check that an
  app with two or more commands has one, so the convention is enforced rather than
  merely recommended.
- **Why:** A CLI answers `--help`; an agent app has no equivalent, so a user who installs
  one has to read the plugin's README or its SKILL.md to find out what they can invoke.
  The plugin's own three commands are already past the point where that is obvious.

  **Overlaps R-014 and R-015 deliberately, and must not fork from either.** R-014 makes
  the launcher answer `--help` at the shell from the app's declared verbs, with no model
  in the loop; R-015 answers about whatever app the user is standing in; this is the same
  list surfaced inside a generated app's own session as `/<name>:help`. Three surfaces,
  one source — whichever lands first owns the declaration and the others render it, so if
  R-014 goes first this becomes "render the declared verbs as a command" rather than
  "write a help file", and the linter check moves to *declared verbs exist*.
- **Outcome:** Every generated app answers `/<name>:help` with its own command list, and
  the linter reports an app that has commands but no `help`.
- **Blocked-by:** —
- **Enables:** —

### R-005 — Delegate description tuning and evals to `skill-creator`

- **Category:** Scaffolding
- **What:** Add a step to `commands/create.md` that hands the generated SKILL.md's
  `description` to the `skill-creator` skill for trigger tuning and eval runs when it is
  installed, and states plainly what is skipped when it is not. Do not reimplement either.
- **Why:** `/agent-app:create` writes a `description` with no guidance on making it
  route correctly, which is the field that decides whether the skill ever fires.
  `skill-creator` and `plugin-dev` already do that well, and `claude plugin eval` exists
  for measurement. Duplicating them would produce a second, worse copy; saying nothing
  leaves a hole in the workflow. No `dependencies` field was found in any plugin.json on
  this machine, so this is a documented soft dependency, not a declared one.
- **Outcome:** `/agent-app:create` either runs the description through `skill-creator` or
  tells the user which step it is skipping and why.
- **Blocked-by:** —
- **Enables:** —

### R-016 — Evaluate `/agent-app:create-installer`: agent apps that install themselves

- **Category:** Scaffolding
- **What:** **Decide first, build second — the deliverable may legitimately be "no".**
  The question: should `/agent-app:create` emit an installer for the app it generates,
  and should this plugin ship one for itself? Once R-014 lands, `agent-app` stops being
  a thing you only install through `/plugin install`: it puts `agent-app-launcher`
  somewhere on `PATH`, which is a change to the user's system and not to their Claude
  Code configuration. Points to settle:
  - **What an installer is allowed to touch**, and what it must ask before touching.
    `PATH` entries, a shell rc file, a completion script (R-017), a symlink per app.
  - **Where things go.** `~/.local/bin` versus a system prefix; per-user by default,
    because a plugin that needs `sudo` to install is a plugin most people will not.
  - **Verify and uninstall are not optional.** `claude-sudo-askpass` on this machine is
    the local precedent worth reading: idempotent, `--verify` changes nothing, `--force`
    reinstalls, and it refuses cleanly when the environment cannot support it.
  - **The generated installer is not itself an agent app**, by this plugin's own cut #2:
    its result is a change to the user's system rather than an answer to their question.
    Say so in whatever gets generated, or `/agent-app:list-installed` will end up
    counting installers.
- **Why:** R-014 turns this plugin into something with a footprint outside Claude Code,
  and a launcher nobody can install is a launcher nobody runs. Doing it by hand-written
  README instructions is how installations end up half-done and unremovable. Whether
  *generated* apps need the same machinery is the genuinely open half: most will not, and
  emitting an installer for an app that only ships a skill would be scaffolding nobody
  asked for.
- **Outcome:** A written decision on whether generated apps get installers and on what an
  installer may do unasked — and, if the answer is yes, `agent-app` itself installs,
  verifies and uninstalls its launcher without leaving anything behind.
- **Blocked-by:** R-014
- **Enables:** R-017

### R-017 — Shell completion for the launcher, bash at minimum

- **Category:** Invocation
- **What:** Make `agent-app-launcher` and the apps it fronts complete at the terminal:
  app names, then that app's verbs, then that verb's flags. Bash is the floor; zsh and
  fish if they come cheaply from the same declaration. The completion script is generated
  from the **declared** verb surface R-014 part 3 establishes — never by running the app,
  and never by parsing prose, since completion has to answer in milliseconds with no
  model anywhere near it. R-016's installer is what puts the script where the shell will
  read it.
- **Why:** The claim R-013 settled is that an agent app is a console app whose `main()`
  is a skill, and R-014 makes that literal at the prompt. Completion is the part of "it
  behaves like `ls`" that users actually feel: a program you must remember the verbs of
  is a program that reads as unfinished, however well it runs. It is also a forcing
  function on R-014's declaration — a verb surface that cannot generate a completion
  script was never really declared.
- **Outcome:** Typing an agent app's name and pressing Tab completes its verbs, and the
  completion script is generated from the same declaration `--help` renders.
- **Blocked-by:** R-014
- **Enables:** —

### R-018 — Tune the reasoning effort each command asks for

- **Category:** Invocation
- **What:** Investigate, then implement, per-command effort — `/agent-app:tune-cmds-effort`
  if it turns out to need a command of its own. Two questions, and the first is not yet
  answered here:
  1. **How to launch a command at a stated effort, independent of the effort the calling
     chat is running at.** Confirmed possible, but not by this session. **The `roadmap`
     skill is being changed to do exactly this in a parallel session as of 2026-08-15 —
     read how it ended up doing it, and do not re-derive the mechanism.** Do not
     investigate before that work lands; reading it mid-change is how two sessions
     produce two different answers.
  2. **Which effort each command actually needs.** `lint` relays a script's findings and
     should be cheap; `partition` reads both halves and argues about a design, and
     starving it produces a review that manufactures findings to look thorough — the
     exact failure the skill's honesty rules warn about. `create` is a session-long
     design conversation. These are guesses until measured: record the numbers rather
     than asserting the ranking.
- **Why:** Every command in this plugin currently inherits whatever effort the chat
  happens to be at, which is wrong in both directions — a `lint` that relays JSON burns
  reasoning it has no use for, and a `partition` run from a cheap session gives shallow
  judgment on the one command whose entire value is judgment. Effort is a property of the
  task, not of the conversation that happened to launch it. It also compounds with R-014:
  a launcher invoking apps headless has no chat effort to inherit and must state one.
- **Outcome:** Each command declares the effort it runs at, that declaration survives
  being invoked from a chat at a different effort, and the choice per command is backed
  by a measurement rather than an intuition.
- **Blocked-by:** —
- **Enables:** —

### R-019 — Evaluate `/agent-app:update-local`: making edits take effect on this machine

- **Category:** Invocation
- **What:** **Evaluate, and the expected answer is "not a command".** Measured 2026-08-15:
  the installed copy at `~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/` is a
  plain directory copy, not a symlink to the source, so edits to a working tree do not
  take effect until the plugin is refreshed. The refresh already exists as two CLI verbs:

  ```
  claude plugin marketplace update <marketplace> && claude plugin update <plugin>
  ```

  followed by a restart. Wrapping two commands that already work is what this plugin's
  own cut #3 tells everyone else not to do, so the deliverable is probably documentation
  plus **one mechanical piece that genuinely is missing: knowing whether you need to.**
  Nothing today reports that the installed copy has fallen behind the source — this
  session found out by grepping the cached SKILL.md for a heading. Content-hash the
  source tree against the installed copy and report *stale* or *current* in one line,
  which is the SKILL.md's own "staleness is a computed fact, not a vibe" rule turned on
  the plugin itself. Settle where it belongs: a `--check-installed` flag on the linter,
  a line in the lint report, or nothing at all.
- **Why:** A plugin whose source and installed copy silently disagree produces the worst
  kind of debugging session — you fix something, re-run, and observe the old behaviour
  with no indication why. This repo lints itself as a matter of policy, and it currently
  lints the *source* while the model runs the *copy*, which means a clean self-lint does
  not establish that the thing actually loaded is clean. That gap is real regardless of
  whether the refresh gets a command. R-016's installer will need the same answer for
  whatever it puts on `PATH`.
- **Outcome:** A written decision on whether the refresh gets a command, and — if the
  staleness check survives the evaluation — one line that says whether what is installed
  matches what is on disk.
- **Blocked-by:** —
- **Enables:** —

### R-020 — Evaluate `/agent-app:upload-to-repo`: is there a release step worth owning?

- **Category:** Distribution
- **What:** **Evaluate, and split the question in two, because the halves have different
  answers.** The *git* half — stage, commit, push, open a PR — is generic, is not this
  plugin's subject, and is already done natively by Claude Code, with packaged
  alternatives available if the user wants them. Building it here would be a second,
  worse copy of a solved problem, which is the same argument this plugin makes against
  reimplementing `skill-creator` in R-005.

  The *release* half is the part that might be worth owning, and most of it also already
  exists: `claude plugin validate <path>` checks the manifest and the skills, agents and
  commands, and `claude plugin tag [path]` creates a `{name}--v{version}` tag while
  validating that `plugin.json` and the enclosing marketplace entry agree. So the
  genuinely agent-app-specific residue is small, and worth naming precisely:
  - **the lint must exit 0** before anything is tagged or pushed — this repo's own
    standing rule, currently enforced by nobody;
  - the version in `plugin.json` was bumped when the prose or the tool changed;
  - HISTORY.md records what shipped, since removal from ROADMAP.md is what "done" means
    here and a release with no HISTORY line loses that.

  Decide whether that residue is a command, a `commands/release.md` checklist, or three
  lines folded into R-006.
- **Why:** Asked as "commit and push", the answer is no — and saying so is worth more
  than building it, since this plugin's whole doctrine is that an agent app wrapped
  around a complete tool is pure overhead. Asked as "do not publish a plugin whose own
  linter fails", the answer is plausibly yes, and that gate has no home today: R-006
  will push whatever is in the tree at the time.
- **Outcome:** A written decision naming which of commit/push, validate/tag, and the
  lint-clean gate this plugin owns — and, for whatever it does own, where that lives.
- **Blocked-by:** —
- **Enables:** —

## Later

### R-006 — Publish to GitHub as `dgutson/agent-app`

- **Category:** Distribution
- **What:** `git init`, commit, create the repository, push, and re-point the marketplace
  from the local directory source to the GitHub source. `plugin.json` already declares
  `homepage` and `repository` as `github.com/dgutson/agent-app`.
- **Why:** Deferred deliberately: at the time, the linter had only ever run against two
  apps. It has since run against seven, which fixed three real defects (`xref` was wrong
  on four of five real-world cases, missing-`name` was over-severe, duplicate skip
  entries). Publishing is what makes the plugin installable on another machine and by
  anyone else; until then the local directory marketplace covers this machine only.

  **R-010 no longer blocks this.** It blocked publication while it proposed renaming a
  command, since renaming after strangers have installed it breaks their muscle memory.
  R-010 is now documentation only, and documentation can land after publication without
  breaking anyone.
- **Outcome:** `agent-app` installs from GitHub the way the other `dgutson/*` plugins do.
- **Blocked-by:** —
- **Enables:** —

### R-001 — `/agent-app:list-installed` command

- **Category:** Commands
- **What:** Add a `list-installed` verb to `scripts/lint_agent_app.py` (or a sibling
  script) that enumerates installed plugins from
  `~/.claude/plugins/installed_plugins.json` and
  reports which are agent apps, with the R-003 marker as the primary signal. For the
  unmarked — which includes every app predating this plugin, such as `update-tools` —
  the fallback is **not** a structural heuristic. R-013 killed the one this item used to
  propose (`skills/` plus executables under `scripts/`): it classified
  `claude-sudo-askpass`, a hook helper and an installer, as an agent app on the first
  case anybody checked, and it would have missed `roadmap`, which is an app with no
  script at all. Use the linter's `classification` block instead — `entry_points`,
  `tools`, `harness_wired`, `emits_payload` — and have the model finish cuts #2 and #3
  from those signals, reporting its verdict *as* a judgment, distinct from a marker's
  declaration. Add `commands/list-installed.md` and a workflow section in the SKILL.md.

  **Named for the scope it works at**, per the convention stated in R-015: this is the
  one command in the plugin that reaches outside the current directory, so it says so.
  Every other command acts on the app you are standing in and stays unsuffixed.
- **Why:** There is no way to answer "which agent apps do I have" short of inspecting
  every installed plugin by hand, as was done across nine of them to settle R-013. The
  distinction between a declared answer and a judged one has to survive into the output:
  a list that prints both in the same column is a list that has quietly turned a
  recommendation into a classification.

  **Deliberately low priority.** Nothing else depends on it, and the question it answers
  is asked rarely — once, when you are taking stock — unlike `lint`, which is asked on
  every change.
- **Outcome:** `/agent-app:list-installed` names every installed agent app, says whether
  each was identified by its own declaration or by judgment against the cuts, and reports
  the ones it could not classify rather than omitting them.
- **Blocked-by:** R-003
- **Enables:** —
