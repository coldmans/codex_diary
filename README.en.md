<p align="center">
  <img alt="Codex Diary Korean diary example" src="docs/assets/app-example-ko.png" width="49%">
  <img alt="Codex Diary English diary example" src="docs/assets/app-example-en.png" width="49%">
</p>

[한국어](README.md) | [English](README.en.md)

# codex-diary

Turn Chronicle Markdown summaries into a daily work report and a diary-style reflection.

**Model note: `gpt-5.5` requires a recent Codex CLI. If it fails on an older version, run `brew upgrade --cask codex`, then reopen the app.**

## Requirements

- macOS on Apple Silicon
- Homebrew
- Local `codex` CLI installed and logged in with `codex login`
- Latest Codex CLI recommended when using `gpt-5.5`
- Chronicle enabled in Codex settings
- Chronicle Markdown summaries under `~/.codex/memories_extensions/chronicle/resources`

Codex Diary reads Chronicle summary Markdown only. It does not process raw screen recordings, screenshots, OCR JSONL, or images directly.

## Enable Chronicle

Before creating diaries, turn on `Chronicle research preview` in Codex settings.

![Codex settings showing Chronicle research preview enabled](docs/assets/chronicle-settings-en.png)

## Install

First install:

```bash
brew tap coldmans/codex-diary https://github.com/coldmans/codex_diary
brew install --cask codex-diary
```

Then open `Codex Diary.app`, connect Codex if needed, choose a date, and create the entry.

Update:

```bash
brew update
brew upgrade --cask codex-diary
```

If you installed it before and want to test from a clean install:

```bash
brew uninstall --cask codex-diary --force
brew untap coldmans/codex-diary
brew tap coldmans/codex-diary https://github.com/coldmans/codex_diary
brew install --cask codex-diary
```

If macOS still blocks first launch, run this once and open the app again:

```bash
xattr -dr com.apple.quarantine "/Applications/Codex Diary.app"
```

## Privacy And Data Flow

- The app reads Chronicle Markdown summaries only. It does not process raw recordings, screenshots, OCR JSONL, or images directly.
- During generation, extracted content for the selected date is masked for obvious sensitive patterns, then sent to the local `codex` CLI for model execution.
- Generated diaries plus app memos/tasks are stored as plaintext on your Mac. The default app output location is `~/Library/Application Support/Codex Diary/diary`.
- Review public screenshots or shared diary files before publishing them.

## What It Creates

- One Markdown entry per day
- A work-report view and a diary-style view
- Timeline notes from Chronicle summaries
- Tomorrow tasks and a short reflection
- Multilingual output from the app settings

Chronicle `10min` summaries are used first. `6h` summaries are only secondary context. The default day boundary is local time `04:00`, so activity from `00:00` to `03:59` belongs to the previous day.

## CLI

The Homebrew Cask installs the desktop app only. The CLI is for users who clone the repository or install the Python package directly.

```bash
codex-diary --date 2026-04-21
codex-diary --date 2026-04-21 --output-language ko
codex-diary --date 2026-04-21 --length very-long
codex-diary --date 2026-04-21 --codex-model gpt-5.5
codex-diary --source-dir ~/.codex/memories_extensions/chronicle/resources
codex-diary --out-dir ./custom-output --day-boundary-hour 4
```

Useful options:

- `--date YYYY-MM-DD`
- `--source-dir <path>`
- `--out-dir <path>`
- `--dry-run`
- `--day-boundary-hour <0-23>`
- `--language <code>` or `--output-language <code>`
- `--length short|medium|long|very-long`
- `--codex-model <model>`

## Development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
python3 -m codex_diary.app
```

## Checks

```bash
python3 -m unittest discover -s tests -v
node --check codex_diary/ui/app.js
python3 -m compileall codex_diary
```
