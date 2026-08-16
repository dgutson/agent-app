# The `.ag` file format

An `.ag` file is a YAML document with a shebang on top. Make it executable and
it is a program:

```yaml
#!/usr/bin/env agent-app-launcher
plugin: agent-app
```

```console
$ chmod +x agent-app.ag
$ ./agent-app.ag lint --root .
```

`#!/usr/bin/env agent-app-launcher` is a shebang to the kernel and a comment to
YAML — `#` opens a YAML comment and `#!` is just `#` followed by `!` — so the
whole file parses as one ordinary YAML document with nothing stripped first.

`agent-app-launcher` has to be findable on `PATH` for the shebang to resolve.
Until there is an installer, that is one symlink:

```console
$ ln -s "$PWD/launcher/agent-app-launcher" ~/.local/bin/agent-app-launcher
```

**You should not have to write one of these by hand.** `/agent-app:update-ag`
works out what the file should say for the app in front of it and writes it,
and `/agent-app:create` runs it for every app it generates. This page is the
specification; that command is the author. Everything below is here so the
format has a written definition — not because reading it is a prerequisite to
having a working `.ag`.

## What the file does *not* contain

It **names** an app; it does not restate one. The commands, their usage lines
and their tool grants are read at run time from the plugin's own
`commands/*.md` frontmatter:

| Command frontmatter | Becomes |
|---|---|
| `description` | the command's line in `--help` |
| `argument-hint` | its usage string |
| `allowed-tools` | the grant passed to `claude --allowed-tools` |
| `model` | honoured by the harness itself — the launcher does nothing |

So there is one declaration, and no copy in the `.ag` file that could drift out
of agreement with it. It also means an app written before any of this existed
gets a command line without changing a byte.

**There is deliberately no `model:` key**, and the reason generalises. Measured:
a command whose frontmatter says `model: claude-haiku-4-5-20251001` runs on
haiku, and the same command without the key runs on the session default — the
harness resolves it when the slash command is dispatched, so the launcher never
sees it. An `.ag` key would therefore not merely duplicate that declaration, it
would **override** it. Anything a command can already declare about how it runs
belongs in the command, not here.

## Keys

Every key is optional except that exactly one of `plugin` or `plugin-dir` must
be present. Any other key is an error rather than something ignored: a typo
that is silently dropped is a launcher running something other than what the
file says.

| Key | Value | Meaning |
|---|---|---|
| `plugin` | `name` or `name@marketplace` | An installed plugin. Resolved through `~/.claude/plugins/installed_plugins.json`, whose `installPath` is used as-is. Qualify it with the marketplace when the bare name is ambiguous. |
| `plugin-dir` | path | A plugin directory, resolved **relative to the `.ag` file**, not to the working directory. Use it for an app that is not installed — during development, or one that ships beside the `.ag`. |
| `default-command` | command name | The command to run when the first argument is not one. Lets `./hello.ag Dani` mean `./hello.ag greet Dani`. See the trade-off below. |
| `timeout` | whole seconds | Wall clock for the run. Default 900. `--timeout` overrides it per invocation. |
| `description` | one line | The summary shown under `usage:` in `--help`. Falls back to the plugin manifest's `description`, which is often a paragraph written to sell the plugin rather than to explain the command. |
| `epilog` | free text | Printed after the command list. Replaces the default note about where launcher options bind. Use it for the one thing a user of *this* app should know before running it. |

### `default-command`, mistyped commands, and flags

With a default declared, an unrecognised first argument is treated as an
argument to the default rather than as a bad command. Measured on `hello.ag`:
`./hello.ag shout` does not report `no command 'shout'` — it runs `greet` with
`shout` as the name. For a one-command app that is exactly what you want, since
there is nothing to mistype *into*. For an app with several commands it means
giving up the unknown-command diagnostic, so declare it deliberately.

**The same trade extends to flags.** An app whose interface is options rather
than positionals — `report --output x --format json` — needs to be reachable
without naming its command, so with a default declared, the first flag the
launcher does not itself define begins the app's arguments:

```console
$ ./report.ag --output x --format json      # runs: report --output x --format json
$ ./report.ag --timeout 300 --output x      # --timeout is the launcher's; --output is not
```

