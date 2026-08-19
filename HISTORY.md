# History

> Completed roadmap items, newest first.

## 2026-08-19

- **R-027 — every run leaves `<app>.log`, written while it runs.**
  Every `.ag` invocation now appends beside its own file — `hello.ag` writes `hello.log` —
  and the path goes to stderr *before* the session starts, so `tail -f` can be aimed at a
  run that is still going. That was the actual complaint behind both items today: not that
  a run cost money, but that there was no way to see what it was doing at the time.
  - **`--output-format stream-json --verbose`, streamed rather than captured.**
    `capture_output=True` hands everything over at exit, which is the one moment a live log
    stops being useful, so it is gone — and the wall clock now needs its own watchdog
    thread, because nothing blocks on a timeout any more. Probed before any of it was built
    (commit `8b4a03e`): the verdict survives the format change, so `structured_output`, the
    exit-status mapping and R-026's cap detection needed no change at all. That was the risk
    that would have doubled the item, and it did not materialise.
  - **Verbatim, and that was the user's call.** The offered default clipped tool-result
    bodies at 2 KB; it was rejected once it was established that clipping only shrinks the
    file on disk — the events arrive either way, so nothing about tokens or cost changes.
    The log is therefore a faithful copy: file contents, command output, whole subagent
    prompts. That is what makes it worth having when a run went wrong, and why `*.log` is
    now gitignored and `ag-format.md` says to treat it as a transcript rather than a build
    artifact.
  - **Subagents are answered, not merely mentioned.** `task_started` carries the subagent's
    type and the entire prompt it was handed, `task_progress` its tokens, tool count and
    duration, `task_notification` its status and returned summary. Every `assistant`/`user`
    line carries `parent_tool_use_id`, so a subagent's own tool calls separate from the main
    agent's even when the two run concurrently.
  - **Two launcher-authored lines bracket the stream** — `run_started` (app, command, args,
    cwd, plugin dir, timeout, cap, wall-clock time) and `run_finished` (exit, status, cost,
    seconds, and the reason when there is one). **Every ending is recorded, including the
    ones that failed**: a log that simply stops cannot tell a crash from a kill.
  - **A run is never failed for the sake of its log.** If the file cannot be opened, the
    launcher says so on stderr and runs unlogged.
  - **Measured end to end, not by inspection.** A clean `lint`: 19 lines, 24 KB,
    `exit 0 / status ok / cost $0.194 / 14.9s`. `--timeout 8`: killed mid-run with 11 events
    already on disk — which is the proof the writes are live rather than flushed at exit —
    and `note: killed at the 8s wall clock`. `--max-cost 0.0001`: `note: stopped at the
    spending cap`, `$0.18` recorded. All three appended to one file. Self-lint:
    `4 entry points, 3 first-party tools`, every check ran, exit 0.
  - **Left undone deliberately**, and said out loud rather than discovered: no rotation and
    no size cap, so the file grows; no `--no-log`; no per-event wall-clock stamp, so a saved
    log says when the run began and how long it took but not when each event landed; and
    only launcher runs are logged — `/app:cmd` inside a chat has no launcher in the loop,
    which `ag-format.md` now states instead of implying every invocation is recorded.

