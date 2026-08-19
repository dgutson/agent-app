#!/usr/bin/env python3
"""Check that an agent app's prose and its tool still agree.

An agent app is a console app whose `main()` is a skill. Most are implemented
in two halves, and those halves rot in one specific direction: the tool grows a
field, and nobody revisits four hundred lines of policy prose to teach the
model to read it. Evidence gets computed and thrown away.

This checks the seam where there is one. Which checks can run is a question
about the artifact's *implementation*, not about whether it is an agent app —
that is judgment, and this script does not make it. A prose-only app has no
seam to check and is not thereby deficient; a skill nobody invokes is not an
app at all, and the checks that presuppose one are reported as inapplicable
rather than passed.

It reports what it could not check as loudly as what it found, because an
unrun check is not a passing one.

Exit codes:  0 clean   1 findings   2 usage error   3 emitted payload is stale
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import textwrap
from dataclasses import dataclass, field
from pathlib import Path

ALLOW_FILE = ".agent-app-allow"

# Where `--emit` writes when nobody says. Named here rather than spelled inline
# because the prose tells a consumer to look for this file, so renaming it in
# one place and not the other sends somebody to read nothing.
EMIT_FILE = ".agent-app-findings.json"

# Bumped when the emitted payload changes shape. A consumer reads it before
# anything else and refuses a number it does not know, rather than picking
# fields out of a structure it is guessing at.
EMIT_FORMAT = 1

# Directories that never hold either prose or first-party source.
SKIP_DIRS = {
    ".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache",
    ".ruff_cache", ".mypy_cache", "dist", "build", ".tox", "site-packages",
}

SOURCE_SUFFIXES = {".py", ".sh", ".bash", ".js", ".mjs", ".ts", ".rb", ".pl"}

# Past this many findings of one rule in one file, the console prints the list
# of subjects instead of a line each. --verbose prints them all.
COLLAPSE_AT = 6
WIDTH = 78


# --------------------------------------------------------------------------
# rules
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Rule:
    """One diagnostic, named once.

    A stable code is what makes a finding referable — in a commit message, in
    `--only`, in whatever CI eventually reads this. The `check` groups the codes
    that share a cause, and the `hint` is printed once per rule rather than once
    per finding: a fix repeated seventeen times is the report nobody reads.
    """

    check: str
    severity: str          # "error" | "warn"
    hint: str


# AA0 structure · AA1 partition · AA2 references · AA3 evidence
# AA4 navigation · AA5 control flow · AA6 commands
RULES: dict[str, Rule] = {
    "AA001": Rule("frontmatter", "error",
                  "add a `---` block declaring `name` and `description`"),
    "AA002": Rule("frontmatter", "warn",
                  "declare `name`, or drop it consistently across the plugin"),
    "AA003": Rule("frontmatter", "error",
                  "correct `name` to match the directory, or rename the directory"),
    "AA004": Rule("frontmatter", "error",
                  "add a `description`; it is the only thing routing reads"),
    "AA005": Rule("frontmatter", "warn",
                  "name the triggering phrases and commands explicitly"),
    "AA101": Rule("rederive", "warn",
                  "judge it with /agent-app:partition; if it stays, say why here"),
    "AA102": Rule("rederive", "warn",
                  "have the tool emit the comparison, or say why the model weighs it"),
    "AA201": Rule("stale-ref", "error",
                  "rename it, or delete the instruction that depends on it"),
    "AA301": Rule("unread", "error",
                  f"teach it in the skill, or record why not in {ALLOW_FILE}"),
    "AA401": Rule("xref", "warn",
                  "point it at the real heading, or drop the direction word"),
    "AA501": Rule("exit-code", "error",
                  "raise it, or stop documenting a status that cannot occur"),
    "AA502": Rule("exit-code", "warn",
                  "document it; the model cannot branch on a status nobody named"),
    "AA601": Rule("command", "warn",
                  "give it a workflow section, or fold it into another command"),
    "AA602": Rule("command", "warn",
                  "add the missing command file, or stop naming it in the skill"),
}

CHECKS = sorted({r.check for r in RULES.values()})


# Which checks a given artifact has any business answering.
#
# Not a classification. Whether something *is* an agent app turns on what
# running it delivers and to whom, which is judgment and stays out of this
# script. These are measurement preconditions: `unread` compares emitted fields
# against prose and needs fields to compare, `rederive` asks how an app's work
# is divided and needs an app. Tiering on what is measurable rather than on
# what the thing is keeps a recommendation ("this wants a script") from
# quietly becoming a verdict ("this is not an agent app").
TIER_ANY = "any-skill"      # holds for anything skill-shaped
TIER_APP = "agent-app"      # presupposes something the user invokes by name
TIER_TOOL = "tool-half"     # presupposes first-party source to compare against

CHECK_TIER = {
    "frontmatter": TIER_ANY,
    "xref": TIER_ANY,
    "command": TIER_ANY,
    "rederive": TIER_APP,
    "unread": TIER_TOOL,
    "stale-ref": TIER_TOOL,
    "exit-code": TIER_TOOL,
}

TIER_REASON = {
    TIER_APP: "nothing here is invoked by name, so there is no app whose "
              "implementation could be misdivided",
    TIER_TOOL: "no first-party tool, so there is no second half for the prose "
               "to disagree with",
}


# --------------------------------------------------------------------------
# model
# --------------------------------------------------------------------------

@dataclass
class Finding:
    code: str
    file: str                  # repo-relative once run() has normalised it
    message: str
    subject: str = ""          # the identifier this finding is about
    line: int | None = None
    col: int | None = None

    @property
    def check(self) -> str:
        return RULES[self.code].check

    @property
    def severity(self) -> str:
        return RULES[self.code].severity

    @property
    def hint(self) -> str:
        return RULES[self.code].hint

    @property
    def loc(self) -> str:
        """As much of the location as was actually established, no more."""
        if self.line is None:
            return self.file
        if self.col is None:
            return f"{self.file}:{self.line}"
        return f"{self.file}:{self.line}:{self.col}"

    def as_dict(self) -> dict:
        return {
            "code": self.code,
            "check": self.check,
            "severity": self.severity,
            "file": self.file,
            "line": self.line,
            "col": self.col,
            "subject": self.subject,
            "message": self.message,
            "hint": self.hint,
        }


@dataclass
class Coverage:
    """What was actually read, and what was not checked and why.

    The point of the app this lints is that unmeasured is not the same as
    clean. That rule applies to the linter too, so it reports its own gaps.
    """

    prose_files: list[str] = field(default_factory=list)
    source_files: list[str] = field(default_factory=list)
    skipped: list[dict] = field(default_factory=list)

    def skip(self, check: str, reason: str, kind: str = "not-run") -> None:
        # One entry per check. Two code paths can both decide a check cannot
        # run, and reporting it twice reads as two separate gaps.
        if any(s["check"] == check for s in self.skipped):
            return
        self.skipped.append({"check": check, "kind": kind, "reason": reason})


@dataclass
class Prose:
    path: Path
    text: str
    headings: list[str]
    # backticked token -> (line, column) of its first appearance
    tokens: dict[str, tuple[int, int]]


@dataclass
class Shape:
    """What the artifact is, as far as a script can honestly establish it.

    Deliberately short of a verdict. Whether something is an agent app turns on
    what running it delivers and to whom — a question about its user, not about
    its files — and a script that guessed at it would be doing exactly what
    this plugin tells everyone else not to do. Two narrower facts *are*
    mechanical, and they are the two the report needs:

    `entry_points` — is there a `main()`: a command, or a skill that names its
    own invocation. Nothing here is inferred from having files.

    `tools` — first-party executables, minus the ones the harness runs. A hook
    is wired to the harness, not to the skill, so counting it as a tool half
    would invent an evidence contract nobody wrote.
    """

    entry_points: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
    harness_wired: list[str] = field(default_factory=list)
    emits_payload: list[str] = field(default_factory=list)

    @property
    def invocable(self) -> bool:
        return bool(self.entry_points)

    @property
    def has_tool_half(self) -> bool:
        return bool(self.tools)

    @property
    def warning(self) -> str:
        """Addressed to whoever aimed this linter, not to the artifact.

        A skill nobody invokes by name has no `main()`, which is the first cut:
        it exists to change how the model proceeds, and its author never
        promised the things an app is checked for. Saying so is a warning about
        the invocation; it is not a finding, and it does not fail the run.
        """
        if not self.invocable:
            return ("nothing here is invoked by name — no commands, and no "
                    "skill naming its own slash command. That is a guidance "
                    "skill rather than an app, and only the checks that hold "
                    "for any skill were run against it.")
        return ""

    def as_dict(self) -> dict:
        return {
            "entry_points": self.entry_points,
            "tools": self.tools,
            "harness_wired": self.harness_wired,
            "emits_payload": self.emits_payload,
            "invocable": self.invocable,
            "has_tool_half": self.has_tool_half,
            "warning": self.warning or None,
        }


def _at(text: str, offset: int) -> tuple[int, int]:
    """1-based line and column of an offset — the location half of a finding.

    Where a column would be a guess — a finding about a whole file, or about
    something that is missing — it stays None and the renderer prints only what
    was established.
    """
    line = text.count("\n", 0, offset) + 1
    col = offset - (text.rfind("\n", 0, offset) + 1) + 1
    return line, col


# --------------------------------------------------------------------------
# collection
# --------------------------------------------------------------------------

def _walk(root: Path):
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        yield p


def collect_prose(root: Path) -> list[Prose]:
    """SKILL.md files and the command markdown that invokes them."""
    out = []
    for p in sorted(_walk(root)):
        if p.suffix != ".md":
            continue
        rel = p.relative_to(root).as_posix()
        if p.name != "SKILL.md" and not rel.startswith("commands/"):
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        headings = re.findall(r"^#{1,6}\s+(.*)$", text, re.M)
        tokens: dict[str, tuple[int, int]] = {}
        for m in re.finditer(r"`([^`\n]{2,60})`", text):
            tok = m.group(1)
            if tok not in tokens:
                tokens[tok] = _at(text, m.start(1))
        out.append(Prose(p, text, headings, tokens))
    return out


def collect_sources(root: Path, skill_dirs: set[Path]) -> list[Path]:
    """First-party executable code: the slave half of the app."""
    out = []
    for p in sorted(_walk(root)):
        if p.suffix not in SOURCE_SUFFIXES:
            continue
        # A script that lives inside a skill directory is still source.
        out.append(p)
    return out


# --------------------------------------------------------------------------
# shape
# --------------------------------------------------------------------------

def _plugin_name(root: Path) -> str:
    manifest = root / ".claude-plugin" / "plugin.json"
    if not manifest.is_file():
        return ""
    try:
        return json.loads(manifest.read_text()).get("name", "")
    except (json.JSONDecodeError, OSError):
        return ""


# `/plugin:command` or `/name`, not preceded by a word character — which is
# what keeps `skills/agent-app/SKILL.md` from reading as an invocation of
# `/agent-app`.
_SLUG = re.compile(r"(?<![\w/.])/([a-z][\w-]*)(?::([a-z][\w-]*))?(?!/)")


def find_entry_points(root: Path, prose: list[Prose], plugin: str) -> list[str]:
    """The app's `main()`s: what a user can invoke by name.

    Three ways an artifact can have one, and a skill that has none is not an
    app — it is guidance, triggered by context to change how the model works
    rather than run to produce something.
    """
    out: set[str] = set()
    cmd_dir = root / "commands"
    if cmd_dir.is_dir():
        for cmd in sorted(cmd_dir.glob("*.md")):
            out.add(f"/{plugin}:{cmd.stem}" if plugin else f"/{cmd.stem}")
    skills = {pr.path.parent.name for pr in prose if pr.path.name == "SKILL.md"}
    own = {n for n in {plugin, *skills} if n}
    for pr in prose:
        # A skill that names its own slash command is telling the reader it is
        # invoked. One that only says "use this whenever…" is not.
        for m in _SLUG.finditer(pr.text):
            if m.group(1) in own or (m.group(2) and m.group(2) in own):
                out.add(m.group(0))
        # `disable-model-invocation` says the user is the only caller there is.
        if re.search(r"^disable-model-invocation:\s*true", pr.text, re.M):
            out.add(f"/{plugin}:{pr.path.parent.name}" if plugin
                    else f"/{pr.path.parent.name}")
    return sorted(out)


def find_harness_wired(root: Path, sources: list[Path], prose_text: str = "") -> list[Path]:
    """Executables the harness runs: hooks, MCP servers, a statusline.

    Transitively, because a hook that calls a helper makes the helper the
    harness's too — `post-write-gitignore.sh` calls `ensure_gitignore.sh`, and
    reading that helper as an app's tool half would be inventing an evidence
    contract its author never wrote.

    But a script the prose invokes is the skill's tool no matter who else calls
    it, so naming it in the prose takes it back out. Without that, one hook
    that shells out to the app's own tool would hide the entire evidence
    contract behind a plausible-looking "no first-party tool" — a suppression
    nobody would see, which is worse than a finding somebody can dismiss.

    Only the manifest's harness keys are read, not the whole file: a script
    named in `description` is being described, not wired.
    """
    blobs: list[str] = []
    manifest = root / ".claude-plugin" / "plugin.json"
    if manifest.is_file():
        try:
            data = json.loads(manifest.read_text())
            blobs += [json.dumps(data[k]) for k in
                      ("hooks", "mcpServers", "statusLine") if k in data]
        except (json.JSONDecodeError, OSError, TypeError):
            pass
    for extra in (root / "hooks" / "hooks.json", root / ".mcp.json"):
        if extra.is_file():
            blobs.append(extra.read_text(encoding="utf-8", errors="replace"))
    wired: set[Path] = set()
    frontier = "\n".join(blobs)
    while frontier:
        newly = {p for p in sources if p not in wired and p.name in frontier}
        if not newly:
            break
        wired |= newly
        frontier = "\n".join(
            p.read_text(encoding="utf-8", errors="replace") for p in newly
        )
    return sorted(p for p in wired if p.name not in prose_text)


def _rel(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def describe_shape(root: Path, prose: list[Prose], sources: list[Path]) -> Shape:
    wired = find_harness_wired(root, sources, "\n".join(pr.text for pr in prose))
    tools = [p for p in sources if p not in set(wired) and not _is_test(p)]
    return Shape(
        entry_points=find_entry_points(root, prose, _plugin_name(root)),
        tools=[_rel(p, root) for p in tools],
        harness_wired=[_rel(p, root) for p in wired],
        emits_payload=[
            _rel(p, root) for p in tools
            if p.suffix == ".py"
            and _EMITS_JSON.search(p.read_text(encoding="utf-8", errors="replace"))
        ],
    )


# --------------------------------------------------------------------------
# evidence-key extraction
# --------------------------------------------------------------------------

def _dataclass_fields(text: str) -> set[str]:
    """Annotated fields of @dataclass / @attrs classes."""
    keys: set[str] = set()
    lines = text.splitlines()
    in_dc = False
    for i, line in enumerate(lines):
        if re.match(r"\s*@(dataclass|attr\.s|attrs\.define)", line):
            in_dc = True
            continue
        if in_dc and re.match(r"\s*class\s+\w+", line):
            # scan the class body
            for body in lines[i + 1:]:
                if body.strip() and not body.startswith((" ", "\t")):
                    break
                m = re.match(r"\s{2,}([a-z_][a-z0-9_]*)\s*:\s*\S", body)
                if m and not m.group(1).startswith("_"):
                    keys.add(m.group(1))
            in_dc = False
    return keys


# A file that writes JSON to stdout is the one that assembles the payload the
# model receives — which makes it the evidence contract, and makes its dict
# keys worth checking against the prose.
_EMITS_JSON = re.compile(
    r"json\.dumps?\([^)]*(?:sys\.stdout|stdout)|print\(\s*json\.dumps?\("
)


def _payload_keys(text: str) -> set[str]:
    """String keys of dict literals in a file that writes JSON to stdout.

    The stdout requirement is what keeps the signal usable. Every module has
    dict literals — package-name lookup tables, HTTP request bodies — and
    flagging those as unread evidence produces a report the reader learns to
    skip. Only the file that assembles the payload the model actually receives
    is the contract.
    """
    if not _EMITS_JSON.search(text):
        return set()
    return {
        m.group(1)
        for m in re.finditer(r'"([a-z][a-z0-9_]{2,30})"\s*:', text)
    }


def _is_test(path: Path) -> bool:
    """Test fixtures are not the app's contract with the model."""
    parts = set(path.parts)
    return bool(
        parts & {"tests", "test", "testing"}
        or path.name.startswith("test_")
        or path.stem.endswith("_test")
        or path.name == "conftest.py"
    )


