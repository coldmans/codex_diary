<p align="center">
  <img alt="Codex Diary Korean diary example" src="docs/assets/app-example-ko.png" width="49%">
  <img alt="Codex Diary English diary example" src="docs/assets/app-example-en.png" width="49%">
</p>

[한국어](README.md) | [English](README.en.md)

# codex-diary

Turn Chronicle Markdown summaries into a daily work report and a diary-style reflection.

**Model note: `gpt-5.5` is currently not supported through the local Codex CLI flow used by this app. Use `gpt-5.4` or another available model for now.**

## Requirements

- macOS
- Homebrew
- Local `codex` CLI installed and logged in with `codex login`
- Chronicle enabled in Codex settings
- Chronicle Markdown summaries under `~/.codex/memories_extensions/chronicle/resources`

Codex Diary reads Chronicle summary Markdown only. It does not process raw screen recordings, screenshots, OCR JSONL, or images directly.

## Enable Chronicle

Before creating diaries, turn on `Chronicle research preview` in Codex settings.

![Codex settings showing Chronicle research preview enabled](docs/assets/chronicle-settings-en.png)

## Install

```bash
brew tap coldmans/codex-diary https://github.com/coldmans/codex_diary
brew install --cask codex-diary
```

Then open `Codex Diary.app`, connect Codex if needed, choose a date, and create the entry.

## What It Creates

- One Markdown entry per day
- A work-report view and a diary-style view
- Timeline notes from Chronicle summaries
- Tomorrow tasks and a short reflection
- Multilingual output from the app settings

Chronicle `10min` summaries are used first. `6h` summaries are only secondary context. The default day boundary is local time `04:00`, so activity from `00:00` to `03:59` belongs to the previous day.

## CLI

```bash
codex-diary --date 2026-04-21
codex-diary --date 2026-04-21 --output-language ko
codex-diary --date 2026-04-21 --length very-long
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

## Development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
python3 -m codex_diary.app
```

Run checks:

```bash
python3 -m unittest discover -s tests -v
node --check codex_diary/ui/app.js
python3 -m compileall codex_diary
```
