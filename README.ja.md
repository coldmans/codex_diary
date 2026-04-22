[English](README.md) | [한국어](README.ko.md) | [日本語](README.ja.md) | [中文](README.zh.md)

# codex-diary

Chronicle の Markdown 要約から、日付ごとの作業レポートと日記ドラフトを生成するローカルツールです。

`codex-diary` は `~/.codex/memories_extensions/chronicle/resources/*.md` のような Chronicle 要約ファイルを読み取り、日付単位の Markdown 日記を生成します。生の画面録画、JPG スクリーンショット、OCR JSONL を直接読むのではなく、Chronicle がすでに作成した要約 Markdown を入力として使う設計です。

現在の生成処理は、ローカルの `codex` CLI ログインセッションに依存しています。Codex が見つからない、または未ログインの場合は、別のプロバイダに自動で切り替えず、接続メッセージを出して終了します。

英語版 `README.md` を基準文書とし、翻訳版は更新が少し遅れる場合があります。

## このツールの考え方

Chronicle はすでに活動記録を要約 Markdown に圧縮しているため、このプロジェクトでは raw capture を再処理せず、その要約を再利用して軽量で比較的プライバシーに配慮した diary フローを保ちます。

現在の diary 生成ポリシー:

- Chronicle の `10min` 要約を主入力として使う
- `6h` 要約は必要な場合だけ補助コンテキストとして使う
- ローカルタイムゾーンを基準に、既定 `04:00` を日付境界に使う
- 1 日につき 1 つの出力ファイルを保持し、再生成時は上書きする

## 主な機能

- 1 つの Markdown ファイルに `Work Report` と `Diary Version` を同時に生成
- `draft-update` と `finalize` モードを提供
- Chronicle 要約 Markdown のみを入力として利用
- 生成前の簡易マスキングに対応
- `pywebview` ベースのデスクトップアプリと CLI を提供
- 多言語 diary 出力に対応
- macOS 向け `.dmg` パッケージングに対応

## 多言語 README の構成

GitHub には README の自動言語切り替え機能がないため、一般的には次の構成を取ります。

- 基本文書として `README.md` を置く
- `README.ko.md` や `README.ja.md` などの翻訳ファイルを追加する
- 各 README の先頭に言語リンクを置く

このリポジトリはその構成にしてあるため、今後ほかの言語を追加するのも簡単です。

## 要件

- Python `3.9+`
- ローカルに `codex` CLI がインストールされていること
- `codex login` による有効な Codex ログインセッション

アプリ内部では `codex login status` で接続状態を確認します。macOS デスクトップアプリでは必要に応じて Terminal で `codex login --device-auth` を開けます。

## インストール

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

macOS パッケージングも使いたい場合:

```bash
pip install -e ".[macos-build]"
```

## CLI クイックスタート

既定の出力先:

- 開発モード: `./output/diary/YYYY-MM-DD.md`
- macOS バンドルアプリ: `~/Library/Application Support/Codex Diary/output/diary/YYYY-MM-DD.md`

例:

```bash
codex-diary finalize --date 2026-04-21
codex-diary draft-update --date 2026-04-21
codex-diary finalize --date 2026-04-21 --dry-run
codex-diary finalize --date 2026-04-21 --output-language ja
codex-diary finalize --source-dir ~/.codex/memories_extensions/chronicle/resources
codex-diary finalize --out-dir ./custom-output --day-boundary-hour 4
```

主なオプション:

- `draft-update` / `finalize`: 下書き更新または最終 diary 生成
- `--date YYYY-MM-DD`: 特定日付を対象に生成
- `--source-dir <path>`: Chronicle 要約ディレクトリを上書き
- `--out-dir <path>`: 出力ディレクトリを指定
- `--dry-run`: ファイル保存せず stdout に出力
- `--day-boundary-hour <0-23>`: ローカル日付境界を指定。既定は `4`
- `--language <code>` または `--output-language <code>`: 出力言語を指定。既定は `en`

Codex が未接続の場合、次のメッセージで終了します。

```text
먼저 codex를 연결해주세요.
```

## デスクトップアプリ

直接起動:

```bash
python3 -m codex_diary.app
```

インストール後のエントリポイント:

```bash
codex-diary-app
```

アプリでできること:

- 対象日付の選択
- Chronicle 入力フォルダ / 出力フォルダの選択
- 出力言語の選択
- `draft-update` / `finalize` の切り替え
- アプリ内でレポート / 日記 / 生 Markdown を表示
- 最近の日付や週次アーカイブの閲覧
- 現在ビューのコピー
- 外部アプリで開く

また、Codex の接続状態を表示し、ログイン完了までは生成操作を無効化します。

## macOS パッケージング

アプリバンドルと DMG を生成:

```bash
codex-diary-package-macos
```

または:

```bash
python3 -m codex_diary.package_macos
```

既定の成果物:

- `dist/Codex Diary.app`
- `dist/Codex-Diary-0.1.0-macOS.dmg`

## 対応している diary 出力言語

生成される diary 本文は現在次の言語に対応しています。

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

これは README 翻訳ファイルの数とは別です。つまり、文書翻訳が一部の言語だけでも、アプリと CLI はより多くの言語で diary を生成できます。

## 出力構造

生成される Markdown には、次の 2 ブロックが含まれます。

- `Work Report`
- `Diary Version`

主な内容:

- 今日やったこと
- 細かな流れも含めた時系列メモ
- 重要な確認事項・決定事項
- 詰まった点・未解決の課題
- 明日やること
- 短い振り返り

`Diary Version` は `Work Report` より自然な文章になりますが、画面に現れていない感情や行動を創作しないように設計されています。

## 環境変数

必須の環境変数はありません。

- API キーの入力は不要です。
- 代わりにローカルの Codex ログインセッションを利用します。

## テスト

```bash
python3 -m unittest discover -s tests -v
node --check codex_diary/ui/app.js
python3 -m compileall codex_diary
```

## 制限事項

- Chronicle 要約はすでに二次要約なので、詳細の一部は失われます。
- ローカルに `codex` CLI がインストールされ、ログイン済みでないと生成できません。
- 現在のソースパーサは Chronicle 要約ファイル名が想定どおりの UTC タイムスタンプ形式であることを前提にしています。
- マスキングはパターンベースなので、完全な秘密情報検出ではありません。
- macOS DMG ビルドは現在 unsigned のローカル配布を前提としています。
