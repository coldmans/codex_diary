<p align="center">
  <img alt="Codex Diary 한국어 일기 예시" src="docs/assets/app-example-ko.png" width="49%">
  <img alt="Codex Diary 영어 일기 예시" src="docs/assets/app-example-en.png" width="49%">
</p>

[한국어](README.md) | [English](README.en.md)

# codex-diary

Chronicle Markdown 요약을 하루 작업 보고서와 일기형 회고로 바꿔 주는 로컬 앱입니다.

**모델 안내: `gpt-5.5`를 사용하려면 최신 Codex CLI가 필요합니다. 구버전에서 실패하면 `brew upgrade --cask codex`로 Codex를 업데이트한 뒤 앱을 다시 열어 주세요.**

## 요구 사항

- macOS
- Homebrew
- 로컬 `codex` CLI 설치 및 `codex login` 완료
- `gpt-5.5` 사용 시 Codex CLI 최신 버전 권장
- Codex 설정에서 Chronicle 활성화
- `~/.codex/memories_extensions/chronicle/resources` 아래 Chronicle Markdown 요약 존재

Codex Diary는 Chronicle 요약 Markdown만 읽습니다. 원본 화면 녹화, 스크린샷, OCR JSONL, 이미지는 직접 처리하지 않습니다.

## Chronicle 켜기

일기를 만들기 전에 Codex 설정에서 `Chronicle 리서치 미리보기`를 켜 주세요.

![Codex 설정에서 Chronicle 리서치 미리보기를 켠 화면](docs/assets/chronicle-settings-ko.png)

## 설치

처음 설치:

```bash
brew tap coldmans/codex-diary https://github.com/coldmans/codex_diary
brew install --cask codex-diary
```

설치 후 `Codex Diary.app`을 열고, 필요하면 Codex를 연결한 뒤 날짜를 선택해서 일기를 생성하면 됩니다.

이미 설치한 적이 있고 처음부터 다시 확인하고 싶다면:

```bash
brew uninstall --cask codex-diary --force
brew untap coldmans/codex-diary
brew tap coldmans/codex-diary https://github.com/coldmans/codex_diary
brew install --cask codex-diary
```

설치 후 macOS가 앱을 막으면 아래 명령을 한 번 실행한 뒤 다시 열어 주세요.

```bash
xattr -dr com.apple.quarantine "/Applications/Codex Diary.app"
```

## 생성 결과

- 날짜별 Markdown 일기 파일
- 작업 보고서 보기와 일기형 보기
- Chronicle 요약 기반 시간순 메모
- 내일 할 일과 짧은 회고
- 앱 설정에 따른 다국어 출력

Chronicle `10min` 요약을 우선 사용하고, `6h` 요약은 보조 컨텍스트로만 사용합니다. 하루 경계는 기본적으로 로컬 시간 `04:00`이며, `00:00`부터 `03:59`까지의 활동은 전날 일기에 포함됩니다.

## CLI

```bash
codex-diary --date 2026-04-21
codex-diary --date 2026-04-21 --output-language ko
codex-diary --date 2026-04-21 --length very-long
codex-diary --source-dir ~/.codex/memories_extensions/chronicle/resources
codex-diary --out-dir ./custom-output --day-boundary-hour 4
```

주요 옵션:

- `--date YYYY-MM-DD`
- `--source-dir <path>`
- `--out-dir <path>`
- `--dry-run`
- `--day-boundary-hour <0-23>`
- `--language <code>` 또는 `--output-language <code>`
- `--length short|medium|long|very-long`

## 개발

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
python3 -m codex_diary.app
```

## 공증된 배포 빌드

Apple Developer Program 가입 후 `Developer ID Application` 인증서가 키체인에 있어야 합니다.

```bash
security find-identity -v -p codesigning
```

notarytool 인증 정보는 한 번만 저장하면 됩니다.

```bash
xcrun notarytool store-credentials codex-diary-notary \
  --apple-id "you@example.com" \
  --team-id "TEAMID" \
  --password "app-specific-password"
```

서명, 공증, stapling, Homebrew Cask 체크섬 갱신을 한 번에 실행:

```bash
python3 -m codex_diary.package_macos \
  --sign-identity "Developer ID Application: Your Name (TEAMID)" \
  --notarize \
  --notary-keychain-profile codex-diary-notary \
  --write-homebrew-cask
```

검증:

```bash
python3 -m unittest discover -s tests -v
node --check codex_diary/ui/app.js
python3 -m compileall codex_diary
```
