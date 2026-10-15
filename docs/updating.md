# Updating

`ai-launcher update` upgrades AI Launcher to the latest release on PyPI. It runs only when you run
it: AI Launcher never checks for a new version on its own, at launch or in the background.

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
