# Codex Diary Launch Kit

This is the copy bank for sharing Codex Diary without sounding like a generic AI productivity launch. Keep the angle personal, local-first, and useful to people who live inside Codex all day.

## Positioning

Primary route: private work memory for Codex-heavy developers.

One-liner:

> Codex Diary turns local Chronicle summaries into a private Markdown work diary, so yesterday's coding session does not disappear into vague memory.

Short pitch:

> If you use Codex heavily, the workday can become a blur: repo switches, fixes, builds, screenshots, and "wait, what did I actually do today?" Codex Diary reads Chronicle Markdown summaries, masks obvious sensitive patterns, and generates a local daily report plus diary-style reflection.

What to emphasize:

- Local macOS desktop app, not a hosted analytics product.
- Reads Chronicle Markdown summaries only, not raw screen recordings.
- Outputs plain Markdown files.
- Handles day boundaries, duplicate event pruning, sensitive-pattern masking, Korean/English UI, and weekly review.
- Useful for developers, students, indie builders, and anyone doing long Codex work sessions.

What to avoid:

- Do not claim perfect privacy. Say local-first and explain the Codex CLI generation step.
- Do not imply it reads all screen recordings. It intentionally reads Chronicle Markdown summaries only.
- Do not call it a team surveillance tool. It is a personal work diary.

## GitHub

Repo description:

> Local macOS app that turns Codex Chronicle summaries into private Markdown work diaries and reports

Suggested topics:

`codex`, `chronicle`, `macos`, `pywebview`, `markdown`, `local-first`, `developer-tools`, `productivity`, `ai`, `work-journal`

## Hacker News

HN's Show HN guidelines say the project should be something people can try, and the post should make clear what it does. See [Show HN Guidelines](https://news.ycombinator.com/showhn.html).

Title:

> Show HN: Codex Diary - local work diaries from Codex Chronicle summaries

First comment:

> I built this because my Codex sessions were getting long enough that I could not reliably answer a simple question at night: "what did I actually do today?"
>
> Codex Diary is a small macOS app that reads Codex Chronicle Markdown summaries, groups them by a local day boundary, masks obvious sensitive patterns, and generates a Markdown work report plus a diary-style reflection through the local Codex CLI.
>
> The important boundary: it does not parse raw screen recordings, screenshots, OCR JSONL, or images. It reads Chronicle's Markdown memory summaries and stores the generated diary locally as plain Markdown.
>
> It is rough, but already useful for daily work logs, personal retros, and explaining a messy day of agent-assisted coding to future me.
>
> Repo/release: https://github.com/coldmans/codex_diary

Follow-up reply if someone asks about privacy:

> The app is local-first, but generation still goes through the local `codex` CLI, so it is not "offline-only." The data boundary I cared about was narrower: do not process raw recordings or screenshots, only Chronicle Markdown summaries after masking obvious sensitive patterns.

## Product Hunt

Product Hunt's launch docs say makers can submit their own product and schedule a launch up to one month ahead. See [Preparing for Launch](https://www.producthunt.com/launch/preparing-for-launch).

Product name:

> Codex Diary

Tagline:

> Private Markdown work diaries from Codex Chronicle summaries

Description:

> Codex Diary is a local macOS app for people who use Codex all day. It turns Chronicle Markdown summaries into daily work reports and diary-style reflections, with sensitive-pattern masking, local Markdown output, multilingual UI, and weekly review.

Maker comment:

> I made Codex Diary after realizing that long agent-assisted coding days were hard to reconstruct from memory. The app reads Chronicle Markdown summaries, not raw recordings, then creates a daily Markdown report and a more human diary-style reflection. It is intentionally small and local-first: useful for personal work logs, learning journals, and "what did I actually ship this week?" reviews.

Gallery captions:

- Turn Chronicle summaries into a daily diary.
- Switch between report, diary, and raw Markdown views.
- Review saved entries by calendar or week.
- Keep generated output as plain Markdown on your Mac.

## X / Twitter

Short post:

> I built Codex Diary: a local macOS app that turns Codex Chronicle summaries into private Markdown work diaries.
>
> For those "what did I actually do yesterday?" Codex-heavy days.
>
> GitHub: https://github.com/coldmans/codex_diary

Thread:

> 1/ I built a tiny app for a problem I kept having: after a long Codex session, I could not remember the actual shape of the day.
>
> 2/ Codex Diary reads Chronicle Markdown summaries and turns them into a daily work report plus a diary-style reflection.
>
> 3/ It does not process raw recordings, screenshots, OCR JSONL, or images. It only uses Chronicle's Markdown summaries.
>
> 4/ Output is plain Markdown on your Mac. The app adds day-boundary grouping, duplicate-event pruning, sensitive-pattern masking, multilingual UI, and weekly review.
>
> 5/ If you live in agent-assisted coding loops and want a better memory trail: https://github.com/coldmans/codex_diary

