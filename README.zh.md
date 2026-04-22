[English](README.md) | [한국어](README.ko.md) | [日本語](README.ja.md) | [中文](README.zh.md)

# codex-diary

一个本地工具，用 Chronicle 的 Markdown 摘要生成按日期归档的工作报告和日记草稿。

`codex-diary` 会读取 `~/.codex/memories_extensions/chronicle/resources/*.md` 这类 Chronicle 摘要文件，并生成对应日期的 Markdown 日记。它不会直接处理原始屏幕录制、JPG 截图或 OCR JSONL，而是明确以 Chronicle 已经生成好的摘要 Markdown 作为输入。

当前生成流程依赖本地 `codex` CLI 登录会话。如果 Codex 不可用或尚未登录，工具会给出连接提示并退出，而不会静默切换到其他提供方。

英文版 `README.md` 是基准文档，其他语言版本在项目变化后可能会有轻微滞后。

## 这个工具的思路

Chronicle 已经把活动轨迹压缩成摘要 Markdown，所以这个项目不会重新处理 raw capture，而是直接复用这些摘要，从而让 diary 流程更轻量，也更有利于隐私控制。

当前 diary 生成策略：

- 优先使用 Chronicle 的 `10min` 摘要
- 仅在需要时把 `6h` 摘要作为补充上下文
- 使用本地时区，默认以 `04:00` 作为跨天边界
- 每天只保留一个输出文件，重新生成时直接覆盖

## 主要功能

- 在同一个 Markdown 文件里同时生成 `Work Report` 和 `Diary Version`
- 支持 `draft-update` 与 `finalize` 两种模式
- 只使用 Chronicle 摘要 Markdown 作为输入
- 支持生成前的敏感信息掩码处理
- 同时提供 CLI 和基于 `pywebview` 的桌面应用
- 支持多语言 diary 输出
- 支持打包 macOS `.dmg`

## 多语言 README 的做法

GitHub 本身不会自动切换 README 语言，所以常见做法是：

- 保留一个主文档 `README.md`
- 增加 `README.ko.md`、`README.ja.md` 之类的翻译文件
- 在每个 README 顶部放语言链接

这个仓库现在已经按这种结构整理好了，所以之后继续增加别的语言会比较容易。

## 运行要求

- Python `3.9+`
- 已安装本地 `codex` CLI
- 已通过 `codex login` 建立有效的 Codex 登录会话

应用内部会通过 `codex login status` 检查登录状态。在 macOS 桌面应用里，也可以按需在 Terminal 中打开 `codex login --device-auth`。

## 安装

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

如果还需要 macOS 打包支持：

```bash
pip install -e ".[macos-build]"
```

## CLI 快速开始

默认输出路径：

- 开发模式：`./output/diary/YYYY-MM-DD.md`
- macOS 打包应用：`~/Library/Application Support/Codex Diary/output/diary/YYYY-MM-DD.md`

示例：

```bash
codex-diary finalize --date 2026-04-21
codex-diary draft-update --date 2026-04-21
codex-diary finalize --date 2026-04-21 --dry-run
codex-diary finalize --date 2026-04-21 --output-language zh
codex-diary finalize --source-dir ~/.codex/memories_extensions/chronicle/resources
codex-diary finalize --out-dir ./custom-output --day-boundary-hour 4
```

主要选项：

- `draft-update` / `finalize`：选择累计草稿或最终 diary 生成
- `--date YYYY-MM-DD`：为指定日期生成
- `--source-dir <path>`：覆盖 Chronicle 摘要目录
- `--out-dir <path>`：指定输出目录
- `--dry-run`：只输出到 stdout，不写文件
- `--day-boundary-hour <0-23>`：设置本地跨天时间，默认 `4`
- `--language <code>` 或 `--output-language <code>`：设置输出语言，默认 `en`

如果 Codex 未连接，命令会以下列提示结束：

```text
먼저 codex를 연결해주세요.
```

## 桌面应用

直接运行：

```bash
python3 -m codex_diary.app
```

安装后的入口命令：

```bash
codex-diary-app
```

应用支持：

- 选择目标日期
- 选择 Chronicle 输入目录和输出目录
- 选择输出语言
- 在 `draft-update` 和 `finalize` 之间切换
- 在应用内查看 report、diary 和原始 Markdown
- 浏览最近日期和每周归档
- 复制当前视图
- 用外部应用打开结果

应用也会显示 Codex 连接状态，并在登录完成前禁用生成操作。

## macOS 打包

构建应用和 DMG：

```bash
codex-diary-package-macos
```

或者：

```bash
python3 -m codex_diary.package_macos
```

默认产物：

- `dist/Codex Diary.app`
- `dist/Codex-Diary-0.1.0-macOS.dmg`

## 支持的 diary 输出语言

当前生成内容支持以下语言：

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

这个列表和 README 翻译文件数量是两回事。也就是说，即使仓库文档只翻译了部分语言，应用和 CLI 仍然可以生成更多语言版本的 diary。

## 输出结构

生成的 Markdown 文件会同时包含这两个部分：

- `Work Report`
- `Diary Version`

通常会包含以下内容：

- 今天做了什么
- 包含细节流程的时间顺序备忘
- 重点确认或决定的事项
- 卡住的点或未解决的问题
- 明天要做的事
- 简短回顾

`Diary Version` 会比报告部分更自然一些，但仍然会尽量保持基于真实可观察工作，不虚构屏幕之外的情绪或活动。

## 环境变量

不需要必填环境变量。

- 不要求输入 API Key。
- 生成依赖的是本地 Codex 登录会话。

## 测试

```bash
python3 -m unittest discover -s tests -v
node --check codex_diary/ui/app.js
python3 -m compileall codex_diary
```

## 限制

- Chronicle 摘要本身已经是二次摘要，因此部分细节不可避免会丢失。
- 如果本地没有安装并登录 `codex` CLI，就无法生成内容。
- 当前源文件解析器假设 Chronicle 摘要文件名使用预期的 UTC 时间戳格式。
- 掩码处理基于模式匹配，不能视为完美的敏感信息检测。
- macOS DMG 打包流程目前面向 unsigned 的本地分发场景。
