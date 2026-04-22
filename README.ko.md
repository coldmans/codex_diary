[English](README.md) | [한국어](README.ko.md) | [日本語](README.ja.md) | [中文](README.zh.md)

# codex-diary

Chronicle Markdown 요약을 읽어서 날짜별 작업 보고서 + 일기 초안을 생성하는 로컬 도구입니다.

`codex-diary`는 `~/.codex/memories_extensions/chronicle/resources/*.md` 같은 Chronicle 요약 파일을 읽어서, 날짜 기준 Markdown 일기를 만들어 줍니다. 원본 화면 녹화, JPG 스크린샷, OCR JSONL을 직접 처리하지 않고, Chronicle이 이미 만들어 둔 요약 Markdown을 입력으로 사용하는 것이 핵심입니다.

현재 생성은 로컬 `codex` CLI 로그인 세션에 의존합니다. Codex가 설치되지 않았거나 로그인되지 않았다면 다른 모델로 조용히 대체하지 않고 연결 안내 메시지와 함께 종료합니다.

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
- `draft-update`, `finalize` 두 가지 모드 지원
- Chronicle 요약 Markdown만 입력으로 사용
- 생성 전 민감정보 마스킹 지원
- `pywebview` 기반 데스크톱 앱과 CLI 함께 제공
- 다국어 diary 출력 지원
- `short`, `medium`, `long`, `very-long` 네 가지 일기 길이 프리셋 지원
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

앱 내부에서는 `codex login status`로 로그인 상태를 확인합니다. macOS 데스크톱 앱에서는 필요 시 Terminal에서 `codex login --device-auth`를 열 수 있습니다.

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
codex-diary finalize --date 2026-04-21
codex-diary draft-update --date 2026-04-21
codex-diary finalize --date 2026-04-21 --dry-run
codex-diary finalize --date 2026-04-21 --output-language ko
codex-diary finalize --date 2026-04-21 --length very-long
codex-diary finalize --source-dir ~/.codex/memories_extensions/chronicle/resources
codex-diary finalize --out-dir ./custom-output --day-boundary-hour 4
```

주요 옵션:

- `draft-update` / `finalize`: 누적 초안 또는 최종 일기 생성
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
- `draft-update` / `finalize` 모드 전환
- 생성 도중 취소
- 앱 안에서 보고서 / 일기 / 원본 Markdown 보기
- 최근 날짜 및 주간 보관함 탐색
- 현재 보기 복사
- 외부 앱으로 열기

또한 Codex 연결 상태를 표시하고, 로그인 전에는 생성 버튼이 비활성화됩니다.

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
- 현재 소스 파서는 Chronicle 파일명이 예상된 UTC 타임스탬프 형식을 따른다고 가정합니다.
- 민감정보 마스킹은 패턴 기반이라 완전한 비밀정보 탐지로 보면 안 됩니다.
- macOS DMG 빌드는 현재 unsigned 로컬 배포 기준입니다.