- **R-026 — an agent app can be capped in dollars, and says so in its own words.**
  `--max-cost USD` now sits beside `--timeout` in every launched app's `--help`, defaults to
  **$5**, and is forwarded to the session underneath as `--max-budget-usd`. The caller never
  types that name. An agent app is a program, so both of its bounds are spelled for what
  they bound rather than for the flag they become — and `--dry-run`'s help line lost the word
  "claude" for the same reason.
  - **A default, not merely an option.** The item left this open and it is the decision that
    matters: an option you have to remember is no protection on the run where you forget it,
    which is the run that raised this. $5 is arbitrary in exactly the way the 900-second
    timeout is arbitrary — printed in `--help`, overridable per run — and its job is to make
    an unattended runaway impossible, not to be a per-app budget.
  - **A capped run had to stop looking like a broken one.** Measured: budget exhaustion
    returns `"subtype": "error_max_budget_usd"` and **no `structured_output`**, so before
    this it fell into the generic *no verdict* branch with nothing to say why. It still exits
    **5** — the wall-clock kill's neighbour, and the same "this run reached no conclusion"
    that already means — but now names both numbers:
    `stopped at the $5 spending cap, $5.02 spent (raise --max-cost)`.
  - **It stops a runaway; it is not an exact ceiling, and the docs say so.** Measured:
    `--max-cost 0.0001` against this repository's own `lint` halted having spent **$0.35**,
    because the cap is checked between steps rather than before each one. Overshoot that
    somebody discovers from a bill is worse than overshoot that was written down.
  - **No `.ag` key, deliberately.** The file carries a `timeout` default and now visibly
    lacks the cost one. That asymmetry is R-024's third key and stays there, where the
    question is a per-app default rather than a bound that exists at all.
  - **Verified end to end**, not by inspection: `--help` renders the option, `--dry-run`
    shows the forwarded flag, `--max-cost 0` is a usage error (exit 2), a capped run exits 5
    with the message above, and an uncapped `lint` still returns its verdict and exits 0.
    Self-lint: `4 entry points, 3 first-party tools`, every check ran, exit 0.

## 2026-08-16