## LinkedIn

> I built Codex Diary, a local macOS app that turns Codex Chronicle summaries into daily work reports and diary-style reflections.
>
> The motivation was simple: after long agent-assisted coding sessions, it is surprisingly hard to reconstruct what happened across repos, fixes, builds, and follow-up decisions.
>
> Codex Diary reads Chronicle Markdown summaries, groups them by local workday, masks obvious sensitive patterns, and stores generated entries as plain Markdown. It intentionally does not process raw recordings, screenshots, OCR JSONL, or images.
>
> It is a small tool, but it has been useful for personal retrospectives, weekly summaries, and keeping a human-readable record of Codex-heavy development work.
>
> GitHub: https://github.com/coldmans/codex_diary

## Korean Dev Communities

Korean short post:

> Codex를 오래 쓰다 보면 하루가 끝났을 때 "오늘 정확히 뭐 했더라?"가 꽤 자주 생겨서, Chronicle Markdown 요약을 개인 작업 일기로 바꾸는 macOS 앱을 만들었습니다.
>
> Codex Diary는 원본 화면 녹화나 스크린샷을 직접 읽지 않고, Chronicle이 만든 Markdown 요약만 읽어서 하루 작업 보고서와 일기형 회고를 생성합니다. 결과는 로컬 Markdown 파일로 저장됩니다.
>
> GitHub: https://github.com/coldmans/codex_diary

Korean technical angle:

> 구현하면서 신경 쓴 점은 "일기 생성"보다 데이터 경계였습니다. 원본 화면 녹화/OCR/이미지를 직접 처리하지 않고 Chronicle Markdown summary만 입력으로 삼고, day boundary, 이벤트 추출/중복 제거, 민감정보 패턴 마스킹, pywebview 설정 저장을 붙였습니다.

## Reddit

Reddit's self-promotion wiki warns that self-promotion is generally frowned upon and recommends understanding each community's norms first. See [Reddit self-promotion guidance](https://www.reddit.com/r/reddit.com/wiki/selfpromotion/). Use this only in communities where personal projects are welcome, and lead with the problem rather than dropping a bare link.

Value-first post:

> I made a small local macOS app for turning Codex Chronicle summaries into Markdown work diaries.
>
> The personal pain: after long agent-assisted coding sessions, I often remembered the vibe of the day but not the actual sequence of decisions, fixes, builds, and blockers.
>
> The app reads Chronicle Markdown summaries, groups them by workday, masks obvious sensitive patterns, and generates a daily report plus a diary-style reflection through the local Codex CLI. It does not read raw recordings/screenshots/OCR files directly.
>
> I am mostly looking for feedback from people who use coding agents heavily: would this kind of local work-memory trail be useful to you, or is your existing notes/commit flow enough?
>
> GitHub: https://github.com/coldmans/codex_diary

## 7-Day Launch Sequence

Day 0:

- Make sure GitHub description/topics are filled.
- Confirm the latest release asset installs.
- Pin one strong screenshot at the top of README.
- Prepare one 30-60 second demo clip if possible.

Day 1:

- Post Show HN.
- Stay online for the first two hours and answer comments plainly.
- Do not over-defend rough edges; turn good criticism into issues.

Day 2:

- Post the X thread and Korean dev-community version.
- Reply with one short demo GIF or screenshot.

Day 3:

- Share one implementation note: "why Codex Diary reads Markdown summaries instead of raw recordings."

Day 4:

- Post a small changelog from feedback.
- Add GitHub issues for top requested features.

Day 5:

- Submit/schedule Product Hunt if the release asset and screenshots feel clean enough.

Day 6:

- Share the weekly-review angle: "what did I ship this week?"

Day 7:

- Publish a short retrospective: what worked, what people asked for, and what changed.

## First Issues To Invite

- Better import diagnostics when Chronicle summaries exist but a selected date is empty.
- Export to Obsidian-friendly folder structure.
- Optional local-only summarization backend.
- Better first-run checklist.
- Demo mode with sample Chronicle summaries.

## Reply Bank

What is Chronicle?

> Chronicle is Codex's screen-recording/memory feature. Codex Diary does not read the raw recording stream; it reads the Markdown summaries Chronicle writes under the user's Codex memory folder.

Does this upload my screen?

> The app itself does not upload raw screen data or images. Generation uses the local `codex` CLI, so the relevant privacy boundary is the Codex CLI/model path plus the app's masking step.

Why not just use commits?

> Commits are great for code history, but they do not capture investigation, rejected approaches, UI review notes, build failures, app-store/upload troubleshooting, or the human story of the day.

Is it only Korean?

> No. The app supports multiple output languages and the UI can run in Korean or English among others.