The launcher's own options still bind first and still win, which is the cost:
with no command named, an app flag spelled like a launcher flag (`--timeout`,
`--dry-run`) is taken by the launcher. Name the command — `./report.ag report
--timeout 5` — and every argument after it belongs to the app again, as always.

**Without a `default-command`, none of this applies** and an unknown leading
flag is a usage error, as before. This is opt-in for the same reason the
mistyped-command behaviour is.

## The command line

```
<app>.ag [launcher options] <command> [arguments...]
```

**Launcher options come before the command; after it, every argument belongs to
the app** — untouched, including flags of the same name. `--help` is the one
exception and is honoured on either side.

| Option | |
|---|---|
| `--help`, `-h` | The app's commands, or one command's usage. Answered from the declaration with **no model started at all** — `claude` is not even looked up. |
| `--dry-run` | Print the resolved `claude` command line and stop. |
| `--timeout SEC` | Override the file's `timeout`. |

The help is rendered by `argparse` from the options themselves, so the options
section cannot drift out of agreement with the options that exist — which is
the failure this repository is about. Only the command list, the `description`
and the `epilog` are supplied.

## Exit status

`claude -p` exits 0 for any session that completed, whatever the session
concluded, so it cannot carry a verdict. The launcher gets one from the app
through `--json-schema`, which makes the harness enforce the shape rather than
trusting prose to remember it, and maps it to an integer:

| Exit | `status` | Meaning |
|---|---|---|
| 0 | `ok` | The affirmative outcome: clean, current, nothing to do. |
| 1 | `findings` | The negative-but-normal outcome: findings, drift, work outstanding. Not an error. |
| 2 | — | Usage error: bad `.ag` file, unknown command, unknown option. Settled without a model. |
| 3 | `refused` | The app declined; something a safe answer depends on could not be established, and nothing was changed. |
| 4 | `error` | The app ran and failed. |
| 5 | — | No verdict: `claude` missing, a wall-clock kill, or a session that completed without one. |

`status` is a claim about the app's *subject*, not about whether the model
answered: an app that ran correctly and found problems is `findings`, never
`error`.

**stdout carries the app's output and nothing else** — no preamble, no
transcript, no envelope — so an `.ag` file survives a pipe. Everything the
launcher itself has to say goes to stderr, except an answer the launcher *is*
the author of (`--help`, `--dry-run`), exactly as with `git --help`.

There is no `--max-turns` in the Claude Code CLI, so a run is bounded by the
wall clock rather than by a turn count.

## Worked example

`examples/hello.ag`, the smallest agent app there is:

```yaml
#!/usr/bin/env agent-app-launcher
plugin-dir: ./hello
default-command: greet
description: Greet somebody by name, from a shell or a script.
```

with `examples/hello/commands/greet.md`:

```markdown
---
description: Greet somebody by name.
argument-hint: "<name>"
allowed-tools: []
---

Greet `$1` in one short line, warmly and without ceremony.

If no name was given, there is nobody to ask for one: say which argument is
missing and refuse.
```

```console
$ ./hello.ag --help
usage: hello.ag [--help] [--dry-run] [--timeout SEC] [command] ...

Greet somebody by name, from a shell or a script.

positional arguments:
  command        one of the commands below
  args           passed to the app untouched

options:
  --help, -h     this, or a command's own usage
  --dry-run      print the resolved claude command and stop
  --timeout SEC  wall clock for the run (default 900)

commands:
  greet  Greet somebody by name  (default)

Options bind before the command. After it, every argument belongs to the app,
including flags of these same names.

exit: 0 affirmative, 1 negative, 2 usage, 3 refused, 4 failed, 5 no verdict

$ ./hello.ag Dani
Hey Dani, great to see you!
$ echo $?
0

$ ./hello.ag greet          # no name to greet
Missing required argument: name. Usage: /hello:greet <name>
$ echo $?
3
```

## Requirements

Python 3 and PyYAML. A file called YAML is parsed by a YAML parser; a subset
parser that quietly misreads a valid block scalar would be worse than not
claiming the format at all.
