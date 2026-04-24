![Codex Diary 앱 데모](docs/assets/codex-diary-demo.svg)

[English](README.md) | [한국어](README.ko.md) | [日本語](README.ja.md) | [中文](README.zh.md)

# codex-diary

## 먼저 Chronicle 켜기

Codex Diary는 Chronicle Markdown 요약을 읽어서 일기를 만듭니다. 일기를 생성하기 전에 Codex 설정에서 `Chronicle 리서치 미리보기`를 켜 주세요.

![Codex 설정에서 Chronicle 리서치 미리보기를 켠 화면](docs/assets/chronicle-settings-ko.png)

## Homebrew로 설치

GitHub 사용자는 Homebrew 설치를 권장합니다.

```bash
brew tap coldmans/codex-diary https://github.com/coldmans/codex_diary
brew install --cask codex-diary
```

또는 DMG를 직접 받을 수 있습니다.

[최신 macOS DMG 다운로드](https://github.com/coldmans/codex_diary/releases/latest/download/Codex-Diary-0.1.0-macOS.dmg)

설치 후 `Codex Diary.app`을 열고, 필요하면 Codex를 연결한 뒤 Chronicle 요약 폴더를 선택해서 원하는 날짜의 일기를 생성하면 됩니다. 현재 앱은 unsigned macOS 빌드로 배포되므로, macOS에서 실행 확인을 요구하면 시스템 설정 또는 Finder 우클릭 메뉴에서 열기를 허용해야 할 수 있습니다.

macOS가 “Apple이 악성 소프트웨어가 있는지 확인할 수 없음”이라고 막으면, 앱을 Applications 폴더로 옮긴 뒤 Finder에서 `Codex Diary.app`을 Control-click 또는 우클릭하고 `열기`를 선택하세요. 고급 사용자는 아래 명령도 사용할 수 있습니다.

```bash
xattr -dr com.apple.quarantine "/Applications/Codex Diary.app"
```

## 무엇을 하는 도구인가

Chronicle Markdown 요약을 읽어서 날짜별 작업 보고서 + 일기 초안을 생성하는 로컬 도구입니다.

`codex-diary`는 `~/.codex/memories_extensions/chronicle/resources/*.md` 같은 Chronicle 요약 파일을 읽어서, 날짜 기준 Markdown 일기를 만들어 줍니다. 원본 화면 녹화, JPG 스크린샷, OCR JSONL을 직접 처리하지 않고, Chronicle이 이미 만들어 둔 요약 Markdown을 입력으로 사용하는 것이 핵심입니다.

현재 생성은 로컬 `codex` CLI 로그인 세션에 의존합니다. Codex가 설치되지 않았거나 로그인되지 않았다면 다른 모델로 조용히 대체하지 않고 연결 안내 메시지와 함께 종료합니다.

생성 중에는 선택 및 마스킹된 Chronicle 이벤트 일부가 로컬 `codex exec` 명령으로 전달되어 최종 일기/보고서 초안 작성에 사용됩니다. 이 호출은 `--ephemeral`로 실행되지만, Chronicle 요약 자체는 민감할 수 있는 입력으로 취급하는 것이 좋습니다.

영문 `README.md`를 기준 문서로 두고, 번역본은 프로젝트 변경 시 약간 늦게 갱신될 수 있습니다.

## 왜 이런 구조인가

Chronicle이 이미 활동 기록을 요약 Markdown으로 정리해 주기 때문에, 이 프로젝트는 raw capture를 다시 읽는 대신 그 요약을 재사용해서 더 가볍고 비교적 프라이버시 친화적인 diary 흐름을 유지합니다.

현재 diary 생성 규칙은 다음과 같습니다.

- Chronicle `10min` 요약을 1차 입력으로 사용
- `6h` 요약은 필요할 때만 보조 컨텍스트로 사용
- 로컬 타임존 기준 기본 `04:00`를 하루 경계로 사용
- 날짜당 결과 파일 하나만 유지하고 재생성 시 덮어쓰기

## 주요 기능

- 한 Markdown 파일 안에 `Work Report`와 `Diary Version`을 함께 생성
- Chronicle 요약 Markdown만 입력으로 사용
- 생성 전 민감정보 마스킹 지원
- `pywebview` 기반 데스크톱 앱과 CLI 함께 제공
- 다국어 diary 출력 지원
- `short`, `medium`, `long`, `very-long` 네 가지 일기 길이 프리셋 지원
- 생성에 사용할 Codex CLI 모델을 `gpt-5.4`, `gpt-5.5` 등으로 선택 가능
- 데스크톱 앱에서 생성 도중 취소 지원
- macOS `.dmg` 패키징 지원

## 다국어 README 방식

GitHub는 README 언어를 자동 전환해 주지 않아서, 보통 아래 방식으로 구성합니다.

- 기본 문서를 `README.md`로 유지
- `README.ko.md`, `README.ja.md` 같은 번역 파일 추가
- 각 README 상단에 언어 링크 배치

이 저장소는 지금 그 구조로 정리되어 있어서, 나중에 다른 언어를 추가하기도 쉽습니다.

## 요구 사항

- Python `3.9+`
- 로컬 `codex` CLI 설치
- `codex login`으로 유효한 Codex 로그인 세션 확보
- Chronicle이 켜져 있고 `~/.codex/memories_extensions/chronicle/resources` 아래에 Markdown 요약을 생성 중이어야 함

앱 내부에서는 `codex login status`로 로그인 상태를 확인합니다. macOS 데스크톱 앱에서는 필요 시 Terminal에서 `codex login --device-auth`를 열 수 있습니다.

Codex Diary는 원본 녹화, 스크린샷, OCR 파일을 직접 처리하지 않습니다. Chronicle 요약 폴더가 없거나 비어 있다면 먼저 Chronicle 요약을 만들거나, Settings에서 올바른 요약 폴더를 선택해 주세요.

## 설치

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

macOS 패키징까지 필요하면:

```bash
pip install -e ".[macos-build]"
```

## CLI 빠른 시작

기본 출력 경로:

- 개발 모드: `./output/diary/YYYY-MM-DD.md`
- macOS 번들 앱: `~/Library/Application Support/Codex Diary/output/diary/YYYY-MM-DD.md`

예시:

```bash
codex-diary --date 2026-04-21
codex-diary --date 2026-04-21 --dry-run
codex-diary --date 2026-04-21 --output-language ko
codex-diary --date 2026-04-21 --length very-long
codex-diary --source-dir ~/.codex/memories_extensions/chronicle/resources
codex-diary --out-dir ./custom-output --day-boundary-hour 4
```

주요 옵션:

- `--date YYYY-MM-DD`: 특정 날짜 기준 생성
- `--source-dir <path>`: Chronicle 요약 폴더 경로 override
- `--out-dir <path>`: 결과 저장 폴더 지정
- `--dry-run`: 파일 저장 없이 stdout 출력
- `--day-boundary-hour <0-23>`: 로컬 하루 경계 시각 지정, 기본값 `4`
- `--language <code>` 또는 `--output-language <code>`: 출력 언어 지정, 기본값 `en`
- `--length <code>` 또는 `--diary-length <code>`: 일기 길이 지정 (`short`, `medium`, `long`, `very-long`)

Codex가 연결되지 않은 경우 아래 메시지와 함께 종료합니다.

```text
먼저 codex를 연결해주세요.
```

## 데스크톱 앱

직접 실행:

```bash
python3 -m codex_diary.app
```

설치 후 엔트리포인트:

```bash
codex-diary-app
```

앱에서 가능한 작업:

- 기준 날짜 선택
- Chronicle 입력 폴더 / 출력 폴더 선택
- 출력 언어 선택
- 일기 길이 프리셋 선택
- 우측 상단 상태 pill에서 Codex 모델 선택
- 생성 도중 취소
- 앱 안에서 보고서 / 일기 / 원본 Markdown 보기
- 최근 날짜 및 주간 보관함 탐색
- 현재 보기 복사
- 외부 앱으로 열기

또한 우측 상단 상태 pill에 현재 선택된 Codex 모델을 표시합니다. 이 선택값은 `codex exec -m ...`에 그대로 전달되므로, 최신 모델이 아직 로컬 CLI에서 열리지 않았다면 다른 사용 가능한 모델을 고른 뒤 다시 생성하면 됩니다.

## macOS 패키징

앱 번들과 DMG 생성:

```bash
codex-diary-package-macos
```

또는:

```bash
python3 -m codex_diary.package_macos
```

기본 산출물:

- `dist/Codex Diary.app`
- `dist/Codex-Diary-0.1.0-macOS.dmg`

DMG를 새로 만든 뒤 Homebrew Cask 체크섬까지 갱신하려면:

```bash
python3 -m codex_diary.package_macos --write-homebrew-cask
```

이 명령은 생성된 DMG의 SHA256으로 `Casks/codex-diary.rb`를 갱신합니다. 사용자가 Homebrew로 설치하기 전에 같은 DMG가 GitHub release tag에 업로드되어 있어야 합니다.

## 지원하는 diary 출력 언어

생성 결과는 현재 아래 언어를 지원합니다.

- `en` English
- `ko` Korean
- `ja` Japanese
- `zh` Chinese
- `fr` French
- `de` German
- `es` Spanish
- `vi` Vietnamese
- `th` Thai
- `ru` Russian
- `hi` Hindi

이 목록은 README 번역 파일 수와는 별개입니다. 즉, 문서는 일부 언어만 번역되어 있어도 앱과 CLI는 더 많은 언어로 diary를 생성할 수 있습니다.

## 생성 결과 구조

생성되는 Markdown 파일에는 아래 두 블록이 함께 들어갑니다.

- `Work Report`
- `Diary Version`

보통 다음 정보가 포함됩니다.

- 오늘 한 일
- 사소한 흐름까지 포함한 시간순 메모
- 중요하게 확인하거나 결정한 것
- 막혔던 점 또는 미해결 이슈
- 내일 할 일
- 짧은 회고

`Diary Version`은 보고서보다 조금 더 자연스럽게 다듬지만, 화면에 드러나지 않은 감정이나 활동을 과장하지 않도록 설계되어 있습니다.

## 내부 로직 문서

- [이벤트 선정과 유사도 판단 쉽게 이해하기](docs/event-selection-similarity.ko.md): Chronicle 요약을 `Event`로 쪼개고, 중복을 제거하고, 프롬프트에 넣을 이벤트를 고르는 과정을 예시 중심으로 설명합니다.

## 환경변수

필수 환경변수는 없습니다.

- API 키를 요구하지 않습니다.
- 대신 로컬 Codex 로그인 세션을 사용합니다.

## 테스트

```bash
python3 -m unittest discover -s tests -v
node --check codex_diary/ui/app.js
python3 -m compileall codex_diary
```

## 한계

- Chronicle 요약 자체가 이미 2차 요약이기 때문에 일부 디테일 손실은 불가피합니다.
- 로컬 `codex` CLI 설치 및 로그인 없이는 생성할 수 없습니다.
- 선택된 Chronicle 이벤트 일부는 `codex exec`를 통해 전달되며, 민감정보 마스킹은 패턴 기반의 best-effort 보호입니다.
- 현재 소스 파서는 Chronicle 파일명이 예상된 UTC 타임스탬프 형식을 따른다고 가정합니다.
- macOS DMG 빌드는 현재 unsigned 로컬 배포 기준이라, macOS에서 미확인 개발자 경고가 뜰 수 있습니다.