- **R-008 — the lint's findings now survive the run that produced them.**
  `lint_agent_app.py --emit [PATH]` writes the payload `--json` prints to a file, so a
  later step can act on the analysis instead of paying for a second one. Defaults to
  `.agent-app-findings.json` in the inspected root; a directory argument gets that name
  inside it. `/agent-app:lint` now runs `--json --emit` and its report is unchanged, plus
  one line saying where the file went — a file appearing in someone's repository
  unannounced is a surprise, however defensible. Still no `Edit` and no `Write` on that
  command: the script writes its own output through `Bash`, which is the rule the
  SKILL.md already stated and this is the first thing to need it.
  - **The file carries what it takes to distrust it.** A `provenance` block records every
    file the run read with a content digest, one `tree_hash` over the set, and the `only`
    and `wide` flags in force — the last because a payload emitted under `--only unread`
    holds one check's findings and otherwise reads exactly like a clean run of all of
    them. `--json` deliberately carries no such block: a session reading stdout has no
    staleness question, because the run it is reading just happened.
  - **The read set is wider than "prose and source", and that was the substantive
    decision.** `.agent-app-allow` and `.claude-plugin/plugin.json` are hashed too. An
    allow line retires a finding and the manifest's `name` decides a command's slug, so a
    check that ignored them would report *current* after exactly the edits most likely to
    have invalidated the file.
  - **Staleness is answered by the tool, not eyeballed.** `--check-emit [PATH]` re-hashes
    and exits `0` current / `3` stale / `2` unusable, naming the paths that `changed`,
    were `added` or were `removed`. Comparing hashes is determinable, so by this plugin's
    own first question it could not be left to prose. `unusable` covers absent,
    unparseable, foreign, and unknown-`format` alike — all four mean "you do not have
    findings yet" — and a `format` newer than this build says so, naming the linter as
    the old half rather than inviting a pointless re-emit.
  - **The self-lint caught the first draft.** `AA501`: the new exit statuses were hidden
    in a `{"current": 0, "stale": 3}.get(...)` lookup, so the prose documented an exit 3
    that nothing could be seen to raise — the `AA502` defect this linter reports in other
    people's tools. Rewritten as three explicit `return`s. Self-lint: `4 entry points,
    3 first-party tools`, every check ran, exit 0.
  - **Left as it is:** `--check-emit` matches on repo-relative paths and does not care
    that the recorded `root` differs, so a payload emitted in one checkout is answerable
    in another. That is what lets CI emit in one job and consume in the next.

- **R-010 lowered to Later**, at the user's call and with a line in the item saying so.
  It makes `/agent-app:agent-app` legible; everything it was competing with in **Now**
  changes what the plugin does.

- **`/agent-app:create` now finishes with a directory, and asks before it builds.**
  Not a roadmap item — the user pointed out that `create` was producing a design rather
  than an app, and that the brief it is handed is never a specification. Two gaps were
  real and both are closed.
  - **It never created `.claude-plugin/plugin.json`, and never stated a layout.** No step
    mentioned the manifest, so an app built by following the workflow literally was not
    an installable plugin; and the file said *"the layout is not the design"*, which was
    true about emphasis and slid into never saying what the layout is. `scripts/scaffold_app.py`
    (137 lines) now writes the manifest and reports the files that remain with what each
    needs — layout is a **must-be-identical** fact, which by this plugin's own rule puts
    it in a script rather than in prose the model re-reads each time. It validates the
    name as a plugin slug, never overwrites an existing manifest, and re-runs as a
    completeness check (`ready` / `incomplete` / `cannot-scaffold`).
  - **Interrogation is now step 1**, with the policy in the SKILL.md rather than a bare
    instruction: separate the gaps you may close yourself from the ones that change what
    gets built, ask the second kind in one message, and state every assumption you made
    for the rest. Worked through on the user's own brief, which is now the teaching
    example. **Running headless, it refuses and puts the questions in the output** — the
    launcher's protocol already forbids asking, and guessing would build to a
    specification nobody wrote.
  - **A leading flag now reaches the app.** `./diagnose-logs.ag --output x --format json`
    was an argparse usage error, because launcher options bind before the command and
    `--output` is not one — so an app whose interface is flags could not be reached
    through its default at all. With a `default-command` declared, the first flag the
    launcher does not itself define now begins the app's arguments. **The same opt-in
    trade `default-command` already makes**, extended from a mistyped verb to a mistyped
    flag; without a default, an unknown leading flag is still a usage error. The split
    reads the parser's own option strings, so it cannot disagree with the options that
    exist.
  - **Measured on the user's example, built end to end.** `diagnose-logs` — scaffolded,
    written, given an `.ag` by `update-ag`, `claude plugin validate` passing — ran as
    `./diagnose-logs.ag --output report.txt --format txt`, wrote a real report and exited
    **1**, correctly: it found things. It also declared `dmesg` unavailable
    (`kernel.dmesg_restrict`) instead of reporting a clean kernel log, which is the
    honesty rule doing its job.
  - **The linter caught the demo committing the exact error the new prose warns about.**
    `diagnose-logs`' command cited `--output` and `--format` while its script implemented
    neither — the model was doing the serialising, which is the mis-partition step 1 now
    tells you to raise at the start. Reported as two `AA201`s on the generated app. Left
    unfixed there, because the finding is worth more than the demo.
  - Two `AA201`s on *this* plugin, from quoting that example's flags, went to
    `.agent-app-allow` with reasons — the case the check's own docstring anticipates
    ("another app's field names quoted as an example"), and the same treatment `--force`
    already had. Self-lint: `4 entry points, 3 first-party tools`, every check ran, exit 0.
  - **Left open as R-025:** an app's *flags* are still not declared anywhere —
    `argument-hint` is free text the launcher passes through blind. R-014's claim that the
    argument surface is declared holds for commands and not for their options, which is
    also why R-017 can complete verbs but not flags.

- **R-023 — nobody hand-writes the `.ag` file, and generated apps get one.**
  `/agent-app:update-ag` (54 lines of prose over `scripts/update_ag.py`, 409 lines)
  works out what an app's `.ag` should say and writes it. `commands/create.md` gained a
  step 8 that invokes it, which is the half R-014 did not deliver; the plugin now ships
  its own `agent-app.ag`, generated by the tool rather than written by hand.
  - **It duplicates none of the format's rules.** The launcher is the authority, and it
    is *asked*: `agent-app-launcher <file> --help` exercises key validation, plugin
    resolution, command parsing and `default-command` validity in about 40ms with no
    model started. The script writes its proposal to a temporary file **beside** the
    target — `plugin-dir` resolves relative to the `.ag`, so validating anywhere else
    would validate a different path — and renames it into place only on exit 0. **A
    written `.ag` is therefore never one that cannot run.** The dependency is a
    subprocess rather than an import on purpose: the launcher is external to the plugin,
    so an absent one degrades to "written but not proved runnable" instead of failing.
  - **It never removes a key it did not add.** Measured on the case that matters: a file
    carrying `version: 2` is refused, with the launcher's own words relayed, and the
    author's line left in place. A key this script cannot account for is at least as
    likely to come from a newer launcher as from a typo — which is exactly the R-016
    scenario, arriving before R-016 does.
  - **Reconcile, not clobber, demonstrated rather than asserted.** The merge is
    line-oriented instead of a YAML round-trip, so comments, key order and a deliberately
    non-obvious `timeout` all survive a rewrite; the run reports its `keep` steps so the
    user can see what was left alone. Round-tripping through the loader would have
    discarded all three, which is the same overreach as a linter rewriting the app it was
    asked to report on.
  - **`plugin:` versus `plugin-dir:` is decided by path, never by name.** A source tree
    whose name happens to be installed elsewhere is still a tree, so it gets
    `plugin-dir:` plus a note that `plugin:` would run the other copy — the staleness
    trap from R-019, committed to a file. Measured on this repo, which is exactly that
    case.
  - **The judgment left to the prose is real, not decorative:** whether *this* app should
    declare a `default-command` (free for one command, a silent typo-swallower for
    several), and what to do when that note fires. Applied honestly to this plugin: four
    commands, so no default.
  - **The command holds no `Edit` and no `Write`** — the script writes the file, invoked
    through `Bash`, following the rule `/agent-app:lint` already states. Worth noting
    against R-009, whose converse check would otherwise read "writes, but holds no write
    grant" as a defect here.
  - **The plugin's own lint improved the code rather than being worked around.** It
    reported 11 `unread` evidence keys; two of them (`default_command`, `timeout`) were
    phantoms from an internal argument dict that only *looked* like a payload, so the
    dict was removed instead of the finding being allow-listed. The other nine are taught
    in the SKILL.md field table. Self-lint: `4 entry points, 2 first-party tools`, every
    check ran, exit 0.
  - **Measured end to end:** `./agent-app.ag lint --root .` runs this repository's own
    linter headless through the launcher and exits 0 with a clean report and no session
    chatter on stdout. The plugin is now a program that lints itself from a shell.
  - README and SKILL.md went from "three commands" to four, and the README heading *The
    fourth entry is not a command* became *The last entry…* — R-010 cites it, and its
    roadmap entry was updated to match.

- **R-014 — agent apps run from a shell.** An executable file whose first line is
  `#!/usr/bin/env agent-app-launcher` and whose body is a short YAML document naming an
  installed app is now a program: `./agent-app.ag lint --root .` runs the app headless,
  prints only its output, and exits on what it concluded. The launcher is **external to
  the plugin**, in `launcher/` — 270 lines of Python 3 plus PyYAML, a 190-line format
  spec, and a hello-world example. Nothing in `skills/`, `commands/` or `scripts/` was
  touched, on the user's instruction.
  - **`claude -p` cannot carry a verdict, measured rather than assumed:** a run told to
    report a failed check answered `FAILED: 3 errors found.` and exited **0**. It exits
    1 only on its own usage errors. So the launcher owns the exit status, obtaining a
    verdict through `--json-schema` — which makes the harness enforce the shape instead
    of trusting prose to remember it — and maps it: `0` ok, `1` findings, `2` usage,
    `3` refused, `4` error, `5` no verdict. **The mapping is fixed, never per-app
    configurable**, because `$?` has to mean the same thing across every agent app.
  - **`--help` starts no model at all.** Exit 0 in **0.05s**; `strace -e trace=execve`
    shows only `hello.ag → agent-app-launcher → python3`, and it answers identically
    with `claude` removed from `PATH`. This is the plugin's own partition rule applied
    to its launcher: a determinable fact is not worth a model.
  - **Resolve, don't restate.** The `.ag` file names an app and never copies its
    declarations — commands, usage lines and tool grants are read at run time from the
    plugin's own `commands/*.md` frontmatter. So there is one declaration and no copy
    that could drift, which is this repository's whole subject, and an app written
    before any of this existed gets a command line without changing a byte.
  - **No `model:` key, and the reason generalises.** Measured: frontmatter
    `model: claude-haiku-4-5-20251001` produced haiku in `modelUsage`; without the key,
    the session default. The harness resolves it when the slash command is dispatched,
    so an `.ag` key would not duplicate that declaration but **override** it. The
    launcher therefore passes no `--model`. Recorded against R-018.
  - **Rejected on principle:** a `permission-mode:` key or a general `claude-args:`
    passthrough. It would make the `.ag` a second undocumented CLI surface, and a
    committed `bypassPermissions` outlives whoever added it. `--allowed-tools` alone was
    measured sufficient headless — 0 permission denials — and without it a headless run
    cannot use `Bash` at all, so an app that shells out to its own tool does nothing.
  - **`default-command` was added, removed, and re-added on the user's call.** Removing
    it was on evidence: with a default declared, `./hello.ag shout` does not report an
    unknown command, it runs `greet` with `shout` as the name — which contradicts this
    repo's rule that a typo must never read as a clean run. It is back in, with the
    trade-off stated in the spec rather than left to be discovered.
  - **Not delivered, and carved out rather than quietly dropped:** the item also
    required that every app `/agent-app:create` generates ships with this invocation.
    `commands/create.md` is untouched, because nothing yet writes an `.ag` and teaching
    the format inline would put a second copy of it in the plugin. **R-023 now owns that
    half** and says so. Today exactly one `.ag` file exists.
  - Also deferred with their reasons recorded: the embedded single-file form (R-022),
    and the `cwd` / `args` / `max-cost` keys (**R-024**, new). The `version:`
    forward-compatibility question went to **R-016**, because an installer is precisely
    what makes version skew possible — while every copy of the launcher is one symlink
    on one machine, it costs nothing to fix.
  - **The launcher is extensionless on purpose:** `lint_agent_app.py`'s
    `SOURCE_SUFFIXES` would otherwise collect it as first-party source and the plugin's
    self-lint would stop being about the plugin. Still `3 entry points, 1 first-party
    tool / clean`, exit 0.
  - **Two things thrown away rather than shipped**, both worth the line: a first build
    of ~600 lines placed the launcher *inside* the plugin and edited its SKILL.md — the
    user rejected it and it was deleted; and a 545-line version was cut to 231 on a
    challenge about size, with identical behaviour, by dropping wrapper classes, custom
    exception types and four flags nobody had asked for.

