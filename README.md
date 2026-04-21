# codex-diary

Chronicle이 이미 생성한 Markdown 메모리 요약을 읽어서, 한국어 기준의 "금일 작업 보고서 + 일기 버전"을 함께 만드는 로컬 도구입니다. 원본 화면 녹화, JPG, OCR JSONL은 직접 읽지 않고 `~/.codex/memories_extensions/chronicle/resources/*.md` 같은 Chronicle 요약 Markdown만 입력으로 사용합니다.

기본 엔진은 CLI로도 쓸 수 있고, 지금은 같은 코어를 재사용하는 Tkinter 기반 데스크톱 앱도 함께 제공합니다.

하루 경계는 로컬 타임존 기준 오전 4시가 기본값입니다. 그래서 `00:00~03:59`의 활동은 전날 일기에 포함되도록 처리합니다. Chronicle 파일명은 현재 포맷 기준 UTC 타임스탬프로 해석한 뒤, 로컬 타임존으로 변환해서 날짜를 묶습니다.

## 주요 기능

- `10min` 요약을 기본 입력으로 사용
- `6h` 요약은 `10min` 정보가 부족할 때만 보조/fallback으로 사용
- `draft-update`와 `finalize` 모드 지원
- 핵심 요약뿐 아니라 사소한 앱 전환/문서 열람/확인 흐름도 시간순 메모로 함께 기록
- 같은 결과물 안에 `금일 작업 보고서`와 `오늘의 일기 버전`을 함께 생성
- 데스크톱 앱에서 날짜 선택, 생성, 미리보기, 복사, 파일 열기 지원
- 데스크톱 앱에서 생성 결과를 외부 IDE가 아니라 앱 안에서 바로 읽기 지원
- 선택 날짜의 저장된 일기 다시 보기와 주간 묶음 보기 지원
- 이메일, 전화번호, 토큰, 긴 인증값 같은 민감정보 마스킹
- LLM API 키가 없어도 규칙 기반 fallback으로 Markdown 생성
- 나중에 cron, launchd, Codex automation으로 연결하기 쉽도록 함수 분리

## 설치와 실행

별도 의존성 없이 Python 3.9+ 기준으로 동작합니다.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

또는 설치 없이도 바로 실행할 수 있습니다.

```bash
python3 -m codex_diary.cli finalize --date 2026-04-21 --dry-run
```

데스크톱 앱을 실행하려면:

```bash
python3 -m codex_diary.app
```

설치 후에는 아래처럼 쓸 수 있습니다.

```bash
codex-diary-app
```

앱에서는 날짜, 입력 폴더, 출력 폴더, 하루 경계 시각, 생성 모드를 고른 뒤 결과를 `전체 Markdown / 금일 작업 보고서 / 오늘의 일기` 탭으로 미리 볼 수 있습니다.

배포된 macOS 앱의 기본 출력 경로는 저장 가능한 위치인 `~/Library/Application Support/Codex Diary/output/diary`입니다. 필요하면 앱 안에서 다른 폴더로 바꿀 수 있습니다.

## macOS DMG 빌드

macOS에서 배포용 `.app` / `.dmg`를 만들려면 PyInstaller 빌드 도구만 추가로 설치하면 됩니다.

```bash
pip install -e ".[macos-build]"
codex-diary-package-macos
```

설치 없이 바로 실행하고 싶다면 아래처럼도 가능합니다.

```bash
python3 -m codex_diary.package_macos
```

기본 산출물:

- 앱 번들: `dist/Codex Diary.app`
- DMG: `dist/Codex-Diary-0.1.0-macOS.dmg`

추가 옵션:

- `--skip-dmg`: `.app`만 만들고 DMG는 건너뜀
- `--dist-dir <path>`: 최종 산출물 위치 변경
- `--build-dir <path>`: PyInstaller 작업 파일 위치 변경

참고:

