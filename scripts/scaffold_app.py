#!/usr/bin/env python3
"""Create the directory structure and manifest of a new agent app.

Layout is a must-be-identical fact, so it lives here rather than in the prose:
two apps scaffolded a week apart should not disagree about where a skill sits,
and a manifest with a mistyped key is a plugin that will not install. Neither
is worth a model's attention, and both are worth getting right every time.

What it cannot supply is content. The partition, the evidence contract, the
rubric and the honesty rules are the judgment `/agent-app:create` exists to
work out with the user, and a scaffold that wrote placeholder prose would only
produce an app that lints clean while saying nothing.

So it writes the manifest and reports the files that remain, with what each one
needs. Re-run it at any point to see what is still outstanding.

Exit codes: `0` every required file is present, `1` files remain to be written,
`2` usage error, or a name that cannot be a plugin.
"""

import argparse
import json
import re
import sys
from pathlib import Path

# The naming rule every plugin on this machine already follows. Checked rather
# than assumed, because an invalid name fails at install time — long after the
# session that chose it has ended.
SLUG = re.compile(r"^[a-z][a-z0-9-]*$")


def checklist(root: Path, name: str) -> list[dict]:
    """The files an app needs that no scaffold can write for it."""
    out = []
    skill = root / "skills" / name / "SKILL.md"
    if not skill.is_file():
        out.append({
            "path": str(skill.relative_to(root)), "kind": "skill",
            "needs": f"frontmatter `name: {name}` matching its directory, and a "
                     f"`description` of at least 80 characters — that field is "
                     f"what routes the skill, and a thin one is reported",
        })
    commands = sorted((root / "commands").glob("*.md")) if (root / "commands").is_dir() else []
    if not commands:
        out.append({
            "path": "commands/<verb>.md", "kind": "command",
            "needs": "one per workflow, with `description`, `argument-hint` and "
                     "`allowed-tools`. Split those that inspect from those that "
                     "change, and give the inspecting ones no Edit and no Write",
        })
    # A tool half is not required — a prose-only app is an app — so it is only
    # tracked once `--tool` has said this one has it.
    tools = root / "scripts"
    if tools.is_dir() and not any(p.suffix in {".py", ".sh"} for p in tools.iterdir()):
        out.append({
            "path": "scripts/<tool>.py", "kind": "tool",
            "needs": "emits evidence and stops short of the verdict, with the "
                     "payload fields the contract settled and nothing that "
                     "decides what they mean",
        })
    if not list(root.glob("*.ag")):
        out.append({
            "path": f"{name}.ag", "kind": "invocation",
            "needs": "written by /agent-app:update-ag, never by hand",
        })
    return out


def main(argv=None) -> int:
    cli = argparse.ArgumentParser(
        description="Create a new agent app's directories and manifest.",
        epilog="exit: 0 every required file is present, 1 files remain, "
               "2 usage or an unusable name")
    cli.add_argument("--root", required=True, metavar="DIR",
                     help="where the app goes; created if absent")
    cli.add_argument("--name", metavar="NAME",
                     help="the plugin name (default: the directory's)")
    cli.add_argument("--description", metavar="TEXT",
                     help="one line for the manifest, shown wherever it is listed")
    cli.add_argument("--tool", action="store_true",
                     help="this app has an evidence half; make scripts/ too")
    cli.add_argument("--json", action="store_true", help="emit the payload")
    cli.add_argument("--write", action="store_true",
                     help="create them; without it nothing is written")
    opts = cli.parse_args(argv)

    root = Path(opts.root).expanduser().resolve()
    name = opts.name or root.name
    problems: list[str] = []
    if not SLUG.match(name):
        problems.append(f"{name!r} cannot be a plugin name: lowercase letters, "
                        f"digits and hyphens, starting with a letter")

    manifest = root / ".claude-plugin" / "plugin.json"
    created: list[str] = []
    if opts.write and not problems:
        wanted = [root / "commands", root / "skills" / name, manifest.parent]
        if opts.tool:
            wanted.append(root / "scripts")
        for directory in wanted:
            if not directory.is_dir():
                directory.mkdir(parents=True)
                created.append(str(directory.relative_to(root)) + "/")
        # An existing manifest is its author's, exactly as an existing .ag is.
        if not manifest.is_file():
            manifest.write_text(json.dumps({
                "name": name,
                "description": opts.description or "",
                "version": "0.1.0",
            }, indent=2) + "\n")
            created.append(str(manifest.relative_to(root)))
        elif opts.description:
            problems.append(f"{manifest.relative_to(root)} already exists, so its "
                            f"description was left alone; edit it if the app's "
                            f"subject has changed")

    missing = checklist(root, name) if root.is_dir() else []
    if not manifest.is_file() and not problems:
        missing.insert(0, {
            "path": str(manifest.relative_to(root)), "kind": "manifest",
            "needs": "re-run with --write; without it the directory is not a plugin "
                     "and cannot be installed",
        })

    payload = {
        "root": str(root),
        "name": name,
        "manifest": str(manifest),
        "created": created,
        "missing": missing,
        "problems": problems,
        "verdict": ("cannot-scaffold" if problems else
                    "incomplete" if missing else "ready"),
    }
    if opts.json:
        print(json.dumps(payload, indent=2))
    else:
        print(f"{name}  ->  {root}")
        for path in created:
            print(f"  + {path}")
        for item in missing:
            print(f"  missing {item['path']}  ({item['kind']})\n"
                  f"      needs {item['needs']}")
        for problem in problems:
            print(f"  problem: {problem}")
        print(payload["verdict"])
    return {"cannot-scaffold": 2, "incomplete": 1}.get(payload["verdict"], 0)


if __name__ == "__main__":
    sys.exit(main())