## 2026-08-15

- **R-021 — the README stops arguing and starts explaining.** 259 lines down to 212: the
  concept, the three relations, how an app is invoked, and how to run the commands and the
  linter. Added, implemented and retired in one session at the user's request.
  - **Indistinguishability is now stated, not implied.** "From the outside it is
    indistinguishable from any other program on the system" — invocation, output, exit
    status and pipeability reveal nothing about whether the last step was Python or
    judgment. The old text only gestured at it with "ideally you never find out".
  - **Skill / plugin / agent app is now about the relations**, on the user's instruction
    that nobody asked a question: the table's third column is *how it relates* rather than
    *question it answers*, and the containment is spelled out in both directions — an app
    is usually implemented as a plugin and almost no plugin is one; an app's `main()` is a
    skill and almost no skill is any app's `main()`.
  - **The three commands are one numbered workflow** in the order an app meets them, with
    the comparison table demoted to a four-row summary beneath it.
  - **Cut:** both sample console outputs, the trimmed-report example, the `skillOverrides`
    reasoning behind *The fourth entry is not a command* (heading kept — R-010 cites it),
    and the tier table, which became three lines of prose. **Kept:** the rule-code table,
    the flag table and the exit codes, since those are usage rather than argument.
  - **Added on the user's follow-up, after the cut:** that an agent app is invoked **both
    interactively at a terminal and non-interactively from a script** — bash, a Makefile
    rule, a git hook, cron, a CI step — with an honest note on where that stands today,
    since R-014 is unbuilt: interactively it is a slash command, headless it is
    `claude -p "/agent-app:lint"`, which runs but exits 0 for any completed session, so
    nothing can branch on the verdict yet. `lint_agent_app.py` is named as the half that
    already works from a script today, having no model in it. Also stated plainly that
    **`agent-app` is itself an agent app, one whose subject is building agent apps** —
    true of the pre-rewrite README as an aside about implementation, and lost to an aside
    again in the first draft of this one.
  - **Not the "roughly half" the item claimed** — 18% shorter, not 50%, and the follow-up
    additions account for part of that. What survived the cut was concept or usage, which
    is what the item asked to keep, so the rest of the reduction would have had to come
    out of content the user wanted.
  - README.md is not read by the linter — it reads `SKILL.md` and `commands/*.md` only —
    so nothing here could break the self-lint, and the plugin still lints clean.