def evidence_keys(sources: list[Path], wide: bool = False) -> dict[str, tuple[str, int, int | None]]:
    """key -> (file, line, column) where it is defined.

    Narrow (the default) reads the model's dataclasses and the dict literals in
    whichever file writes the payload to stdout. That is where the contract is
    assembled, and it keeps the report small enough to act on.

    It also *under*-reports: a key contributed by a helper module, nested into
    the payload downstream, is invisible to it. `wide` reads every dict literal
    in every non-test module instead, which finds those at the cost of a lot of
    lookup tables. The gap between the two is reported as a coverage limit
    rather than left implicit.
    """
    found: dict[str, tuple[str, int, int | None]] = {}
    for p in sources:
        if p.suffix != ".py" or _is_test(p):
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        if wide:
            keys = _dataclass_fields(text) | {
                m.group(1)
                for m in re.finditer(r'"([a-z][a-z0-9_]{2,30})"\s*:', text)
            }
        else:
            keys = _dataclass_fields(text) | _payload_keys(text)
        if not keys:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            for k in list(keys):
                if k in found:
                    continue
                m = re.search(rf'(^|["\s]){re.escape(k)}["\s:]', line)
                if m:
                    found[k] = (str(p), i, m.start(0) + len(m.group(1)) + 1)
        for k in keys:
            found.setdefault(k, (str(p), 1, None))
    return found


