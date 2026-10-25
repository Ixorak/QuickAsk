# QuickAsk

A small Windows tool: **highlight any text**, press **Ctrl+Shift+Q**, and Claude's answer lands **straight in your clipboard**. Then just paste it with Ctrl+V.

It runs in the background, with only an icon in the notification area (the hidden icons next to the clock).

## How it works

1. The hotkey is registered with Windows (`RegisterHotKey`).
2. When you press it, QuickAsk copies the highlighted text.
3. It sends that text to [Claude Code](https://claude.com/claude-code) in non-interactive mode (`claude -p`).
4. The answer replaces the clipboard content.

The icon changes color to show what's happening:

| Color | State |
|---|---|
| 🔵 Blue | Ready |
| 🟠 Orange | Working |
| 🟢 Green | Answer copied |
| 🔴 Red | Error (details in `quickask.log`) |

## Requirements

- Windows 10 or 11
- [Python 3](https://www.python.org/downloads/) (check "Add to PATH" during install)
- [Claude Code](https://claude.com/claude-code) installed and signed in to your own account

QuickAsk uses the Claude Code installed on your PC, so requests go through your own Claude account.

## Installation

1. Download or clone the repository.
2. Double-click `build.bat`. It installs the dependencies and builds the app.
3. Run `dist\QuickAsk.exe`.

It's a single portable .exe with no installer, so you can move it anywhere.

To start it with Windows: press Win+R, type `shell:startup`, and put a shortcut to `QuickAsk.exe` in that folder.

## Configuration

On first launch, a `config.json` file is created next to the exe:

```json
{
  "hotkey": "ctrl+shift+q",
  "instruction": "Answer in English in one sentence of 15 words max, no explanation, no introduction, no Markdown",
  "timeout": 120,
  "claude_path": ""
}
```

| Key | Purpose |
|---|---|
| `hotkey` | Keyboard shortcut. Modifiers: `ctrl`, `shift`, `alt`, `win`. Keys: A-Z, 0-9, F1-F24 |
| `instruction` | Prompt sent to Claude along with the highlighted text. By default: a one-sentence answer (15 words max) in English |
| `timeout` | Maximum wait time, in seconds |
| `claude_path` | Full path to `claude.exe`, if QuickAsk can't find it on its own |

After editing it, quit QuickAsk (right-click the icon, then Quit) and start it again.

### Changing the answer language

Answers are in English by default. To get them in another language, open `config.json` and replace `in English` in `instruction` with the language you want:

```json
"instruction": "Answer in French in one sentence of 15 words max, no explanation, no introduction, no Markdown",
```

Any language works (`in Spanish`, `in German`, `in Italian`...). You can also write the whole instruction directly in your language, for example in French:

```json
"instruction": "Reponds en francais en une seule phrase de 15 mots maximum, sans explication, sans introduction, sans Markdown",
```

To get longer or shorter answers, change the number of words the same way.

> In `instruction`, avoid apostrophes, quotes and the characters `& | ^ % !`.

## Troubleshooting

- **The icon doesn't change when I press the hotkey**: another app may already use that shortcut. Check `quickask.log` and pick a different one in `config.json`. Also avoid `ctrl+alt+…` on Swiss, French and other European keyboards, where Ctrl+Alt acts as AltGr.
- **Nothing happens in an app running as administrator**: that's a Windows limitation. Run QuickAsk as administrator too.
- **My antivirus blocks the exe**: this is a common false positive with PyInstaller-built executables. You can also run `python quickask.py` directly.

## License

MIT. See [LICENSE](LICENSE).
