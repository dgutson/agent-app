#!/usr/bin/env python3
"""Write and maintain the `.ag` file that makes an agent app runnable from a shell.

The format's rules live in exactly one place — `launcher/agent-app-launcher`,
which enforces them — and this script never restates them. It works out what
the file should say, writes it to a temporary file beside the target, and asks
the launcher to accept it: `agent-app-launcher <file> --help` exercises key
validation, plugin resolution, command parsing and `default-command` validity
in about 40ms with no model started. Only a file the launcher accepts is
renamed into place, so a written `.ag` is never one that cannot run.

That is also why the dependency is a subprocess rather than an import. The
launcher is deliberately external to this plugin; invoking it degrades to "the
file was written but not proved runnable" when it is absent, where importing it
would fail outright.

**It never removes a key it did not add.** A key it cannot account for is
reported and the write refuses, because a key this script does not recognise is
at least as likely to come from a newer launcher as from a typo, and deleting
the author's line is the one repair that cannot be undone.

What is left for the prose is the judgment a script has no basis for: whether
*this* app should declare a `default-command`, and what to do when the app is
also installed somewhere other than the tree in front of you.

Exit codes: `0` the `.ag` is current, `1` it would change, `2` usage error or
the app cannot be resolved.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

SHEBANG = "#!/usr/bin/env agent-app-launcher"

# How a plan step is rendered. `keep` is reported rather than silently omitted,
# because "nothing you wrote was discarded" is a claim worth showing.
MARKS = {"keep": " ", "add": "+", "fix": "~", "drop": "-"}
PENDING = {"add", "fix", "drop"}


def frontmatter(path: Path) -> dict:
    """The YAML frontmatter of a markdown file, as a mapping."""
    m = re.match(r"^---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|$)",
                 path.read_text(encoding="utf-8", errors="replace"), re.S)
    try:
        block = yaml.safe_load(m.group(1)) if m else None
    except yaml.YAMLError:
        return {}
    return block if isinstance(block, dict) else {}


def launcher_path() -> Path | None:
    """The launcher, from the plugin it ships in or from `PATH`."""
    local = Path(__file__).resolve().parent.parent / "launcher" / "agent-app-launcher"
    if local.is_file():
        return local
    found = shutil.which("agent-app-launcher")
    return Path(found) if found else None


def validate(ag: Path) -> dict:
    """Ask the launcher whether it would run this file.

    `--help` is answered from the declaration with no model started, so it is
    the cheapest proof available that a file resolves, parses and names real
    commands. Its stderr is the diagnosis, in the launcher's own words.
    """
    exe = launcher_path()
    if exe is None:
        return {"ran": False, "exit": None,
                "stderr": "agent-app-launcher was not found, so the file was "
                          "written but not proved runnable"}
    try:
        done = subprocess.run([sys.executable, str(exe), str(ag), "--help"],
                              capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError) as exc:
        return {"ran": False, "exit": None, "stderr": str(exc)}
    return {"ran": True, "exit": done.returncode, "stderr": done.stderr.strip()}


def read_app(root: Path) -> tuple[str, dict, list[str]]:
    """The app's name and declared commands — the one source both halves read."""
    problems: list[str] = []
    name = root.name
    manifest = root / ".claude-plugin" / "plugin.json"
    if manifest.is_file():
        try:
            name = json.loads(manifest.read_text()).get("name") or root.name
        except (OSError, ValueError):
            problems.append(f"{manifest} is not readable JSON, so the app's "
                            f"name falls back to the directory name {root.name!r}")

    cmds: dict[str, dict] = {}
    cmd_dir = root / "commands"
    if not cmd_dir.is_dir():
        problems.append(f"{root} has no commands/ directory, so it declares "
                        f"nothing to invoke")
        return name, cmds, problems
    for p in sorted(cmd_dir.glob("*.md")):
        fm = frontmatter(p)
        cmds[p.stem] = {
            "description": str(fm.get("description") or "").strip(),
            "argument_hint": str(fm.get("argument-hint") or "").strip(),
        }
    if not cmds:
        problems.append(f"{cmd_dir} holds no *.md, so the app declares nothing "
                        f"to invoke")
    return name, cmds, problems


def registry() -> dict[str, Path]:
    """Installed plugin key -> install path, from the harness's own record.

    `installed_plugins.json` carries `installPath` outright, so the cache
    layout is never reassembled here.
    """
    config = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
    out: dict[str, Path] = {}
    try:
        plugins = json.loads(
            (config / "plugins" / "installed_plugins.json").read_text())["plugins"]
    except (OSError, ValueError, KeyError):
        return out
    for key, entries in plugins.items():
        for entry in entries:
            if entry.get("installPath"):
                out[key] = Path(entry["installPath"]).resolve()
                break
    return out