# --------------------------------------------------------------------------
# checks
# --------------------------------------------------------------------------

def _looks_like_identifier(tok: str) -> bool:
    """Only judge tokens that are unambiguously code.

    A bare English word in backticks (`check`, `stale`) is prose emphasis as
    often as it is a symbol, and guessing wrong produces a finding the reader
    has to dismiss. snake_case, dotted paths, and flags are unambiguous.
    """
    if re.fullmatch(r"--[a-z][a-z0-9-]*", tok):
        return True
    if re.fullmatch(r"[a-z][a-z0-9_]*\.[a-z_][a-z0-9_.]*", tok):
        return True
    return bool(re.fullmatch(r"[a-z][a-z0-9]*(_[a-z0-9]+)+", tok))


def check_stale_refs(
    prose: list[Prose], source_text: str, allow: dict[str, str], cov: Coverage
) -> list[Finding]:
    """Prose asserting a symbol or flag the code does not have.

    The allowlist covers this check too, because a skill legitimately cites
    identifiers it does not own — another app's field names quoted as an
    example, a flag belonging to a tool it merely mentions. Those go in the
    same file, with the same requirement to say why.
    """
    if not source_text:
        cov.skip("stale-ref", "no first-party source files found")
        return []
    out = []
    for pr in prose:
        for tok, (line, col) in pr.tokens.items():
            if not _looks_like_identifier(tok) or tok in allow:
                continue
            needle = tok.split(".")[-1] if "." in tok else tok
            if needle in source_text:
                continue
            out.append(Finding(
                "AA201", str(pr.path),
                f"prose cites `{tok}`, which appears nowhere in the source",
                tok, line, col,
            ))
    return out


