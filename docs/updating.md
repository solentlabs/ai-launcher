# Updating

`ai-launcher update` upgrades AI Launcher to the latest release on PyPI. It runs only when you run
it. By default AI Launcher never checks for a new version on its own; you can
[opt in to a daily check](#checking-automatically).

```bash
ai-launcher update --check   # say whether a newer release exists; change nothing
ai-launcher update           # show the command, ask, then run it
ai-launcher update --yes     # same, without the question (needed without a terminal)
```

## What It Does

1. Asks PyPI (`https://pypi.org/pypi/ai-launcher/json`) for the latest version. That is the only
   network call, and it sends nothing about you or your projects.
2. Compares it with the version you are running. If you are current, it says so and stops.
3. Works out how AI Launcher was installed and shows the matching command before running anything.

| Installed with                           | Command it runs                                      |
| ---------------------------------------- | ---------------------------------------------------- |
| `pipx`                                   | `pipx upgrade ai-launcher`                           |
| `pip install --user` (or a Store Python) | `python -m pip install --user --upgrade ai-launcher` |
| `pip` inside a virtual environment       | `python -m pip install --upgrade ai-launcher`        |
| An editable or source checkout           | Nothing: it tells you to `git pull` and reinstall    |

The command runs as a list of arguments, never through a shell, and the package name is fixed in the
code, so nothing from PyPI's reply is ever run.

## Checking Automatically

Off by default. To be told when a newer release exists, add this to `caches.toml` in the config
folder (`~/.config/ai-launcher/` on Linux and WSL; see [Registry](cache-and-scratch.md#registry)):

```toml
[update]
check = true
```

Then, while the project picker is open, AI Launcher asks PyPI for the latest version in the
background, at most once every 24 hours. If a newer release exists, the launch box shows one line
after you pick a project:

```text
│ 🆕 Update:   0.9.0 is available (you have 0.8.0) · ai-launcher update             │
```

Decisions:

- **Opt-in.** With `check` unset or `false`, nothing contacts PyPI except `ai-launcher update`.
- **Never slows a launch.** The check runs in a background thread while you choose a project. The
  launch box reads the saved result only, so a result found during this picker shows from the next
  launch on.
- **Same request as `update --check`.** One GET to the PyPI URL above, with nothing about you or
  your projects in it. It installs nothing: the line only names the command.
- **Quiet on error.** No network, a timeout, or an unreadable reply means no line, and the check is
  tried again at the next launch. A bug here must not stop a session starting.
- **Once per release.** The line repeats at every launch until you update; it has no snooze.
- **Last result** is kept in `update-check.json` in the state folder, beside `cache-sizes.json`.
  Deleting it only means the next launch checks again.

## The About Row

The project picker has an `📦 About` row under Configuration and Cache and scratch. It works whether
or not you opted in to the automatic check.

- **The preview pane** shows the version you are running, how AI Launcher was installed (pipx,
  `pip --user`, a virtual environment, or an editable or source checkout), and the update status:
  the newest release the automatic check has seen and when, `not checked yet`, or `off` with the
  setting to add. It reads saved data only and makes no network call.
- **Enter on the row** runs `ai-launcher update` in place: it asks PyPI, shows the command, asks
  `Update now? [y/N]`, and runs it. This is the only moment the row contacts PyPI. When it finishes,
  press Enter to go back to the picker. The new version is used the next time you start AI Launcher.
- **A 🆕 after the row's name** means the saved check found a newer release, so you can see it
  without opening the row.

It is the same flow, with the same install detection, as the command: an editable install is told to
`git pull`, and on Windows, started from `ai-launcher.exe`, the command is shown, not run.

## Windows

Windows will not replace an `.exe` that is running. When you start `ai-launcher.exe` itself, the
upgrade could fail halfway, so AI Launcher prints the command and leaves it to you. The command uses
the full path of the Python that runs the launcher, so it works even without the `py` launcher:

```powershell
& 'C:\Path\To\python.exe' -m pip install --user --upgrade ai-launcher
```

Run it from a normal PowerShell prompt, not from inside the launcher. Running
`python -m ai_launcher update` also works, since that is `python.exe`, not the `.exe` being
replaced.

## Versions Before This Feature

`update` exists only in versions that include it. If `ai-launcher --version` shows an older release,
run the install command above once by hand; after that, `update` handles it.

## Exit Codes

| Code | Meaning                                                   |
| ---- | --------------------------------------------------------- |
| 0    | Up to date, or the update ran, or `--check`               |
| 1    | The upgrade command failed, or no terminal and no `--yes` |
| 2    | Could not reach PyPI or read its reply                    |

The automatic check has no exit code of its own: it never changes how a launch ends.