- 현재 빌드는 코드 서명이나 notarization이 없는 로컬 배포용입니다.
- GitHub Releases 같은 곳에 `dist/Codex-Diary-0.1.0-macOS.dmg`를 올리면 사용자가 내려받아 설치할 수 있습니다.
- 다만 브라우저로 내려받은 DMG/App은 macOS Gatekeeper가 막을 수 있습니다. 이 경우 첫 실행은 Finder에서 우클릭 `열기`를 쓰거나, 로컬 테스트 용도라면 `xattr -dr com.apple.quarantine "/Applications/Codex Diary.app"` 같은 방식으로 quarantine 속성을 제거해야 할 수 있습니다.

## CLI 사용법

기본 출력 경로:

- 초안 갱신: `output/diary/drafts/YYYY-MM-DD.md`
- 최종 일기: `output/diary/YYYY-MM-DD.md`

예시:

```bash
codex-diary draft-update --date 2026-04-21
codex-diary finalize --date 2026-04-21
codex-diary finalize --date 2026-04-21 --dry-run
codex-diary finalize --source-dir ~/.codex/memories_extensions/chronicle/resources
codex-diary finalize --out-dir ./custom-output --day-boundary-hour 4
```

지원 옵션:

- `draft-update` / `finalize`: 생성 모드. 기본값은 `finalize`
- `--date YYYY-MM-DD`: 특정 날짜 기준으로 생성
- `--source-dir <path>`: Chronicle 요약 폴더 override
- `--out-dir <path>`: 결과 저장 폴더
- `--dry-run`: 파일 저장 없이 stdout 출력
- `--day-boundary-hour 4`: 하루 경계 시각 지정

## 데스크톱 앱 사용법

- 실행: `python3 -m codex_diary.app` 또는 `codex-diary-app`
- 입력: 날짜, Chronicle 요약 폴더, 출력 폴더, 하루 경계 시각
- 모드: `최종 일기` / `초안 갱신`
- 결과: `전체 Markdown`, `금일 작업 보고서`, `오늘의 일기` 보기 전환
- 편의 기능: 생성 후 자동 저장, 현재 보기 복사, 앱 안에서 결과 보기, 외부 앱 열기, 선택 날짜 보기, 해당 주 보기

## 환경변수

LLM은 선택 사항입니다. API 키가 없으면 규칙 기반 fallback으로 자동 동작합니다.

- `OPENAI_API_KEY`: 있으면 OpenAI Responses API를 사용
- `OPENAI_MODEL`: 기본값 `gpt-4.1-mini`
- `OPENAI_BASE_URL`: 기본값 `https://api.openai.com/v1`
- `DIARY_LLM_PROVIDER`: 현재는 `openai`만 지원

## 테스트

```bash
python3 -m unittest discover -s tests -v
```

## 생성 결과 형식

도구는 한 문서 안에 아래 두 가지 결과를 함께 만듭니다.

- `금일 작업 보고서`
- `오늘의 일기 버전`

보고서 쪽에는 아래 항목이 들어갑니다.

- 오늘 한 일
- 사소한 흐름까지 포함한 시간순 메모
- 중요하게 확인하거나 결정한 것
- 막혔던 점 또는 미해결 이슈
- 내일 할 일
- 짧은 회고

일기 버전은 같은 사실을 조금 더 부드럽고 살짝 귀엽게 풀어 쓰되, 화면에 실제로 드러난 맥락을 넘어서 감정이나 오프라인 활동을 과장하지 않도록 설계했습니다.

## 한계점

- Chronicle 요약 자체가 이미 2차 요약물이므로, 원문보다 세부 맥락이 줄어든 상태에서 일기를 만듭니다.
- LLM 없이 동작하는 fallback은 사실을 보수적으로 유지하는 대신 문체가 다소 단정적으로 느껴질 수 있습니다.
- 현재는 Chronicle 파일명을 UTC 기준으로 가정합니다. 이 포맷이 달라지면 파일명 파서를 함께 조정해야 합니다.
- 민감정보 마스킹은 일반적인 패턴 중심이라 모든 비밀값을 완벽히 식별하지는 못할 수 있습니다.
- macOS DMG는 현재 unsigned 상태라, 외부 배포 시에는 코드 서명과 notarization을 추가하는 편이 좋습니다.