# Verbs that ask the reader to *establish* something rather than weigh it.
# Anchored at instruction position — start of a line or clause — because the
# same words appear harmlessly mid-sentence when the prose is describing what
# the tool already did.
_DETERMINE = (
    r"grep|search for|look for|find all|find every|scan for|list all"
    r"|count|tally|compare|diff"
    r"|check whether|check if|check that|verify that|confirm that|make sure"
    r"|parse|extract|determine|work out|figure out|calculate|compute"
)
_THRESHOLD = r"\b(?:more|fewer|less|greater)\s+than\s+\d+|\bat (?:least|most)\s+\d+"

# A line that also points at the tool is describing delegation, not asking for
# re-derivation. This is what keeps the check from flagging every workflow step.
_DELEGATES = re.compile(
    r"`[^`\n]*(?:--|\bpython3?\b|\bnode\b|\.py\b|\.sh\b)[^`\n]*`"
    r"|\bthe tool\b|\balready\b|\bthe script\b|\bit reports\b|\bit emits\b",
    re.I,
)


def check_rederivation(prose: list[Prose], allow: dict[str, str]) -> list[Finding]:
    """Prose instructing the model to establish something a script could.

    Deliberately a *candidate* detector, not a verdict. Whether a given line is
    misplaced is judgment — that is `/agent-app:partition`'s job — but finding
    the lines worth judging is mechanical, so it belongs here. Partition then
    starts from evidence instead of re-reading the whole app, which is the same
    division of labour the rest of this plugin argues for.

    Suppress a line with a trailing `<!-- agent-app: ok -->` when the prose is
    quoting these verbs rather than issuing them.
    """
    out = []
    for pr in prose:
        lines = pr.text.splitlines()
        # Frontmatter is metadata, not instruction. `allowed-tools: … Grep`
        # is a permission grant, and reading it as an order to grep would make
        # this check fire on every command file in existence.
        start = 0
        if lines and lines[0].strip() == "---":
            for j, line in enumerate(lines[1:], 1):
                if line.strip() == "---":
                    start = j
                    break
        for i, raw in enumerate(lines, 1):
            if i <= start:
                continue
            if raw.lstrip().startswith("#") or "<!-- agent-app: ok -->" in raw:
                continue
            body = re.sub(r"^\s*(?:[-*+]|\d+\.)\s*", "", raw)
            hit = re.match(rf"\**(?:{_DETERMINE})\b", body, re.I) or re.search(
                rf"(?:^|[,;:—]\s*|\band\s+|\bthen\s+)(?:{_DETERMINE})\b", body, re.I
            )
            thresh = re.search(_THRESHOLD, body, re.I)
            if not (hit or thresh):
                continue
            if _DELEGATES.search(raw):
                continue
            what = (hit or thresh).group(0).strip(" ,;:—")
            # The clause-position alternative swallows the conjunction that
            # anchored it; quoting "and check whether" back at the reader
            # reads as a parse error rather than as the instruction it found.
            what = re.sub(r"^(?:and|then)\s+", "", what, flags=re.I)
            col = raw.find(what) + 1 if what in raw else None
            if hit:
                out.append(Finding(
                    "AA101", str(pr.path),
                    f'asks the model to "{what.lower()}" — a script may owe this answer',
                    what.lower(), i, col,
                ))
            else:
                out.append(Finding(
                    "AA102", str(pr.path),
                    f'states a threshold ("{what.lower()}") for the model to evaluate',
                    what.lower(), i, col,
                ))
    return out


def check_unread_evidence(
    prose: list[Prose],
    keys: dict[str, tuple[str, int, int | None]],
    allow: dict[str, str],
    cov: Coverage,
) -> list[Finding]:
    """Evidence the tool emits that no prose teaches the model to read.

    This is the check that pays. The other direction stays clean on its own,
    because prose gets written with the code in view; this one rots silently
    every time the tool learns something new.
    """
    if not keys:
        cov.skip("unread", "no dataclass fields or JSON payload keys found")
        return []
    blob = "\n".join(pr.text for pr in prose)
    out = []
    for k, (path, line, col) in sorted(keys.items()):
        if k in allow or k in blob:
            continue
        out.append(Finding(
            "AA301", path, f"`{k}` is emitted, and no prose reads it", k, line, col,
        ))
    return out


def check_xrefs(prose: list[Prose]) -> list[Finding]:
    """Cross-references pointing at a section that is not there.

    Only a *named* target counts — backticked, quoted, or followed by the word
    "section". Prose says "see below", "see them", and "see auth/session.py:88"
    constantly, and treating those as cross-references made this check wrong
    far more often than right on real skills.
    """
    out = []
    for pr in prose:
        slugs = {h.lower() for h in pr.headings}
        for m in re.finditer(
            r"see (?:the )?(?:[`\"]([A-Za-z][\w \-]{2,40}?)[`\"]|"
            r"([A-Za-z][\w \-]{2,40}?) section)"
            r"(?:\s+(below|above))?",
            pr.text,
        ):
            target = (m.group(1) or m.group(2)).strip().lower()
            direction = m.group(3)
            if "/" in target or "." in target:
                continue  # a path, not a heading
            if not direction and " " in target:
                continue  # "see the release notes" — prose, not a xref
            norm = target.replace("-", " ").replace("_", " ")
            if any(norm in s.replace("-", " ").replace("_", " ") for s in slugs):
                continue
            line, col = _at(pr.text, m.start())
            out.append(Finding(
                "AA401", str(pr.path),
                f'"{target}" matches no heading in this file',
                target, line, col,
            ))
    return out


def check_exit_codes(prose: list[Prose], sources: list[Path], cov: Coverage) -> list[Finding]:
    """Documented exit codes versus the ones actually raised."""
    raised: dict[int, tuple[str, int, int]] = {}
    for p in sources:
        text = p.read_text(encoding="utf-8", errors="replace")
        for i, line in enumerate(text.splitlines(), 1):
            for m in re.finditer(r"(?:sys\.exit|SystemExit|return)\s*\(?\s*([0-9])\b", line):
                raised.setdefault(int(m.group(1)), (str(p), i, m.start(1) + 1))
            for m in re.finditer(r"^\s*exit\s+([0-9])\b", line):
                raised.setdefault(int(m.group(1)), (str(p), i, m.start(1) + 1))
    if not raised:
        cov.skip("exit-code", "no literal exit statuses found in the source")
        return []
    # Codes are usually written in backticks, and often in a run:
    # "Exit codes: `0` clean, `1` findings, `2` usage error."
    documented: dict[int, tuple[str, int, int]] = {}
    for pr in prose:
        for m in re.finditer(r"exit\s*(?:code)?s?\b[^.\n]{0,120}", pr.text, re.I):
            for d in re.finditer(r"`?\b([0-9])\b`?", m.group(0)):
                code = int(d.group(1))
                if code not in documented:
                    line, col = _at(pr.text, m.start() + d.start(1))
                    documented[code] = (str(pr.path), line, col)
    out = []
    for code in sorted(set(documented) - set(raised) - {0}):
        path, line, col = documented[code]
        out.append(Finding(
            "AA501", path,
            f"prose documents exit {code}, which the source never raises",
            str(code), line, col,
        ))
    for code in sorted(set(raised) - set(documented) - {0, 1}):
        path, line, col = raised[code]
        out.append(Finding(
            "AA502", path, f"exit {code} is raised and never documented",
            str(code), line, col,
        ))
    return out


