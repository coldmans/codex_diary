# UI Assets

Drop mascot images into this folder to replace the inline SVG placeholders
used by the desktop app.  All four files are optional — if a file is missing,
the app falls back to a CSS/SVG cloud shape.

| Filename | Where it appears |
|---|---|
| `mascot-empty.png` | Empty-state center illustration (reading with book) |
| `mascot-diary.png` | Diary view right-side illustration (desk scene) |
| `mascot-calendar.png` | Calendar view illustration |
| `app-icon.png` | Source PNG for the macOS app icon; also used in the sidebar brand and diary heading |

Transparent PNG is preferred.  SVG also works — rename the file to `.svg` and
update the `<img>` src in `ui/index.html` if you want to keep it as SVG.