- **R-006 — published as [dgutson/agent-app](https://github.com/dgutson/agent-app),
  public, MIT.** `git init` on a tree that had never been a repository, one initial
  commit of 14 files / 2,851 lines, pushed to `main`. `.claude-plugin/marketplace.json`
  is at the repo root, so `/plugin marketplace add dgutson/agent-app` followed by
  `/plugin install agent-app@agent-app-marketplace` — the two lines the README already
  carried — now work from any machine.
  - **Gated on the plugin's own rule** before anything was pushed: `lint_agent_app.py
    --root .` exit 0, and `claude plugin validate .` passing. Publishing a linter that
    fails its own check was the one outcome worth refusing.
  - **Deliberately not committed:** `HANDOFF.md` (session scratch, and stale — it still
    named R-013 as next) and `.claude/settings.local.json` (permission allowlists full of
    absolute paths from one checkout). Both added to `.gitignore` rather than merely
    left untracked.
  - **The marketplace was NOT re-pointed from the local directory to GitHub**, which the
    item asked for. Doing it would have broken the development loop measured in R-019:
    with the source at `./`, edits take effect after `claude plugin marketplace update`;
    pointed at GitHub, every local change would need a push first. Fourteen items remain
    open, so the local source stays. Re-point with
    `claude plugin marketplace remove agent-app-marketplace && claude plugin marketplace
    add dgutson/agent-app` once development settles. The item's stated outcome —
    installable from GitHub by another machine or another person — is met either way.
  - `marketplace.json`'s public description was rewritten to the definition R-013
    settled; it still described agent apps as "skills whose tool establishes the facts",
    which is the framing the same session had just corrected.

- **R-013 — the definition is written down, and the linter stopped reporting on
  promises nobody made.** An agent app is **a console app whose `main()` is a skill**:
  the user runs it by name, gets a result, and ideally never learns a model ran the last
  mile. Three ordered cuts decide membership — is there a `main()` somebody invokes; is
  the result the user's rather than the harness's; does the last step actually need
  judgment — and they are in the SKILL.md and the README, along with a table separating
  *skill* (a unit of instruction), *plugin* (a distribution format) and *agent app* (a
  kind of program).
  - **Read differently from the item as written, on the user's correction.** The item
    proposed *"does a first-party tool establish the facts?"* as cut #2, which would have
    made `roadmap` — three skills, no script — not an agent app. It is one: whether an
    app ships a script is implementation, invisible to the user, and a definition that
    flips when prose is refactored into Python is a definition about internals. Shipping
    a script is now explicitly **not** a cut, and the partition rule is stated as advice
    on implementing an app rather than as a membership test.
  - **Checks are tiered by measurement precondition, not by classification** — which is
    what keeps a recommendation ("this wants a script") from becoming a verdict ("this is
    not an agent app"). `frontmatter`/`xref`/`command` always run; `rederive` needs an
    entry point; `unread`/`stale-ref`/`exit-code` need first-party source to compare
    against. Naming a check with `--only` overrides its tier and the run says so.
  - **`not-applicable` joined `not-run`/`partial`/`note`** as a coverage kind, printed in
    its own `NOT APPLICABLE` block, excluded from "unmeasured is not clean", and taught
    in the prose as the one kind that carries no warning.
  - **New `classification` block in `--json`** — `entry_points`, `tools`,
    `harness_wired`, `emits_payload`, `invocable`, `has_tool_half`, `warning` — which
    establishes the mechanical half of the cuts and refuses the verdict, because cuts #2
    and #3 are judgment. Harness-wired executables are found transitively (a hook's
    helper is the harness's too) except when the prose invokes them, which is what keeps
    one hook shelling out to the app's own tool from hiding the whole evidence contract.
  - **Measured, on the cases that motivated the item:** `roadmap` went from *"3 checks
    not run — unmeasured is not clean"* to `clean … 3 checks not applicable`; `uv-skill`
    lost its `AA101` and gained a warning naming it a guidance skill; `handoff`'s four
    scripts were correctly read as the harness's, not its tool half. `plugin-finder`
    (22), `check-chat` (31) and `update-tools` (20) are unchanged, and the plugin lints
    itself clean.
  - **Handed on:** R-003's marker asserts **conformance**, not provenance, and a marked
    artifact with no tool half is an error — recorded in the item, along with R-001
    losing the structural heuristic that misclassified `claude-sudo-askpass`. Also
    corrected en route: `issues` 0.2.0 ships `scripts/issues.py`, so the roadmap's
    "`roadmap` and `issues`" pair was only ever `roadmap`.

- **R-011 — the linter's console output now reads like a linter.** One line per finding,
  `path:line:col: severity CODE message`, sorted by file and relative to the inspected
  root. Every diagnostic has a stable code (`AA001`–`AA602`, grouped `AA0` structure
  through `AA6` commands) held in a single `RULES` registry that also fixes its check,
  severity and fix hint — so the hint prints once per rule in a `fix by rule` footer
  rather than once per finding. A rule firing more than six times in one file collapses
  to a comma-separated list of its subjects, with `--verbose` to expand it. On
  `update-tools`: 64 lines for 20 findings, down to 29 (38 with `--verbose`).
  - **Read differently from the item as written**, following the "look like ruff/pylint"
    steer: a flat file-sorted list rather than a section per check, with the codes and the
    footer doing the grouping, and the by-check counts living in that footer instead of
    being repeated in the lead line — which now carries severity totals and the coverage
    gaps.
  - **Went past the item.** `checks_skipped` entries gained a `kind` (`not-run` /
    `partial` / `note`), because an unrun check and a partially-run one were being
    reported in identical words. `--only` now takes a rule code as well as a check name,
    scopes the coverage gaps to the question asked, and exits 2 on an unknown value
    instead of answering a typo with a clean report.
  - **The JSON contract changed with it:** `where` split into `file`, `line` and `col`
    — null where no position was established, never a fabricated `1` — and `code` and
    `subject` were added, so a consumer groups on a field instead of parsing a rendered
    string back apart. Taught in the SKILL.md, `commands/lint.md` and the README. The
    plugin lints itself clean.