def check_command_coverage(root: Path, prose: list[Prose]) -> list[Finding]:
    """Every command has a workflow, and every workflow has a command."""
    cmd_dir = root / "commands"
    if not cmd_dir.is_dir():
        return []
    plugin_name = _plugin_name(root)
    skills = [pr for pr in prose if pr.path.name == "SKILL.md"]
    skill_blob = "\n".join(pr.text for pr in skills)
    out = []
    for cmd in sorted(cmd_dir.glob("*.md")):
        slug = f"/{plugin_name}:{cmd.stem}" if plugin_name else f"/{cmd.stem}"
        if skills and slug not in skill_blob:
            out.append(Finding(
                "AA601", str(cmd),
                f"{slug} has a command file and no workflow in any SKILL.md",
                slug,
            ))
    for pr in skills:
        for slug in sorted(set(re.findall(r"(/[a-z][\w-]*:[a-z][\w-]*)", pr.text))):
            name = slug.split(":", 1)[1]
            if not (cmd_dir / f"{name}.md").is_file():
                line, col = _at(pr.text, pr.text.find(slug))
                out.append(Finding(
                    "AA602", str(pr.path),
                    f"skill names {slug}, and commands/{name}.md does not exist",
                    slug, line, col,
                ))
    return out


def check_frontmatter(prose: list[Prose]) -> list[Finding]:
    out = []
    for pr in prose:
        if pr.path.name != "SKILL.md":
            continue
        m = re.match(r"^---\n(.*?)\n---\n", pr.text, re.S)
        if not m:
            out.append(Finding(
                "AA001", str(pr.path), "no YAML frontmatter", pr.path.parent.name, 1,
            ))
            continue
        head = m.group(1)
        offset = m.start(1)
        name = re.search(r"^name:\s*(.+)$", head, re.M)
        desc = re.search(r"^description:\s*(.+(?:\n\s+.+)*)$", head, re.M)
        if not name:
            # Not fatal: the directory name is used when `name:` is absent.
            # Reported anyway, because a plugin where some skills declare it
            # and others do not is a plugin where nobody decided.
            out.append(Finding(
                "AA002", str(pr.path),
                "frontmatter has no `name`; the directory name is used instead",
                pr.path.parent.name, 1,
            ))
        elif name.group(1).strip() != pr.path.parent.name:
            line, col = _at(pr.text, offset + name.start(1))
            out.append(Finding(
                "AA003", str(pr.path),
                f"name `{name.group(1).strip()}` does not match directory "
                f"`{pr.path.parent.name}`",
                name.group(1).strip(), line, col,
            ))
        if not desc:
            out.append(Finding(
                "AA004", str(pr.path), "frontmatter has no `description`",
                pr.path.parent.name, 1,
            ))
        elif len(desc.group(1)) < 80:
            line, col = _at(pr.text, offset + desc.start(1))
            out.append(Finding(
                "AA005", str(pr.path),
                f"description is {len(desc.group(1))} characters; too thin to route on",
                pr.path.parent.name, line, col,
            ))
    return out


# --------------------------------------------------------------------------
# allowlist
# --------------------------------------------------------------------------

def read_allow(root: Path) -> dict[str, str]:
    """Identifiers whose treatment is a decision somebody has already made.

    One flat list, two meanings, because both are the same act: an evidence key
    the skill deliberately does not teach, or an identifier the prose cites
    without owning. Either way the entry says "this was considered", and the
    text after the `#` says why.
    """
    path = root / ALLOW_FILE
    if not path.is_file():
        return {}
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, _, reason = line.partition("#")
        out[key.strip()] = reason.strip()
    return out


def write_allow(
    root: Path,
    keys: dict[str, tuple[str, int, int | None]],
    prose: list[Prose],
    source_text: str,
) -> int:
    blob = "\n".join(pr.text for pr in prose)
    unread = sorted(k for k in keys if k not in blob)
    foreign = sorted({
        tok
        for pr in prose
        for tok in pr.tokens
        if _looks_like_identifier(tok)
        and (tok.split(".")[-1] if "." in tok else tok) not in source_text
    })
    path = root / ALLOW_FILE
    lines = [
        "# Identifiers whose treatment is a decision somebody has already made.",
        "#",
        "# Baseline, written by `lint_agent_app.py --init-allow`. Every line is",
        "# still an open question until someone replaces the TODO with a reason.",
        "# A line with no reason is a decision nobody has made yet.",
    ]
    if unread:
        lines += [
            "",
            "# --- emitted by the tool, not taught by the prose ---",
            "# Teach it in the skill, or say here why the model has no use for it.",
            "",
        ]
        lines += [f"{k}  # TODO: teach it, or say why not" for k in unread]
    if foreign:
        lines += [
            "",
            "# --- cited by the prose, not owned by this tool ---",
            "# Another app's field quoted as an example, or a flag of a tool this",
            "# one only mentions. Say whose it is.",
            "",
        ]
        lines += [f"{k}  # TODO: say whose identifier this is" for k in foreign]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(unread) + len(foreign)


# --------------------------------------------------------------------------
# the findings payload, and putting it somewhere a later run can read
# --------------------------------------------------------------------------

def payload(root: Path, shape: Shape, findings: list[Finding], cov: Coverage) -> dict:
    """The machine-readable report, assembled once.

    Both channels that carry findings — `--json` on stdout and the file
    `--emit` writes — are built from here, so a consumer of one is never
    reading a different structure from a consumer of the other.
    """
    return {
        "root": str(root),
        "classification": shape.as_dict(),
        "findings": [f.as_dict() for f in findings],
        "coverage": {
            "prose_files": cov.prose_files,
            "source_files_read": len(cov.source_files),
            "checks_skipped": cov.skipped,
        },
    }


def inputs_read(root: Path) -> list[Path]:
    """Every file a run reads on its way to a finding.

    Prose and source are the two anybody would name. The allowlist and the
    plugin manifest are the two that get forgotten and that silently change the
    answer: an `.agent-app-allow` line retires a finding, and the manifest's
    `name` decides what a command's slug is. Hashing only the obvious two would
    call a payload current after exactly the edits most likely to have
    invalidated it.
    """
    out: set[Path] = {pr.path for pr in collect_prose(root)}
    out |= set(collect_sources(root, set()))
    for extra in (root / ALLOW_FILE, root / ".claude-plugin" / "plugin.json",
                  root / "hooks" / "hooks.json", root / ".mcp.json"):
        if extra.is_file():
            out.add(extra)
    return sorted(out)