def resolve(root: Path, target: Path, name: str) -> dict:
    """`plugin:` when the root *is* an installed copy, `plugin-dir:` otherwise.

    The test is the path, not the name. A source tree whose name happens to be
    installed elsewhere is still a tree, and saying `plugin:` there would write
    a file that runs a different copy than the one it sits in — which is the
    staleness trap, committed.
    """
    installed = registry()
    here = sorted(k for k, p in installed.items() if p == root)
    if here:
        key = here[0]
        bare = key.split("@", 1)[0]
        twins = sum(1 for k in installed if k.split("@", 1)[0] == bare)
        return {"key": "plugin", "value": key if twins > 1 else bare,
                "installed_as": key, "install_path": str(installed[key]),
                "note": None}

    rel = os.path.relpath(root, target.parent)
    elsewhere = sorted(k for k, p in installed.items()
                       if k.split("@", 1)[0] == name and p != root)
    note = None
    if elsewhere:
        note = (f"{name!r} is also installed, as {elsewhere[0]} at "
                f"{installed[elsewhere[0]]} — a different directory from this "
                f"one. `plugin: {name}` would run that copy rather than the "
                f"tree this file sits in.")
    return {"key": "plugin-dir", "value": rel if rel.startswith(".") else f"./{rel}",
            "installed_as": elsewhere[0] if elsewhere else None,
            "install_path": str(installed[elsewhere[0]]) if elsewhere else None,
            "note": note}


def build_plan(root: Path, target: Path, cmds: dict, existing: dict, res: dict,
               default, seconds, summary) -> tuple[list[dict], list[str]]:
    """What the file should gain or have corrected — never what it should lose.

    The three judgment arguments are instructions, not preferences: `None` means
    "no instruction", and every key the caller says nothing about is left
    exactly as its author wrote it.
    """
    plan: list[dict] = []
    problems: list[str] = []

    if "plugin" in existing:
        plan.append({"key": "plugin", "action": "keep", "value": existing["plugin"],
                     "why": "names an installed app; left as its author wrote it"})
    elif "plugin-dir" in existing:
        cur = str(existing["plugin-dir"])
        points = (target.parent / cur).resolve()
        if points == root:
            plan.append({"key": "plugin-dir", "action": "keep", "value": cur,
                         "why": "already resolves to this app"})
        else:
            plan.append({"key": "plugin-dir", "action": "fix", "value": res["value"],
                         "why": f"{cur!r} resolves to {points}, which is not {root}"})
    else:
        plan.append({"key": res["key"], "action": "add", "value": res["value"],
                     "why": "the file must name an app, and this is the one at --root"})

    cur = existing.get("default-command")
    choice = default
    if choice is False:
        if cur is not None:
            plan.append({"key": "default-command", "action": "drop", "value": None,
                         "why": "asked for, so the app keeps its unknown-command "
                                "diagnostic"})
    elif choice is not None:
        if choice not in cmds:
            problems.append(f"--default-command {choice!r} is not one of "
                            f"{', '.join(sorted(cmds)) or 'this app has no commands'}")
        elif choice == cur:
            plan.append({"key": "default-command", "action": "keep", "value": cur,
                         "why": "already what was asked for"})
        else:
            plan.append({"key": "default-command",
                         "action": "add" if cur is None else "fix", "value": choice,
                         "why": "chosen for this app"})
    elif cur is not None:
        if cur in cmds:
            plan.append({"key": "default-command", "action": "keep", "value": cur,
                         "why": "the author's choice, and still a real command"})
        else:
            problems.append(
                f"default-command {cur!r} is not one of {', '.join(sorted(cmds))}, "
                f"so the launcher refuses the file. Removing it and naming a real "
                f"command are different repairs; say which with --default-command "
                f"or --no-default-command.")

    for key, val in (("timeout", seconds), ("description", summary)):
        if val is None:
            if key in existing:
                plan.append({"key": key, "action": "keep", "value": existing[key],
                             "why": "the author's value, and no instruction to change it"})
        elif existing.get(key) == val:
            plan.append({"key": key, "action": "keep", "value": val,
                         "why": "already set to that"})
        else:
            plan.append({"key": key, "action": "add" if key not in existing else "fix",
                         "value": val, "why": "given on the command line"})
    return plan, problems


def emit(key: str, value) -> str:
    """One `key: value` line, quoted by the YAML dumper rather than by hand."""
    return yaml.safe_dump({key: value}, default_flow_style=False,
                          sort_keys=False, allow_unicode=True).strip()


def merge(text: str, plan: list[dict]) -> str:
    """Existing lines survive verbatim; only planned keys are rewritten.

    Line-oriented on purpose. Round-tripping through the YAML loader would
    discard the comments and the ordering its author chose, which is the same
    overreach as a linter rewriting the app it was asked to report on.
    """
    changes = {step["key"]: step for step in plan if step["action"] in PENDING}
    lines = text.splitlines() if text.strip() else []
    if not lines or not lines[0].startswith("#!"):
        lines.insert(0, SHEBANG)

    out: list[str] = []
    seen: set[str] = set()
    for line in lines:
        m = re.match(r"([A-Za-z][\w-]*)\s*:", line)
        key = m.group(1) if m else None
        if key is not None:
            seen.add(key)
        step = changes.get(key) if key else None
        if step is None:
            out.append(line)
        elif step["action"] != "drop":
            out.append(emit(key, step["value"]))
    out += [emit(k, s["value"]) for k, s in changes.items()
            if k not in seen and s["action"] != "drop"]
    return "\n".join(out).rstrip("\n") + "\n"


