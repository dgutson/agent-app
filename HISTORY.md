# History

> Completed roadmap items, newest first.

## 2026-08-15

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