def _digest(path: Path) -> str:
    """Truncated, because this establishes that a file moved, nothing more.

    Sixteen hex digits is far past coincidence for a working tree and short
    enough that the hashes stay a footnote in the payload rather than most of
    it. Anyone needing a hash to survive an adversary needs a different tool.
    """
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def tree_state(root: Path) -> dict[str, str]:
    """Repo-relative path -> digest, for everything the run read.

    Relative on purpose: a payload emitted in one checkout is then answerable
    in another, which is what lets CI emit in one job and consume in the next.
    """
    return {_rel(p, root): _digest(p) for p in inputs_read(root)}


def tree_hash(state: dict[str, str]) -> str:
    """One digest over the whole read set — the thing worth quoting in a log."""
    h = hashlib.sha256()
    for path in sorted(state):
        h.update(f"{path}\0{state[path]}\0".encode())
    return h.hexdigest()[:16]


def resolve_emit(arg: str, root: Path) -> Path:
    """`--emit` with no value, or with a directory, lands on the default name."""
    if not arg:
        return root / EMIT_FILE
    target = Path(arg)
    return target / EMIT_FILE if target.is_dir() else target


def emit_findings(
    path: Path, root: Path, shape: Shape, findings: list[Finding],
    cov: Coverage, only: str, wide: bool,
) -> dict:
    """Write the payload, plus what a later reader needs to distrust it.

    The `provenance` block is the difference between this file and `--json`,
    and it is why it is only in this one. A session reading stdout has no
    staleness question — the run it is reading just happened. A file outlives
    the tree it describes, so it has to carry enough to say so: what the run
    read and what those files hashed to, and which flags shaped the result,
    since a payload written under `--only` holds one check's findings and
    reads exactly like a clean run of all of them.
    """
    state = tree_state(root)
    data = {"format": EMIT_FORMAT, **payload(root, shape, findings, cov)}
    data["provenance"] = {
        "emitted_by": "lint_agent_app.py",
        "only": only,
        "wide": wide,
        "tree_hash": tree_hash(state),
        "files": state,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return data


def check_emit(path: Path, root: Path) -> tuple[str, dict]:
    """Does an emitted payload still describe this tree?

    Returns a status and its evidence. `unusable` covers every way the file
    cannot answer the question — absent, unparseable, written by something
    else, written in a format this build does not know — because they all mean
    the same thing to a caller: you do not have findings, go and get some.
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return "unusable", {"reason": f"no such file: {path}"}
    except (OSError, json.JSONDecodeError) as exc:
        return "unusable", {"reason": f"cannot read {path}: {exc}"}
    prov = data.get("provenance") if isinstance(data, dict) else None
    if not isinstance(prov, dict) or not isinstance(prov.get("files"), dict):
        return "unusable", {"reason": f"{path} carries no provenance block; it "
                                      "was not written by --emit"}
    seen = data.get("format")
    if seen != EMIT_FORMAT:
        # Naming which half is old matters: the reflex on a version mismatch is
        # to re-emit, and that is the wrong move when this linter is the old one.
        older = "this linter" if isinstance(seen, int) and seen > EMIT_FORMAT else "the file"
        return "unusable", {"reason": f"{path} is format {seen}, and this build "
                                      f"knows {EMIT_FORMAT} — {older} is the old half"}
    was, now = prov["files"], tree_state(root)
    detail = {
        "changed": sorted(p for p in set(now) & set(was) if now[p] != was[p]),
        "added": sorted(set(now) - set(was)),
        "removed": sorted(set(was) - set(now)),
    }
    moved = sum(len(v) for v in detail.values())
    return ("current" if not moved else "stale"), detail


# --------------------------------------------------------------------------
# report
# --------------------------------------------------------------------------

# A gap is either a check that never ran, a check that ran over less than the
# whole app, or a caveat on how to read what it found. Collapsing the three
# into one word would be the same overstatement this linter exists to catch.
#
# `not-applicable` is not a gap at all, and is the fourth for exactly that
# reason. A check that presupposes something the artifact never claimed —
# a tool half, an invocation — has nothing to say about it, and filing that
# under the same word as "did not run" reports an absence as a deficiency.
NOT_APPLICABLE = "not-applicable"
KIND_LABEL = {"not-run": "not run", "partial": "partial", "note": "note",
              NOT_APPLICABLE: "n/a"}
KIND_ORDER = {"not-run": 0, "partial": 1, "note": 2, NOT_APPLICABLE: 3}


def _unmeasured(cov: Coverage) -> list[dict]:
    """The gaps that are really gaps: something checkable went unchecked."""
    return [s for s in cov.skipped if s["kind"] != NOT_APPLICABLE]


def _inapplicable(cov: Coverage) -> list[dict]:
    return [s for s in cov.skipped if s["kind"] == NOT_APPLICABLE]


def _count(n: int, one: str, many: str = "") -> str:
    return f"{n} {one}" if n == 1 else f"{n} {many or one + 's'}"


def _wrap(text: str, head: str, indent: str) -> str:
    """Wrap, without ever splitting a token the reader has to retype.

    `--init-allow` broken across a line boundary stops being a flag somebody
    can copy, which is most of what a hint is for.
    """
    return textwrap.fill(
        text, width=WIDTH, initial_indent=head, subsequent_indent=indent,
        break_on_hyphens=False, break_long_words=False,
    )


def _gap_tail(cov: Coverage) -> str:
    """The coverage gaps, compressed to fit on the summary line."""
    if not cov.skipped:
        return ""
    kinds = [s["kind"] for s in cov.skipped]
    parts = []
    if kinds.count("not-run"):
        parts.append(_count(kinds.count("not-run"), "check") + " not run")
    if kinds.count("partial"):
        parts.append(_count(kinds.count("partial"), "partial check"))
    if kinds.count("note"):
        parts.append(_count(kinds.count("note"), "note"))
    if kinds.count(NOT_APPLICABLE):
        parts.append(_count(kinds.count(NOT_APPLICABLE), "check") + " not applicable")
    return " — " + ", ".join(parts)


def _shape_line(shape: Shape) -> str:
    """One line saying what was found to lint, before saying anything about it."""
    entries = (_count(len(shape.entry_points), "entry point")
               if shape.entry_points else "no entry point")
    tools = (_count(len(shape.tools), "first-party tool")
             if shape.tools else "no first-party tool")
    tail = ("" if shape.tools or not shape.invocable
            else " — the prose is the whole implementation")
    return f"shape: {entries}, {tools}{tail}"


def _print_findings(findings: list[Finding], verbose: bool) -> None:
    order = sorted(findings, key=lambda f: (f.file, f.line or 0, f.col or 0, f.code))
    groups: dict[tuple[str, str], list[Finding]] = {}
    for f in order:
        groups.setdefault((f.file, f.code), []).append(f)
    printed: set[tuple[str, str]] = set()
    for f in order:
        key = (f.file, f.code)
        group = groups[key]
        if verbose or len(group) <= COLLAPSE_AT:
            print(f"{f.loc}: {f.severity} {f.code} {f.message}")
            continue
        if key in printed:
            continue
        printed.add(key)
        print(f"{f.file}: {f.severity} {f.code} {f.check} ×{len(group)}")
        subjects = ", ".join(g.subject or g.loc for g in group)
        print(_wrap(subjects, "    ", "    "))


def _print_rules(findings: list[Finding]) -> None:
    """One line per rule that fired: what it was, how many, what to do."""
    counts: dict[str, int] = {}
    for f in findings:
        counts[f.code] = counts.get(f.code, 0) + 1
    rows = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    cw = max(len(RULES[c].check) for c, _ in rows)
    nw = max(len(str(n)) for _, n in rows)
    print("fix by rule")
    for code, n in rows:
        rule = RULES[code]
        print(f"  {code}  {rule.check:<{cw}}  ×{n:<{nw}}  {rule.hint}")


def _print_unmeasured(rows: list[dict]) -> None:
    print("NOT CHECKED — a check that did not run in full is not one that passed")
    rows = sorted(rows, key=lambda s: (KIND_ORDER[s["kind"]], s["check"]))
    kw = max(len(KIND_LABEL[s["kind"]]) for s in rows)
    nw = max(len(s["check"]) for s in rows)
    for s in rows:
        head = f"  {KIND_LABEL[s['kind']]:<{kw}}  {s['check']:<{nw}}  "
        print(_wrap(s["reason"], head, " " * len(head)))


def _print_inapplicable(rows: list[dict]) -> None:
    """Kept apart from NOT CHECKED, and worded so it cannot read as a defect."""
    print("NOT APPLICABLE — these presuppose something this artifact does not have")
    nw = max(len(s["check"]) for s in rows)
    for s in sorted(rows, key=lambda s: s["check"]):
        head = f"  {s['check']:<{nw}}  "
        print(_wrap(s["reason"], head, " " * len(head)))


def render_emit_check(path: Path, status: str, detail: dict) -> None:
    """One line for a machine to branch on, then the paths a person needs.

    The exit status is the answer; this is the part that says which file moved,
    because "stale" with nothing named is a report that sends the reader back
    to `git status` to work out what this run already knew.
    """
    if status == "unusable":
        print(detail["reason"], file=sys.stderr)
        return
    if status == "current":
        print(f"current: {path} still describes this tree")
        return
    kinds = [k for k in ("changed", "added", "removed") if detail[k]]
    print(f"stale: {path} was written before "
          + ", ".join(f"{_count(len(detail[k]), 'file')} {k}" for k in kinds))
    for kind in kinds:
        for rel in detail[kind]:
            print(f"  {kind:<7}  {rel}")


def render(
    findings: list[Finding], cov: Coverage, root: Path,
    verbose: bool = False, only: str = "", shape: Shape | None = None,
) -> None:
    """The console report: what fired, where, and what to do about each kind.

    Paths are relative to the inspected root, one line per finding, and every
    explanation appears exactly once — the reader has to be able to act on this
    without scrolling back through the same sentence repeated per finding.
    """
    if root != Path.cwd():
        print(f"root: {root}")
    if shape is not None:
        print(_shape_line(shape))
        if shape.warning:
            print(_wrap(shape.warning, "warning: ", "         "))
    if findings:
        errors = sum(1 for f in findings if f.severity == "error")
        files = {f.file for f in findings}
        print(f"{_count(len(findings), 'finding')} "
              f"({_count(errors, 'error')}, "
              f"{_count(len(findings) - errors, 'warning')}) "
              f"in {_count(len(files), 'file')}{_gap_tail(cov)}")
        print()
        _print_findings(findings, verbose)
        print()
        _print_rules(findings)
    else:
        read = (f"{_count(len(cov.prose_files), 'prose file')}, "
                f"{_count(len(cov.source_files), 'source file')}")
        head = f"no {only} findings" if only else "clean"
        if _unmeasured(cov):
            print(f"{head}: {read}{_gap_tail(cov)} — unmeasured is not clean")
        elif cov.skipped:
            # Every gap is an inapplicable check. Nothing went unmeasured, so
            # the warning that belongs on a real gap would be a false alarm.
            print(f"{head}: {read}{_gap_tail(cov)}")
        else:
            print(f"{head}: {read}" + ("" if only else ", every check ran"))
    if _unmeasured(cov):
        print()
        _print_unmeasured(_unmeasured(cov))
    if _inapplicable(cov):
        print()
        _print_inapplicable(_inapplicable(cov))


# --------------------------------------------------------------------------
# driver
# --------------------------------------------------------------------------

def run(
    root: Path, wide: bool = False, force: set[str] | None = None,
) -> tuple[list[Finding], Coverage, dict, Shape]:
    force = force or set()
    cov = Coverage()
    prose = collect_prose(root)
    skill_dirs = {p.path.parent for p in prose if p.path.name == "SKILL.md"}
    sources = collect_sources(root, skill_dirs)
    cov.prose_files = [p.path.relative_to(root).as_posix() for p in prose]
    cov.source_files = [p.relative_to(root).as_posix() for p in sources]
    shape = describe_shape(root, prose, sources)

    if not prose:
        cov.skip("all", "no SKILL.md or commands/*.md found under root")
        return [], cov, {}, shape

    # Settle applicability before anything runs. A check that does not apply
    # must not also collect a reason for not having run — those are different
    # sentences, and `Coverage.skip` keeps only the first one per check.
    holds = {
        TIER_ANY: True,
        TIER_APP: shape.invocable,
        TIER_TOOL: shape.has_tool_half,
    }
    for check, tier in sorted(CHECK_TIER.items()):
        if holds[tier]:
            continue
        if check in force:
            # Asked for by name. Running it is the answer to the question they
            # asked; saying nothing about the mismatch would not be.
            cov.skip(check, f"{TIER_REASON[tier]} — run anyway, because you "
                            "asked for this check by name", kind="note")
            continue
        cov.skip(check, TIER_REASON[tier], kind=NOT_APPLICABLE)
    off = {s["check"] for s in cov.skipped if s["kind"] == NOT_APPLICABLE}

    source_text = "\n".join(
        p.read_text(encoding="utf-8", errors="replace") for p in sources
    )
    keys = evidence_keys(sources, wide=wide) if "unread" not in off else {}
    if "unread" not in off:
        if not any(p.suffix == ".py" for p in sources):
            cov.skip("unread", "evidence-key extraction is implemented for Python only")
        elif not wide:
            missed = len(evidence_keys(sources, wide=True)) - len(keys)
            if missed > 0:
                cov.skip(
                    "unread-recall",
                    f"{missed} further dict-literal key(s) live outside the "
                    "payload-assembling file and were not examined. A key nested "
                    "into the payload from a helper module is unchecked, not clean "
                    "— rerun with --wide if the answer matters.",
                    kind="partial",
                )

    allow = read_allow(root)
    if keys and not (root / ALLOW_FILE).is_file():
        cov.skip(
            "unread-baseline",
            f"no {ALLOW_FILE}, so every unread key is reported, including "
            "pre-existing ones. Run --init-allow to baseline.",
            kind="note",
        )

    findings: list[Finding] = []
    findings += check_frontmatter(prose)
    if "stale-ref" not in off:
        findings += check_stale_refs(prose, source_text, allow, cov)
    if "rederive" not in off:
        findings += check_rederivation(prose, allow)
    if "unread" not in off:
        findings += check_unread_evidence(prose, keys, allow, cov)
    findings += check_xrefs(prose)
    if "exit-code" not in off:
        findings += check_exit_codes(prose, sources, cov)
    findings += check_command_coverage(root, prose)
    for f in findings:
        try:
            f.file = Path(f.file).relative_to(root).as_posix()
        except ValueError:
            pass
    return findings, cov, keys, shape


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="lint_agent_app",
        description="Check that an agent app's prose and its tool still agree.",
    )
    ap.add_argument("--root", default=".", type=Path,
                    help="plugin root to check (default: cwd)")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--init-allow", action="store_true",
                    help=f"write a {ALLOW_FILE} baseline of every currently "
                         "unread evidence key, then exit")
    ap.add_argument("--emit", metavar="PATH", nargs="?", const="", default=None,
                    help="also write the findings payload to PATH, with a content "
                         "hash of every file the run read, so a later step can tell "
                         f"whether it still applies (default: {EMIT_FILE} in the "
                         "root). The console report is unchanged")
    ap.add_argument("--check-emit", metavar="PATH", nargs="?", const="", default=None,
                    help="report whether an emitted payload still describes the "
                         f"tree (default: {EMIT_FILE} in the root), then exit "
                         "without linting anything")
    ap.add_argument("--only", metavar="CHECK", default="",
                    help="report only this check or rule code")
    ap.add_argument("--wide", action="store_true",
                    help="extract evidence keys from every module, not just the "
                         "one that writes the payload (higher recall, more noise)")
    ap.add_argument("-v", "--verbose", action="store_true",
                    help="print every finding, never collapsing a rule that "
                         "fired repeatedly in one file")
    args = ap.parse_args(argv)

    root: Path = args.root.resolve()
    if not root.is_dir():
        print(f"not a directory: {root}", file=sys.stderr)
        return 2

    # Three modes, and each writes or reads something the others do not. Asking
    # for two at once is a sentence with no meaning, and running one of them
    # silently would leave the caller believing the other also happened.
    modes = [name for name, on in (("--init-allow", args.init_allow),
                                   ("--emit", args.emit is not None),
                                   ("--check-emit", args.check_emit is not None))
             if on]
    if len(modes) > 1:
        print(f"{' and '.join(modes)} do different jobs; pick one", file=sys.stderr)
        return 2

    if args.check_emit is not None:
        target = resolve_emit(args.check_emit, root)
        status, detail = check_emit(target, root)
        if args.json and status != "unusable":
            print(json.dumps({"status": status, "emit": str(target), **detail},
                             indent=2))
        else:
            render_emit_check(target, status, detail)
        # Spelled out rather than looked up in a dict. A status a reader cannot
        # find by looking for `return` is one nobody documents, which is the
        # AA502 defect this linter reports in other people's tools — and it
        # reported it here first.
        if status == "current":
            return 0
        if status == "stale":
            return 3
        return 2

    only = args.only.strip()
    if only and only not in CHECKS and only.upper() not in RULES:
        # A typo must not read as a clean run. That is the exact failure this
        # linter exists to prevent, and it would be one line of output away.
        print(f"unknown check or rule code: {only}\n"
              f"checks: {', '.join(CHECKS)}\n"
              f"codes:  {', '.join(sorted(RULES))}", file=sys.stderr)
        return 2

    if args.init_allow:
        prose = collect_prose(root)
        sources = collect_sources(root, set())
        keys = evidence_keys(sources, wide=args.wide)
        source_text = "\n".join(
            p.read_text(encoding="utf-8", errors="replace") for p in sources
        )
        if not keys and not source_text:
            print("no tool found; nothing to baseline", file=sys.stderr)
            return 2
        n = write_allow(root, keys, prose, source_text)
        print(f"wrote {root / ALLOW_FILE} with {n} unread key(s) to triage")
        return 0

    # Naming a check overrides its tier: the question was asked directly, so
    # the honest answer is the check's own, not "that does not apply here".
    asked = RULES[only.upper()].check if only.upper() in RULES else only
    findings, cov, _, shape = run(root, wide=args.wide, force={asked} if only else set())
    if only:
        if only.upper() in RULES:
            check = RULES[only.upper()].check
            findings = [f for f in findings if f.code == only.upper()]
        else:
            check = only
            findings = [f for f in findings if f.check == check]
        # Narrow the coverage gaps to the same question. A gap in `unread`
        # is not an answer being withheld from someone who asked about
        # `rederive`; it is a different question they did not ask.
        cov.skipped = [s for s in cov.skipped if s["check"] == "all"
                       or s["check"] == check or s["check"].startswith(check + "-")]

    if args.json:
        print(json.dumps(payload(root, shape, findings, cov), indent=2))
    else:
        render(findings, cov, root, verbose=args.verbose, only=only, shape=shape)

    if args.emit is not None:
        target = resolve_emit(args.emit, root)
        try:
            data = emit_findings(target, root, shape, findings, cov, only, args.wide)
        except OSError as exc:
            # Louder than the findings it failed to write. A caller told nothing
            # goes looking for a file that is not there, or reads an older one.
            print(f"could not write {target}: {exc}", file=sys.stderr)
            return 2
        # Never on stdout under --json: a human line inside the payload would
        # break the one consumer that channel exists for.
        print(f"emitted {target} — {_count(len(findings), 'finding')}, "
              f"tree {data['provenance']['tree_hash']}",
              file=sys.stderr if args.json else sys.stdout)

    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