def write_file(target: Path, text: str) -> tuple[Path | None, dict]:
    """Write only a file the launcher accepts, and never leave a broken one.

    The temporary file is created beside the target rather than in a temp
    directory, because `plugin-dir` resolves relative to the `.ag` file — a
    proposal validated somewhere else would be validating a different path.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=target.parent, prefix=".ag-", suffix=".ag")
    tmp = Path(name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        checked = validate(tmp)
        # The proposal was judged under a temporary name the caller will never
        # see again; the diagnosis has to name the file they were asking about.
        checked["stderr"] = checked["stderr"].replace(str(tmp), str(target))
        if checked["ran"] and checked["exit"] != 0:
            return None, checked
        os.chmod(tmp, 0o755)
        os.replace(tmp, target)
        return target, checked
    finally:
        if tmp.exists():
            tmp.unlink()


def render(payload: dict) -> None:
    print(f"{payload['name']}  ->  {payload['target']}")
    for step in payload["plan"]:
        value = "" if step["value"] is None else f" {step['value']}"
        print(f"  {MARKS[step['action']]} {step['key']}{value}"
              f"    — {step['why']}")
    if payload["resolution"]["note"]:
        print(f"  note: {payload['resolution']['note']}")
    for problem in payload["problems"]:
        print(f"  problem: {problem}")
    if payload["written"]:
        print(f"wrote {payload['written']}")
    # A failed validation is already stated as a problem; printing its stderr
    # again would report one fault twice. Only the case nothing else covers —
    # the launcher was not there to ask — is worth a line of its own.
    checked = payload["validated"]
    if checked["ran"] is False and checked["stderr"]:
        print(f"  unverified: {checked['stderr']}")
    print(payload["verdict"])


def main(argv=None) -> int:
    cli = argparse.ArgumentParser(
        description="Write and maintain an agent app's .ag file.",
        epilog="exit: 0 the .ag is current, 1 it would change, 2 usage or "
               "the app cannot be resolved")
    cli.add_argument("--root", default=".", metavar="DIR",
                     help="the app to describe (default: the current directory)")
    cli.add_argument("--target", metavar="PATH",
                     help="the .ag file to write (default: <root>/<name>.ag)")
    cli.add_argument("--json", action="store_true", help="emit the payload")
    cli.add_argument("--write", action="store_true",
                     help="apply the plan; without it nothing is written")
    group = cli.add_mutually_exclusive_group()
    group.add_argument("--default-command", metavar="NAME",
                       help="declare this command as the default")
    group.add_argument("--no-default-command", action="store_true",
                       help="remove a declared default")
    cli.add_argument("--timeout", type=int, metavar="SEC",
                     help="wall clock for the app's runs")
    cli.add_argument("--description", metavar="TEXT",
                     help="the summary shown under usage: in --help")
    opts = cli.parse_args(argv)

    root = Path(opts.root).expanduser().resolve()
    if not root.is_dir():
        print(f"{cli.prog}: {root} is not a directory", file=sys.stderr)
        return 2

    name, cmds, problems = read_app(root)
    target = (Path(opts.target).expanduser().resolve() if opts.target
              else root / f"{name}.ag")

    text = ""
    existing: dict = {}
    if target.is_file():
        text = target.read_text(encoding="utf-8", errors="replace")
        try:
            loaded = yaml.safe_load(text)
            existing = loaded if isinstance(loaded, dict) else {}
        except yaml.YAMLError as exc:
            problems.append(f"{target} is not readable YAML ({exc}), so nothing "
                            f"in it can be preserved; move it aside to start over")

    res = resolve(root, target, name)
    plan, trouble = build_plan(
        root, target, cmds, existing, res,
        False if opts.no_default_command else opts.default_command,
        opts.timeout, opts.description)
    problems += trouble

    written = None
    checked = {"ran": False, "exit": None, "stderr": ""}
    pending = [s for s in plan if s["action"] in PENDING]
    if opts.write and not problems:
        written, checked = write_file(target, merge(text, plan))
        if written is None:
            problems.append(f"the launcher refused the file: {checked['stderr']}")
    elif target.is_file() and not problems:
        checked = validate(target)
        if checked["ran"] and checked["exit"] != 0:
            problems.append(f"the .ag already there does not run: {checked['stderr']}")

    payload = {
        "root": str(root),
        "name": name,
        "target": str(target),
        "commands": cmds,
        "resolution": res,
        "existing": {"present": target.is_file() and not written,
                     "keys": existing},
        "plan": plan,
        "problems": problems,
        "written": str(written) if written else None,
        "validated": checked,
        "verdict": ("cannot-resolve" if problems else
                    "current" if written or not pending else "would-change"),
    }
    print(json.dumps(payload, indent=2)) if opts.json else render(payload)
    return {"cannot-resolve": 2, "would-change": 1}.get(payload["verdict"], 0)


if __name__ == "__main__":
    sys.exit(main())
