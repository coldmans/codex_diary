from __future__ import annotations

from collections import Counter, deque
from datetime import datetime
from difflib import SequenceMatcher
import inspect
from pathlib import Path
import re
from typing import Any, Callable, Iterable, Optional

from .diary_length import DEFAULT_DIARY_LENGTH_CODE, normalize_diary_length
from .chronicle import discover_sources, get_local_timezone, split_sources_by_granularity
from .i18n import get_language_option, heading_labels
from .llm import GenerationCancelledError, LLMError, LLMProvider, load_provider_from_codex
from .models import ChronicleSource, DiaryBuildResult, Event
from .parser import extract_events

LLM_PROMPT_EVENT_LIMIT = 120
LLM_PROMPT_EVENT_TEXT_LIMIT = 240
LLM_PROMPT_SECTION_TITLE_LIMIT = 72
LLM_PROMPT_CHAR_BUDGET = 18000
LLM_PROMPT_PINNED_PER_TAG = 2
PROMPT_PRIORITY_TAGS = ("decision", "blocker", "next_action")
PRIMARY_COVERAGE_BUCKET_MINUTES = 120
MIN_PRIMARY_SPAN_HOURS = 6
DEDUPLICATION_WINDOW_MINUTES = 90
DEDUPLICATION_WINDOW_WITH_6H_MINUTES = 390

APP_STOPWORDS = {
    "Codex",
    "Chrome",
    "Notion",
    "ChatGPT",
    "Claude",
    "Discord",
    "Google AI Studio",
    "KakaoTalk",
    "macOS System Settings",
}
TEXT_STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "that",
    "this",
    "from",
    "into",
    "then",
    "while",
    "user",
    "window",
    "screen",
    "visible",
    "recording",
    "summary",
    "current",
    "their",
    "they",
    "was",
    "were",
    "had",
    "has",
    "there",
    "still",
    "page",
    "project",
    "work",
    "workflow",
    "through",
    "reviewed",
    "checked",
    "current",
    "documentation",
    "docs",
}
MIN_PRIMARY_EVENTS = 5
SUBJECT_HINTS = ("chargeCat", "TripleS", "K-Context Guide", "Chronicle", "Kanana")

DEFAULT_OUTPUT_LANGUAGE = "english"
COMPATIBILITY_FALLBACK_LANGUAGE = "korean"
CANONICAL_REPORT_HEADING = "## 금일 작업 보고서"
CANONICAL_DIARY_HEADING = "## 오늘의 일기 버전"
CANONICAL_SECTION_HEADINGS = {
    "today": "### 오늘 한 일",
    "timeline": "### 사소한 흐름까지 포함한 시간순 메모",
    "decisions": "### 중요하게 확인하거나 결정한 것",
    "blockers": "### 막혔던 점 또는 미해결 이슈",
    "tomorrow": "### 내일 할 일",
    "reflection": "### 짧은 회고",
}

ProgressCallback = Callable[[dict[str, Any]], None]
CancellationCheck = Callable[[], bool]

DIARY_LENGTH_PROFILES: dict[str, dict[str, Any]] = {
    "short": {
        "activity_limit": 5,
        "decision_limit": 4,
        "blocker_limit": 4,
        "next_action_limit": 4,
        "timeline_limit": 14,
        "prompt_event_limit": 120,
        "prompt_char_budget": 18000,
        "diary_paragraph_instruction": "2-4 short paragraphs",
        "guidance": "Keep the report concise and the diary gently compact.",
    },
    "medium": {
        "activity_limit": 6,
        "decision_limit": 5,
        "blocker_limit": 5,
        "next_action_limit": 5,
        "timeline_limit": 22,
        "prompt_event_limit": 150,
        "prompt_char_budget": 22000,
        "diary_paragraph_instruction": "3-5 medium paragraphs",
        "guidance": "Make the diary clearly fuller than the short version, with a bit more connective detail.",
    },
    "long": {
        "activity_limit": 8,
        "decision_limit": 6,
        "blocker_limit": 6,
        "next_action_limit": 6,
        "timeline_limit": 32,
        "prompt_event_limit": 190,
        "prompt_char_budget": 28000,
        "diary_paragraph_instruction": "4-6 fairly full paragraphs",
        "guidance": "Keep the timeline rich and let the diary linger on transitions, comparisons, and context recovery.",
    },
    "very-long": {
        "activity_limit": 10,
        "decision_limit": 8,
        "blocker_limit": 8,
        "next_action_limit": 8,
        "timeline_limit": 44,
        "prompt_event_limit": 240,
        "prompt_char_budget": 36000,
        "diary_paragraph_instruction": "6-8 full paragraphs",
        "guidance": "Be exhaustive while staying factual, and preserve many small but real context switches and follow-up checks.",
    },
}

OUTPUT_LANGUAGE_SPECS: dict[str, dict[str, Any]] = {
    "english": {
        "label": "English",
        "aliases": ("en",),
        "report_heading": "## Work Report",
        "diary_heading": "## Diary Version",
        "sections": {
            "today": "### What I Did Today",
            "timeline": "### Timeline Notes, Including Small Steps",
            "decisions": "### Key Decisions and Confirmations",
            "blockers": "### Blockers or Open Issues",
            "tomorrow": "### Tasks for Tomorrow",
            "reflection": "### Short Reflection",
        },
        "title": {"draft": "Work Diary Draft", "final": "Work Diary"},
        "source_note": "> Compiled from Chronicle {ten_minute} 10-minute summaries{six_hour}.",
        "source_note_six_hour": " and {count} 6-hour summaries",
        "timeline_empty": "- There were not many additional low-signal moments worth keeping as timeline notes.",
        "default_decision": [
            "More than a new decision, the day was useful for re-aligning the current context and priorities."
        ],
        "default_blocker": [
            "There was no severe blocker that stopped the work outright, but a few follow-up checks were still left."
        ],
        "default_next_action": [
            "Pick one nearby implementation or cleanup task and turn today's recovered context into action"
        ],
        "today_empty": "There were not many records to work from, but I still used the Chronicle summaries left on screen to recover today's context.",
        "connectors": ["Early on,", "Then,", "In the middle,", "Later,", "Toward the end,"],
        "diary_intro_empty": "Today was a day of gathering the traces left on screen and tidying the flow, even if only a little.",
        "diary_intro_with_subject": "Today felt like a steady day of holding onto the work. I started by revisiting {subject}, and that context quietly stayed with me through the rest of the day.",
        "diary_intro_generic": "Today felt like a steady day of holding onto the work. A good part of the time went into recovering the flow I was already in.",
        "diary_mood_dense": "a day of bouncing between screens while trying not to lose the thread",
        "diary_mood_calm": "a day of quietly carrying the workflow forward",
        "diary_body_timeline": "I moved between apps and glanced through short documents along the way, so even when the tasks were small, the flow kept going.",
        "diary_body_subject": "Rather than staying in one place, I also kept track of {subject}, and that stood out clearly in today's record.",
        "diary_body_activity": "Rather than staying in one place, I also kept track of {activity}, and that stood out clearly in today's record.",
        "diary_body_decision": "Instead of pushing hard on a new implementation, the day felt more like a moment to realign the direction around {decision}.",
        "diary_body_fallback": "Once I gathered the small traces left on screen, it turned out to be a day of moving my attention around more often than it first seemed.",
        "diary_close": "Still, {blocker}. Tomorrow, starting with {next_action} would probably make the day move a little more cleanly.",
        "diary_tail": "If I had to put it in one line, {reflection}",
        "reflection": {
            "multi_project": "Rather than pushing one implementation straight through, more of the day went into moving between projects and documents to recover context and compare options.",
            "single_project": "More of the day went into re-establishing the current state and choosing the next move than into direct implementation.",
            "research": "Because I checked documentation and references along the way, I gathered enough grounding to make the next decision with a bit more confidence.",
            "blocker": "If the remaining verification items keep slipping, the next session may drift back into exploration, so it would help to break the follow-up into smaller concrete actions.",
            "clear": "Now it would be best to connect the recovered context to one or two concrete implementation or cleanup tasks right away.",
        },
    },
    "korean": {
        "label": "Korean",
        "aliases": ("ko", "kr"),
        "report_heading": CANONICAL_REPORT_HEADING,
        "diary_heading": CANONICAL_DIARY_HEADING,
        "sections": {
            "today": CANONICAL_SECTION_HEADINGS["today"],
            "timeline": CANONICAL_SECTION_HEADINGS["timeline"],
            "decisions": CANONICAL_SECTION_HEADINGS["decisions"],
            "blockers": CANONICAL_SECTION_HEADINGS["blockers"],
            "tomorrow": CANONICAL_SECTION_HEADINGS["tomorrow"],
            "reflection": CANONICAL_SECTION_HEADINGS["reflection"],
        },
    },
    "japanese": {
        "label": "Japanese",
        "aliases": ("ja", "jp"),
        "report_heading": "## 今日の作業レポート",
        "diary_heading": "## 今日の日記バージョン",
        "sections": {
            "today": "### 今日やったこと",
            "timeline": "### 細かな流れも含めた時系列メモ",
            "decisions": "### 重要な確認事項・決定事項",
            "blockers": "### 詰まった点・未解決の課題",
            "tomorrow": "### 明日やること",
            "reflection": "### 短い振り返り",
        },
        "title": {"draft": "作業日記ドラフト", "final": "作業日記"},
        "source_note": "> Chronicle の10分要約 {ten_minute} 件{six_hour}をもとに整理した。",
        "source_note_six_hour": "と6時間要約 {count} 件",
        "timeline_empty": "- 時系列メモとして残すほどの細かな流れはあまり多くなかった。",
        "default_decision": ["新しい決定よりも、現在の文脈と優先順位をもう一度そろえることに意味があった日だった。"],
        "default_blocker": ["作業を完全に止める致命的な障害は見えなかったが、あとで確認すべき点はいくつか残っていた。"],
        "default_next_action": ["今日取り戻した文脈を、いちばん近い実装または整理タスクにすぐつなげる"],
        "today_empty": "使える記録は多くなかったが、画面に残っていた Chronicle の要約を手掛かりに今日の文脈を整理し直した。",
        "connectors": ["最初は", "続いて", "途中では", "その後は", "終わりごろには"],
        "diary_intro_empty": "今日は画面に残っていた記録を集めながら、小さくても流れを整えておいた一日だった。",
        "diary_intro_with_subject": "今日は作業の流れを静かにつかみ直す一日だった。始まりは {subject} を見直すところからで、その文脈が一日を通してそっと続いていた。",
        "diary_intro_generic": "今日は作業の流れを静かにつかみ直す一日だった。最初から、すでに進んでいた流れをもう一度手元に戻すことに時間を使った感じだった。",
        "diary_mood_dense": "いろいろな画面を行き来しながら流れをつなぎ止めていた日",
        "diary_mood_calm": "作業の流れを落ち着いてつないでいった日",
        "diary_body_timeline": "途中でアプリを行き来したり短い資料を確認したりしながら、大きな作業だけではなくても流れを切らさないようにしていた。",
        "diary_body_subject": "ひとつの場所にとどまるより、{subject} まで一緒に追っていたことが今日の記録にはっきり残っていた。",
        "diary_body_activity": "ひとつの場所にとどまるより、{activity} まで一緒に追っていたことが今日の記録にはっきり残っていた。",
        "diary_body_decision": "何かを強く押し進めるというより、{decision} くらいの温度で方向を整え直した一日に近かった。",
        "diary_body_fallback": "画面に残っていた細かな痕跡まで集めてみると、思ったよりも視線と手をこまめに動かしていた日だった。",
        "diary_close": "ただ、{blocker} という点は軽く残っていた。明日は {next_action} からつかむと、一日がもう少し気持ちよく回りそうだ。",
        "diary_tail": "ひとことで書いておくなら、{reflection}",
        "reflection": {
            "multi_project": "一つの実装だけを押し進めるより、複数のプロジェクトや文書を行き来しながら文脈を復元し、比較していた時間の比重が大きかった。",
            "single_project": "直接の実装よりも、現在の状態を整理し直して次の一手を選ぶことに時間を使っていた流れが見えた。",
            "research": "文書や参照資料も合わせて確認したおかげで、次の判断に必要な根拠はある程度そろった。",
            "blocker": "残っている検証項目を先送りにすると次の作業がまた探索寄りに流れそうなので、後続作業はもっと小さく切っておくほうがよさそうだ。",
            "clear": "ここからは整理した文脈を、実際の実装や整理作業一つ二つにすぐつなげるのがよさそうだ。",
        },
    },
    "chinese": {
        "label": "Chinese",
        "aliases": ("zh", "cn"),
        "report_heading": "## 今日工作报告",
        "diary_heading": "## 今日日记版",
        "sections": {
            "today": "### 今天做了什么",
            "timeline": "### 包含细节流程的时间顺序备忘",
            "decisions": "### 重点确认或决定的事项",
            "blockers": "### 卡住的点或未解决的问题",
            "tomorrow": "### 明天要做的事",
            "reflection": "### 简短回顾",
        },
        "title": {"draft": "工作日记草稿", "final": "工作日记"},
        "source_note": "> 根据 Chronicle 的 {ten_minute} 份10分钟摘要{six_hour}整理。",
        "source_note_six_hour": "和 {count} 份6小时摘要",
        "timeline_empty": "- 值得单独记成时间线的细碎流程并不多。",
        "default_decision": ["与其说有新的决定，不如说这一天更适合重新对齐当前语境和优先级。"],
        "default_blocker": ["没有看到会让工作立刻停下来的严重阻碍，但仍有一些后续确认项留着。"],
        "default_next_action": ["把今天恢复出来的语境，立即连接到一个最近的实现或整理任务上"],
        "today_empty": "可用记录不算多，但还是借着屏幕上留下的 Chronicle 摘要重新整理了今天的工作语境。",
        "connectors": ["开始时", "接着", "中途", "后来", "临近结束时"],
        "diary_intro_empty": "今天像是把屏幕上留下的痕迹重新收拢起来，哪怕只是小幅度地把流程整理顺的一天。",
        "diary_intro_with_subject": "今天像是在安静地重新抓住工作流的一天。开始是从回看 {subject} 起步，那条语境也轻轻地陪着我走完整天。",
        "diary_intro_generic": "今天像是在安静地重新抓住工作流的一天。很多时间都花在把已经在做的那条线重新接回手里。",
        "diary_mood_dense": "在多个界面之间来回切换、努力不让线索断掉的一天",
        "diary_mood_calm": "平稳地把工作流继续往前带的一天",
        "diary_body_timeline": "中间会切换应用，也会顺手看一些短文档，所以就算不是大任务，流程也一直没有断。",
        "diary_body_subject": "今天并不只是停留在一个地方，我也同时照看了 {subject}，这点在记录里留下了很清楚的痕迹。",
        "diary_body_activity": "今天并不只是停留在一个地方，我也同时照看了 {activity}，这点在记录里留下了很清楚的痕迹。",
        "diary_body_decision": "与其说是在猛推新的实现，不如说今天更像是在围绕 {decision} 重新把方向校准了一下。",
        "diary_body_fallback": "把屏幕上留下的细碎痕迹都收起来看，才发现今天比想象中更频繁地在不同事情之间切换。",
        "diary_close": "不过，{blocker} 这一点还是轻轻地留了下来。明天如果先从 {next_action} 开始，整天大概会更顺一点。",
        "diary_tail": "如果要用一句话记下来的话，{reflection}",
        "reflection": {
            "multi_project": "比起一口气推进单个实现，这一天更像是在多个项目和文档之间往返，恢复语境并做比较判断。",
            "single_project": "比起直接实现，更能看到的是先把当前状态重新理顺，再决定下一步要怎么走。",
            "research": "因为也一起查了文档和参考资料，下一次做判断时需要的依据已经积累得比较够了。",
            "blocker": "如果把剩下的验证项继续往后拖，下一轮工作可能又会回到探索模式，所以最好把后续动作拆得再小一点。",
            "clear": "接下来更合适的是把整理好的语境，立刻接到一两个具体的实现或整理动作上。",
        },
    },
    "french": {
        "label": "French",
        "aliases": ("fr",),
        "report_heading": "## Rapport de travail du jour",
        "diary_heading": "## Version journal du jour",
        "sections": {
            "today": "### Ce que j'ai fait aujourd'hui",
            "timeline": "### Notes chronologiques, y compris les petits mouvements",
            "decisions": "### Points importants verifies ou decides",
            "blockers": "### Blocages ou points encore ouverts",
            "tomorrow": "### Ce qu'il faut faire demain",
            "reflection": "### Courte retrospective",
        },
        "title": {"draft": "Brouillon de journal de travail", "final": "Journal de travail"},
        "source_note": "> Compile a partir de {ten_minute} resumes Chronicle de 10 minutes{six_hour}.",
        "source_note_six_hour": " et de {count} resumes de 6 heures",
        "timeline_empty": "- Il n'y avait pas beaucoup de petits mouvements supplementaires qui valaient une note chronologique.",
        "default_decision": ["Plus qu'une nouvelle decision, la journee a surtout servi a remettre le contexte et les priorites au clair."],
        "default_blocker": ["Aucun blocage critique n'a completement arrete le travail, mais quelques verifications restaient a faire."],
        "default_next_action": ["Transformer le contexte retrouve aujourd'hui en une tache concrete d'implementation ou de rangement"],
        "today_empty": "Il n'y avait pas beaucoup de traces a exploiter, mais j'ai quand meme repris le contexte du jour a partir des resumes Chronicle visibles a l'ecran.",
        "connectors": ["Au debut,", "Ensuite,", "Au milieu,", "Puis,", "Vers la fin,"],
        "diary_intro_empty": "Aujourd'hui, j'ai surtout rassemble les traces laissees a l'ecran pour remettre un peu d'ordre dans le fil de la journee.",
        "diary_intro_with_subject": "Aujourd'hui ressemblait a une journee passee a reprendre doucement le fil du travail. J'ai commence par revoir {subject}, et ce contexte est reste avec moi jusqu'au bout.",
        "diary_intro_generic": "Aujourd'hui ressemblait a une journee passee a reprendre doucement le fil du travail. Une bonne partie du temps a servi a retrouver le fil deja en cours.",
        "diary_mood_dense": "une journee passee a naviguer entre plusieurs ecrans sans vouloir perdre le fil",
        "diary_mood_calm": "une journee passee a faire avancer le flux de travail avec calme",
        "diary_body_timeline": "J'ai circule entre plusieurs applications et parcouru de courts documents, donc meme quand les taches etaient petites, le fil ne s'est pas casse.",
        "diary_body_subject": "Au lieu de rester a un seul endroit, j'ai aussi garde {subject} en vue, et cela ressort nettement dans les notes du jour.",
        "diary_body_activity": "Au lieu de rester a un seul endroit, j'ai aussi garde {activity} en vue, et cela ressort nettement dans les notes du jour.",
        "diary_body_decision": "Plutot que de pousser une nouvelle implementation, la journee a surtout servi a realigner la direction autour de {decision}.",
        "diary_body_fallback": "En rassemblant meme les petites traces laissees a l'ecran, je me rends compte que j'ai change de point d'attention plus souvent que je ne l'imaginais.",
        "diary_close": "Cela dit, {blocker}. Demain, commencer par {next_action} aiderait sans doute la journee a avancer plus proprement.",
        "diary_tail": "Si je devais le resumer en une ligne, {reflection}",
        "reflection": {
            "multi_project": "Plutot que de pousser une seule implementation, la journee a surtout consiste a circuler entre plusieurs projets et documents pour retrouver le contexte et comparer les options.",
            "single_project": "On voit une journee passee davantage a remettre l'etat courant au clair et a choisir la suite qu'a implementer directement.",
            "research": "Le fait de verifier aussi la documentation et les references m'a donne une base suffisante pour prendre la prochaine decision avec plus d'assurance.",
            "blocker": "Si les verifications restantes continuent de glisser, la prochaine session risque de repartir en exploration, donc mieux vaut decouper la suite en actions plus petites.",
            "clear": "A partir de maintenant, le mieux serait de relier tout de suite ce contexte retrouve a une ou deux taches concretes d'implementation ou de rangement.",
        },
    },
    "german": {
        "label": "German",
        "aliases": ("de",),
        "report_heading": "## Arbeitsbericht des Tages",
        "diary_heading": "## Tagebuchversion von heute",
        "sections": {
            "today": "### Was ich heute gemacht habe",
            "timeline": "### Zeitliche Notizen, auch zu kleinen Schritten",
            "decisions": "### Wichtige Bestatigungen oder Entscheidungen",
            "blockers": "### Blocker oder offene Punkte",
            "tomorrow": "### Aufgaben fur morgen",
            "reflection": "### Kurze Reflexion",
        },
        "title": {"draft": "Arbeitsjournal Entwurf", "final": "Arbeitsjournal"},
        "source_note": "> Zusammengestellt aus {ten_minute} Chronicle-Zusammenfassungen im 10-Minuten-Takt{six_hour}.",
        "source_note_six_hour": " und {count} Zusammenfassungen im 6-Stunden-Takt",
        "timeline_empty": "- Es gab nicht viele zusatzliche kleine Momente, die als Zeitnotiz festgehalten werden mussten.",
        "default_decision": ["Wichtiger als eine neue Entscheidung war heute das erneute Ausrichten von Kontext und Prioritaten."],
        "default_blocker": ["Es gab keinen kritischen Blocker, der die Arbeit komplett gestoppt hat, aber einige Nachprufungen sind offen geblieben."],
        "default_next_action": ["Den heute wiederhergestellten Kontext direkt in eine konkrete Implementierungs- oder Aufraumaufgabe uberfuhren"],
        "today_empty": "Es gab nicht viele verwertbare Spuren, aber ich habe den Tageskontext trotzdem uber die sichtbaren Chronicle-Zusammenfassungen wieder zusammengesetzt.",
        "connectors": ["Am Anfang", "Danach", "Zwischendurch", "Spater", "Gegen Ende"],
        "diary_intro_empty": "Heute war ein Tag, an dem ich vor allem die auf dem Bildschirm gebliebenen Spuren gesammelt und den Ablauf ein wenig sortiert habe.",
        "diary_intro_with_subject": "Heute fuhlte sich an wie ein ruhiger Tag, an dem ich den Arbeitsfluss wieder aufgenommen habe. Ich habe mit {subject} begonnen, und dieser Kontext blieb den ganzen Tag bei mir.",
        "diary_intro_generic": "Heute fuhlte sich an wie ein ruhiger Tag, an dem ich den Arbeitsfluss wieder aufgenommen habe. Ein guter Teil der Zeit ging darauf, den laufenden Faden wieder in die Hand zu bekommen.",
        "diary_mood_dense": "ein Tag, an dem ich zwischen mehreren Bildschirmen hin und her gewechselt habe, ohne den Faden verlieren zu wollen",
        "diary_mood_calm": "ein Tag, an dem ich den Arbeitsfluss ruhig weitergetragen habe",
        "diary_body_timeline": "Ich bin zwischen Apps gewechselt und habe kurze Dokumente uberflogen, sodass der Fluss selbst bei kleinen Aufgaben nicht abgerissen ist.",
        "diary_body_subject": "Statt nur an einer Stelle zu bleiben, habe ich auch {subject} mit im Blick behalten, und das ist in den Notizen des Tages deutlich zu sehen.",
        "diary_body_activity": "Statt nur an einer Stelle zu bleiben, habe ich auch {activity} mit im Blick behalten, und das ist in den Notizen des Tages deutlich zu sehen.",
        "diary_body_decision": "Anstatt eine neue Umsetzung hart voranzutreiben, ging es heute eher darum, die Richtung rund um {decision} neu auszurichten.",
        "diary_body_fallback": "Als ich sogar die kleinen Spuren auf dem Bildschirm eingesammelt habe, wurde klar, dass ich meinen Fokus heute haufiger verlagert habe, als es zuerst wirkte.",
        "diary_close": "Trotzdem blieb {blocker}. Morgen ware es vermutlich am saubersten, mit {next_action} zu beginnen.",
        "diary_tail": "Wenn ich es in einem Satz festhalten soll, {reflection}",
        "reflection": {
            "multi_project": "Statt eine einzelne Umsetzung durchzudrucken, bestand der Tag eher daraus, zwischen mehreren Projekten und Dokumenten zu wechseln, um Kontext wiederherzustellen und Optionen zu vergleichen.",
            "single_project": "Der Tag ging eher darauf, den aktuellen Stand neu zu ordnen und den nachsten Schritt zu wahlen, als direkt zu implementieren.",
            "research": "Weil ich unterwegs auch Dokumentation und Referenzen gepruft habe, ist nun genug Grundlage fur die nachste Entscheidung da.",
            "blocker": "Wenn die offenen Prufpunkte weiter nach hinten rutschen, konnte die nachste Sitzung wieder zu sehr in Erkundung abgleiten. Kleinere Folgeschritte waren deshalb besser.",
            "clear": "Jetzt ware es am besten, den wiederhergestellten Kontext sofort in ein oder zwei konkrete Implementierungs- oder Aufraumaufgaben zu uberfuhren.",
        },
    },
    "spanish": {
        "label": "Spanish",
        "aliases": ("es",),
        "report_heading": "## Informe de trabajo del dia",
        "diary_heading": "## Version de diario de hoy",
        "sections": {
            "today": "### Lo que hice hoy",
            "timeline": "### Notas cronologicas, incluidos los pasos pequenos",
            "decisions": "### Confirmaciones o decisiones importantes",
            "blockers": "### Bloqueos o temas abiertos",
            "tomorrow": "### Tareas para manana",
            "reflection": "### Reflexion breve",
        },
        "title": {"draft": "Borrador de diario de trabajo", "final": "Diario de trabajo"},
        "source_note": "> Organizado a partir de {ten_minute} resumenes de Chronicle de 10 minutos{six_hour}.",
        "source_note_six_hour": " y {count} resumenes de 6 horas",
        "timeline_empty": "- No hubo muchos movimientos pequenos adicionales que valiera la pena dejar como nota cronologica.",
        "default_decision": ["Mas que una nueva decision, el dia sirvio para volver a alinear el contexto y las prioridades."],
        "default_blocker": ["No aparecio un bloqueo grave que detuviera por completo el trabajo, pero quedaron algunas verificaciones pendientes."],
        "default_next_action": ["Convertir el contexto recuperado hoy en una tarea concreta de implementacion o de orden"],
        "today_empty": "No habia demasiados rastros para usar, pero aun asi reorganice el contexto del dia apoyandome en los resumenes de Chronicle visibles en pantalla.",
        "connectors": ["Al principio,", "Luego,", "A mitad del proceso,", "Despues,", "Hacia el final,"],
        "diary_intro_empty": "Hoy fue un dia de reunir las huellas que quedaron en pantalla y ordenar un poco el flujo, aunque fuera de manera pequena.",
        "diary_intro_with_subject": "Hoy se sintio como un dia de retomar el flujo de trabajo con calma. Empece revisando {subject}, y ese contexto se quedo conmigo durante el resto del dia.",
        "diary_intro_generic": "Hoy se sintio como un dia de retomar el flujo de trabajo con calma. Buena parte del tiempo se fue en volver a agarrar el hilo que ya estaba en marcha.",
        "diary_mood_dense": "un dia de ir saltando entre pantallas sin querer perder el hilo",
        "diary_mood_calm": "un dia de seguir el flujo de trabajo con calma",
        "diary_body_timeline": "Fui cambiando entre aplicaciones y mirando documentos cortos, asi que incluso cuando las tareas eran pequenas, el flujo no se corto.",
        "diary_body_subject": "En lugar de quedarme en un solo sitio, tambien mantuve a la vista {subject}, y eso quedo bastante claro en el registro de hoy.",
        "diary_body_activity": "En lugar de quedarme en un solo sitio, tambien mantuve a la vista {activity}, y eso quedo bastante claro en el registro de hoy.",
        "diary_body_decision": "Mas que empujar con fuerza una implementacion nueva, el dia se sintio como un momento para volver a alinear la direccion alrededor de {decision}.",
        "diary_body_fallback": "Al juntar incluso las pequenas huellas que quedaron en pantalla, se noto que hoy cambie de foco mas veces de lo que parecia al principio.",
        "diary_close": "Aun asi, {blocker}. Manana probablemente convenga empezar por {next_action}.",
        "diary_tail": "Si tuviera que dejarlo en una sola linea, {reflection}",
        "reflection": {
            "multi_project": "Mas que empujar una sola implementacion, el dia se fue en moverme entre varios proyectos y documentos para recuperar contexto y comparar opciones.",
            "single_project": "Se ve un dia mas enfocado en volver a ordenar el estado actual y elegir el siguiente paso que en implementar directamente.",
            "research": "Como tambien revise documentacion y referencias, ya tengo una base suficiente para tomar la siguiente decision con algo mas de claridad.",
            "blocker": "Si las verificaciones pendientes siguen aplazandose, la proxima sesion puede volver a caer en exploracion, asi que conviene partir el seguimiento en pasos mas pequenos.",
            "clear": "Ahora lo mejor seria conectar este contexto recuperado con una o dos tareas concretas de implementacion o de orden cuanto antes.",
        },
    },
    "vietnamese": {
        "label": "Vietnamese",
        "aliases": ("vi",),
        "report_heading": "## Bao cao cong viec hom nay",
        "diary_heading": "## Phien ban nhat ky hom nay",
        "sections": {
            "today": "### Hom nay da lam gi",
            "timeline": "### Ghi chu theo trinh tu thoi gian, ke ca cac buoc nho",
            "decisions": "### Nhung dieu quan trong da xac nhan hoac quyet dinh",
            "blockers": "### Diem bi nghen hoac van de chua xong",
            "tomorrow": "### Viec can lam ngay mai",
            "reflection": "### Nhin lai ngan",
        },
        "title": {"draft": "Ban nhap nhat ky cong viec", "final": "Nhat ky cong viec"},
        "source_note": "> Tong hop dua tren {ten_minute} ban tom tat Chronicle 10 phut{six_hour}.",
        "source_note_six_hour": " va {count} ban tom tat 6 gio",
        "timeline_empty": "- Khong co nhieu chuyen dong nho bo sung can luu thanh ghi chu theo thoi gian.",
        "default_decision": ["Khong phai la mot quyet dinh moi, ma la mot ngay de can chinh lai boi canh va uu tien hien tai."],
        "default_blocker": ["Khong thay tro ngai nghiem trong den muc dung han cong viec, nhung van con vai muc can kiem tra tiep."],
        "default_next_action": ["Bien boi canh da phuc hoi hom nay thanh mot tac vu cu the de implement hoac sap xep"],
        "today_empty": "Khong co qua nhieu dau vet de dua vao, nhung toi van dung cac tom tat Chronicle con hien tren man hinh de thu gom lai boi canh cua ngay hom nay.",
        "connectors": ["Luc dau,", "Sau do,", "O giua qua trinh,", "Tiep theo,", "Gan cuoi,"],
        "diary_intro_empty": "Hom nay giong nhu mot ngay gom lai nhung dau vet con tren man hinh va sap xep lai dong chay cong viec du chi mot chut.",
        "diary_intro_with_subject": "Hom nay la mot ngay binh tinh de nam lai dong cong viec. Toi bat dau bang viec xem lai {subject}, va boi canh do nhe nhang di cung toi den het ngay.",
        "diary_intro_generic": "Hom nay la mot ngay binh tinh de nam lai dong cong viec. Kha nhieu thoi gian duoc dung de bat lai mach dang lam do.",
        "diary_mood_dense": "mot ngay di lai giua nhieu man hinh ma van co gang giu mach cong viec",
        "diary_mood_calm": "mot ngay tiep tuc dong cong viec mot cach nhe nhang",
        "diary_body_timeline": "Toi di qua lai giua cac ung dung va xem nhanh mot vai tai lieu ngan, nen du cong viec nho, dong chay van khong bi dut.",
        "diary_body_subject": "Thay vi o yen mot cho, toi cung theo sat {subject}, va dieu do hien len kha ro trong ghi chep hom nay.",
        "diary_body_activity": "Thay vi o yen mot cho, toi cung theo sat {activity}, va dieu do hien len kha ro trong ghi chep hom nay.",
        "diary_body_decision": "Thay vi day manh mot implement moi, hom nay giong nhu mot luc de can chinh lai huong di quanh {decision}.",
        "diary_body_fallback": "Khi gom ca nhung dau vet nho con tren man hinh, moi thay hom nay toi da doi diem chu y nhieu hon luc dau nghi.",
        "diary_close": "Dau vay, {blocker}. Ngay mai bat dau tu {next_action} co le se lam cho ca ngay troi hon.",
        "diary_tail": "Neu phai ghi gon trong mot cau, {reflection}",
        "reflection": {
            "multi_project": "Thay vi day mot implement duy nhat, phan lon ngay hom nay da dung de qua lai giua nhieu du an va tai lieu nham phuc hoi boi canh va so sanh lua chon.",
            "single_project": "Co ve ngay hom nay dung de sap xep lai trang thai hien tai va chon buoc tiep theo nhieu hon la implement truc tiep.",
            "research": "Vi cung da xem tai lieu va tai nguyen tham khao, toi da co du co so de dua ra quyet dinh tiep theo chac hon mot chut.",
            "blocker": "Neu cac muc can xac minh con tiep tuc bi day lui, phien tiep theo co the lai tro ve che do tham do, vi vay nen chia buoc tiep theo nho hon se tot hon.",
            "clear": "Luc nay tot nhat la noi boi canh da phuc hoi nay vao mot hai tac vu implement hoac don dep cu the ngay.",
        },
    },
    "thai": {
        "label": "Thai",
        "aliases": ("th",),
        "report_heading": "## รายงานงานของวันนี้",
        "diary_heading": "## เวอร์ชันไดอารีของวันนี้",
        "sections": {
            "today": "### วันนี้ทำอะไรบ้าง",
            "timeline": "### บันทึกตามลำดับเวลา รวมถึงจังหวะเล็กๆ",
            "decisions": "### สิ่งสำคัญที่ยืนยันหรือได้ตัดสินใจ",
            "blockers": "### จุดที่ติดหรือประเด็นที่ยังค้าง",
            "tomorrow": "### สิ่งที่จะทำพรุ่งนี้",
            "reflection": "### ทบทวนสั้นๆ",
        },
        "title": {"draft": "ร่างบันทึกงาน", "final": "บันทึกงาน"},
        "source_note": "> สรุปจาก Chronicle 10 นาทีจำนวน {ten_minute} ชุด{six_hour}",
        "source_note_six_hour": " และสรุป 6 ชั่วโมงจำนวน {count} ชุด",
        "timeline_empty": "- ไม่มีจังหวะย่อยเพิ่มเติมมากนักที่ควรเก็บไว้เป็นโน้ตตามเวลา",
        "default_decision": ["วันนี้ไม่ได้มีการตัดสินใจใหม่มากนัก แต่เป็นวันที่ใช้จัดแนวบริบทและลำดับความสำคัญให้ตรงกันอีกครั้ง"],
        "default_blocker": ["ไม่มีอุปสรรคหนักจนงานหยุดทันที แต่ยังมีรายการที่ต้องตรวจต่ออีกเล็กน้อย"],
        "default_next_action": ["เปลี่ยนบริบทที่กู้คืนได้วันนี้ให้กลายเป็นงาน implement หรือเก็บงานที่ทำต่อได้ทันที"],
        "today_empty": "แม้จะมีร่องรอยให้ใช้งานไม่มาก แต่ก็ยังใช้สรุป Chronicle ที่ค้างอยู่บนหน้าจอช่วยดึงบริบทของวันนี้กลับมาได้",
        "connectors": ["ช่วงแรก", "จากนั้น", "ตรงกลางวัน", "ต่อมา", "ช่วงท้าย"],
        "diary_intro_empty": "วันนี้เหมือนเป็นวันที่ค่อยๆ เก็บร่องรอยที่เหลืออยู่บนหน้าจอ แล้วจัดระเบียบจังหวะการทำงานให้เข้าที่ขึ้นอีกนิด",
        "diary_intro_with_subject": "วันนี้เป็นวันที่ค่อยๆ จับจังหวะงานกลับมาใหม่ จุดเริ่มต้นคือการย้อนดู {subject} และบริบทนั้นก็อยู่กับฉันไปทั้งวันอย่างเงียบๆ",
        "diary_intro_generic": "วันนี้เป็นวันที่ค่อยๆ จับจังหวะงานกลับมาใหม่ เวลาส่วนหนึ่งหมดไปกับการดึงเส้นงานเดิมกลับมาให้อยู่ในมืออีกครั้ง",
        "diary_mood_dense": "วันที่สลับไปมาระหว่างหลายหน้าจอแต่พยายามไม่ให้เส้นงานหลุดมือ",
        "diary_mood_calm": "วันที่ค่อยๆ พางานเดินต่ออย่างนิ่งๆ",
        "diary_body_timeline": "ระหว่างทางมีการสลับแอปและเปิดดูเอกสารสั้นๆ บ้าง ถึงงานจะไม่ใหญ่ แต่จังหวะก็ยังเดินต่อเนื่อง",
        "diary_body_subject": "วันนี้ไม่ได้อยู่กับอย่างเดียว แต่ยังคอยตามดู {subject} ไปด้วย และร่องรอยนั้นก็ชัดเจนอยู่ในบันทึกของวันนี้",
        "diary_body_activity": "วันนี้ไม่ได้อยู่กับอย่างเดียว แต่ยังคอยตามดู {activity} ไปด้วย และร่องรอยนั้นก็ชัดเจนอยู่ในบันทึกของวันนี้",
        "diary_body_decision": "แทนที่จะเร่งดัน implementation ใหม่ วันนี้กลับใกล้เคียงกับการค่อยๆ จัดทิศทางรอบๆ {decision} ให้เข้าที่มากกว่า",
        "diary_body_fallback": "พอลองเก็บแม้แต่ร่องรอยเล็กๆ ที่ค้างอยู่บนหน้าจอมารวมกัน ก็เห็นว่าฉันย้ายจุดสนใจบ่อยกว่าที่คิดไว้ตอนแรก",
        "diary_close": "อย่างไรก็ดี {blocker} ยังหลงเหลืออยู่เบาๆ พรุ่งนี้ถ้าเริ่มจาก {next_action} ก่อน วันก็น่าจะไหลได้ลื่นขึ้น",
        "diary_tail": "ถ้าจะเขียนสรุปไว้เพียงประโยคเดียว {reflection}",
        "reflection": {
            "multi_project": "แทนที่จะดัน implementation เดียวให้สุด วันนี้กลับใช้เวลาไปกับการสลับระหว่างหลายโปรเจกต์และหลายเอกสารเพื่อกู้บริบทและเปรียบเทียบตัวเลือก",
            "single_project": "วันนี้ดูจะใช้เวลาไปกับการจัดระเบียบสถานะปัจจุบันและเลือกก้าวถัดไป มากกว่าการ implement ตรงๆ",
            "research": "เพราะได้เปิดดูเอกสารและข้อมูลอ้างอิงไปพร้อมกัน จึงมีฐานข้อมูลพอสำหรับการตัดสินใจครั้งถัดไปมากขึ้น",
            "blocker": "ถ้ารายการตรวจสอบที่เหลือยังถูกเลื่อนไปเรื่อยๆ รอบถัดไปอาจกลับไปวนอยู่กับการสำรวจอีก ดังนั้นควรหั่นงานต่อให้ออกมาเล็กกว่านี้",
            "clear": "จากนี้คงดีที่สุดถ้าจะเชื่อมบริบทที่กู้คืนได้เข้ากับงาน implement หรือเก็บงานจริงสักหนึ่งหรือสองชิ้นทันที",
        },
    },
    "russian": {
        "label": "Russian",
        "aliases": ("ru",),
        "report_heading": "## Рабочий отчет за сегодня",
        "diary_heading": "## Дневниковая версия за сегодня",
        "sections": {
            "today": "### Что я сделал сегодня",
            "timeline": "### Хронологические заметки, включая мелкие шаги",
            "decisions": "### Важные подтверждения и решения",
            "blockers": "### Блокеры или открытые вопросы",
            "tomorrow": "### Что сделать завтра",
            "reflection": "### Короткая рефлексия",
        },
        "title": {"draft": "Черновик рабочего дневника", "final": "Рабочий дневник"},
        "source_note": "> Сводка составлена по {ten_minute} десятиминутным Chronicle-сводкам{six_hour}.",
        "source_note_six_hour": " и {count} шестичасовым сводкам",
        "timeline_empty": "- Не было многих дополнительных мелких моментов, которые стоило бы отдельно оставить в хронологической заметке.",
        "default_decision": ["Сегодня важнее было не принять новое решение, а заново выровнять текущий контекст и приоритеты."],
        "default_blocker": ["Не было критического блокера, который полностью остановил бы работу, но несколько проверок все еще остались."],
        "default_next_action": ["Сразу перевести восстановленный сегодня контекст в одну конкретную задачу по реализации или наведению порядка"],
        "today_empty": "Опорных следов было не так много, но я все равно восстановил контекст дня по Chronicle-сводкам, оставшимся на экране.",
        "connectors": ["Сначала", "Затем", "Посередине", "Позже", "Ближе к концу"],
        "diary_intro_empty": "Сегодняшний день был похож на сбор следов, оставшихся на экране, и на аккуратную попытку немного выровнять рабочий поток.",
        "diary_intro_with_subject": "Сегодня был спокойный день, в котором я снова поймал рабочий поток. Началось все с того, что я пересмотрел {subject}, и этот контекст тихо сопровождал меня до конца дня.",
        "diary_intro_generic": "Сегодня был спокойный день, в котором я снова поймал рабочий поток. Значительная часть времени ушла на то, чтобы заново взять в руки уже начатую линию работы.",
        "diary_mood_dense": "день, когда я переключался между разными экранами и старался не потерять нить",
        "diary_mood_calm": "день, когда я спокойно продолжал рабочий поток",
        "diary_body_timeline": "По ходу дела я переключался между приложениями и просматривал короткие документы, так что даже маленькие задачи не обрывали общий ход.",
        "diary_body_subject": "Сегодня я не держался только за одно место, но и продолжал следить за {subject}, и это довольно ясно осталось в записях.",
        "diary_body_activity": "Сегодня я не держался только за одно место, но и продолжал следить за {activity}, и это довольно ясно осталось в записях.",
        "diary_body_decision": "Вместо того чтобы резко продавливать новую реализацию, день скорее ушел на то, чтобы заново выровнять направление вокруг {decision}.",
        "diary_body_fallback": "Когда я собрал даже мелкие следы, оставшиеся на экране, оказалось, что сегодня я переключал внимание чаще, чем казалось сначала.",
        "diary_close": "И все же {blocker}. Завтра, если начать с {next_action}, день, вероятно, пойдет чуть чище.",
        "diary_tail": "Если оставить это в одной строке, {reflection}",
        "reflection": {
            "multi_project": "Вместо того чтобы продавливать одну реализацию, большая часть дня ушла на переходы между несколькими проектами и документами, чтобы восстановить контекст и сравнить варианты.",
            "single_project": "День скорее ушел на то, чтобы заново упорядочить текущее состояние и выбрать следующий шаг, чем на прямую реализацию.",
            "research": "Поскольку я параллельно проверял документацию и справочные материалы, теперь есть достаточно опоры для следующего решения.",
            "blocker": "Если оставшиеся проверки и дальше будут откладываться, следующая сессия снова может уйти в исследование, так что полезно разбить продолжение на более мелкие шаги.",
            "clear": "Теперь лучше всего сразу связать восстановленный контекст с одной-двумя конкретными задачами по реализации или наведению порядка.",
        },
    },
    "hindi": {
        "label": "Hindi",
        "aliases": ("hi",),
        "report_heading": "## आज की कार्य रिपोर्ट",
        "diary_heading": "## आज की डायरी संस्करण",
        "sections": {
            "today": "### आज क्या किया",
            "timeline": "### छोटे कदमों सहित समयानुक्रम नोट्स",
            "decisions": "### महत्वपूर्ण पुष्टि या फैसले",
            "blockers": "### अटके हुए बिंदु या खुले मुद्दे",
            "tomorrow": "### कल के काम",
            "reflection": "### छोटी समीक्षा",
        },
        "title": {"draft": "कार्य डायरी ड्राफ्ट", "final": "कार्य डायरी"},
        "source_note": "> Chronicle की {ten_minute} दस-मिनट सारांशों{six_hour} के आधार पर संकलित।",
        "source_note_six_hour": " और {count} छह-घंटे सारांशों",
        "timeline_empty": "- समयानुक्रम नोट के रूप में रखने लायक अतिरिक्त छोटे क्षण बहुत अधिक नहीं थे।",
        "default_decision": ["आज कोई नया फैसला लेने से अधिक महत्व इस बात का था कि मौजूदा संदर्भ और प्राथमिकताओं को फिर से एक सीध में रखा जाए।"],
        "default_blocker": ["ऐसा कोई गंभीर अवरोध नहीं दिखा जिसने काम को पूरी तरह रोक दिया हो, लेकिन कुछ फॉलो-अप जांचें अभी भी बाकी रहीं।"],
        "default_next_action": ["आज पुनर्स्थापित किए गए संदर्भ को तुरंत किसी एक ठोस implementation या cleanup काम में बदलना"],
        "today_empty": "उपयोग करने लायक रिकॉर्ड बहुत अधिक नहीं थे, फिर भी स्क्रीन पर बचे Chronicle सारांशों के आधार पर आज का संदर्भ फिर से जोड़ा।",
        "connectors": ["शुरुआत में", "फिर", "बीच में", "उसके बाद", "अंत की ओर"],
        "diary_intro_empty": "आज का दिन स्क्रीन पर बचे निशानों को समेटकर काम की धारा को थोड़ा-सा व्यवस्थित करने जैसा था।",
        "diary_intro_with_subject": "आज का दिन काम की धारा को धीरे-धीरे फिर से पकड़ने जैसा लगा। शुरुआत {subject} को दोबारा देखने से हुई, और वही संदर्भ पूरे दिन साथ बना रहा।",
        "diary_intro_generic": "आज का दिन काम की धारा को धीरे-धीरे फिर से पकड़ने जैसा लगा। काफी समय उसी चल रही रेखा को फिर से हाथ में लेने में गया।",
        "diary_mood_dense": "ऐसा दिन जिसमें मैं कई स्क्रीन के बीच घूमता रहा लेकिन धागा टूटने नहीं देना चाहता था",
        "diary_mood_calm": "ऐसा दिन जिसमें काम की धारा को शांति से आगे बढ़ाया",
        "diary_body_timeline": "बीच-बीच में ऐप बदलता रहा और छोटे दस्तावेज भी देखे, इसलिए काम छोटे होने पर भी धारा बनी रही।",
        "diary_body_subject": "आज मैं सिर्फ एक जगह नहीं रुका, बल्कि {subject} पर भी नज़र बनाए रखी, और यह बात आज की नोट्स में साफ दिखाई दी।",
        "diary_body_activity": "आज मैं सिर्फ एक जगह नहीं रुका, बल्कि {activity} पर भी नज़र बनाए रखी, और यह बात आज की नोट्स में साफ दिखाई दी।",
        "diary_body_decision": "नई implementation को जोर से आगे बढ़ाने के बजाय, आज का दिन {decision} के आसपास दिशा को फिर से सीधा करने जैसा लगा।",
        "diary_body_fallback": "जब स्क्रीन पर बचे छोटे-छोटे निशान भी समेटकर देखे, तब लगा कि आज ध्यान का केंद्र मैंने शुरुआत में सोचा था उससे ज्यादा बार बदला।",
        "diary_close": "फिर भी {blocker} हल्के तौर पर बचा रहा। कल अगर {next_action} से शुरू करूं, तो दिन शायद थोड़ा साफ़ ढंग से आगे बढ़ेगा।",
        "diary_tail": "अगर इसे एक पंक्ति में लिखना हो, {reflection}",
        "reflection": {
            "multi_project": "एक ही implementation को धकेलने के बजाय, दिन का बड़ा हिस्सा कई प्रोजेक्ट और दस्तावेज़ों के बीच जाते हुए संदर्भ को वापस जोड़ने और विकल्पों की तुलना करने में गया।",
            "single_project": "सीधे implementation से अधिक, आज का दिन मौजूदा स्थिति को फिर से व्यवस्थित करने और अगला कदम चुनने में गया।",
            "research": "क्योंकि साथ-साथ दस्तावेज़ और संदर्भ सामग्री भी देखी, अगला फैसला लेने के लिए अब पर्याप्त आधार इकट्ठा हो गया है।",
            "blocker": "अगर बचे हुए सत्यापन बिंदु इसी तरह टलते रहे, तो अगला सत्र फिर से खोजबीन में बह सकता है; इसलिए अगले कदमों को और छोटे हिस्सों में बांटना बेहतर होगा।",
            "clear": "अब सबसे अच्छा यही होगा कि इस पुनर्स्थापित संदर्भ को तुरंत एक-दो ठोस implementation या cleanup कामों से जोड़ा जाए।",
        },
    },
}

LANGUAGE_CODE_BY_KEY = {
    "english": "en",
    "korean": "ko",
    "japanese": "ja",
    "chinese": "zh",
    "french": "fr",
    "german": "de",
    "spanish": "es",
    "vietnamese": "vi",
    "thai": "th",
    "russian": "ru",
    "hindi": "hi",
}

for language_key, language_code in LANGUAGE_CODE_BY_KEY.items():
    headings = heading_labels(language_code)
    OUTPUT_LANGUAGE_SPECS[language_key]["label"] = get_language_option(language_code).label
    OUTPUT_LANGUAGE_SPECS[language_key]["report_heading"] = headings["report"]
    OUTPUT_LANGUAGE_SPECS[language_key]["diary_heading"] = headings["diary"]
    OUTPUT_LANGUAGE_SPECS[language_key]["sections"] = {
        "today": f"### {headings['today']}",
        "timeline": f"### {headings['timeline']}",
        "decisions": f"### {headings['decisions']}",
        "blockers": f"### {headings['blockers']}",
        "tomorrow": f"### {headings['tomorrow']}",
        "reflection": f"### {headings['reflection']}",
    }

OUTPUT_LANGUAGE_ALIAS_MAP: dict[str, str] = {}
for key, spec in OUTPUT_LANGUAGE_SPECS.items():
    OUTPUT_LANGUAGE_ALIAS_MAP[key] = key
    OUTPUT_LANGUAGE_ALIAS_MAP[spec["label"].lower()] = key
    for alias in spec.get("aliases", ()):
        OUTPUT_LANGUAGE_ALIAS_MAP[alias.lower()] = key

REPORT_HEADING_VARIANTS = tuple(spec["report_heading"] for spec in OUTPUT_LANGUAGE_SPECS.values())
DIARY_HEADING_VARIANTS = tuple(spec["diary_heading"] for spec in OUTPUT_LANGUAGE_SPECS.values())
MARKDOWN_HEADING_ALIASES: dict[str, str] = {}
for spec in OUTPUT_LANGUAGE_SPECS.values():
    MARKDOWN_HEADING_ALIASES[spec["report_heading"]] = CANONICAL_REPORT_HEADING
    MARKDOWN_HEADING_ALIASES[spec["diary_heading"]] = CANONICAL_DIARY_HEADING
    for section_key, heading in spec.get("sections", {}).items():
        canonical = CANONICAL_SECTION_HEADINGS.get(section_key)
        if canonical:
            MARKDOWN_HEADING_ALIASES[heading] = canonical

PHRASE_PACKS: dict[str, dict[str, Any]] = {
    "english": {
        "activity": {
            "backend_migration": "reviewed the backend migration and configuration changes.",
            "workspace": "reviewed the page structure, tasks, and linked materials.",
            "docs": "checked documents and references to compare the needed grounding.",
            "planning": "tightened the MVP scope and the implementation direction.",
            "integration": "checked the integration and authentication flow.",
            "error": "looked through error signals and likely fix points.",
            "context": "recovered the current work context and organized the current state.",
            "generic": "carefully organized the work shown on screen.",
        },
        "decision": {
            "mvp": "reframed the direction around an MVP that still keeps backend, frontend, and delivery in view.",
            "fallback": "left a fallback path open in case the main integration stays blocked.",
            "integration": "made it clear that the API flow and verification order should be nailed down first.",
            "subject": "re-aligned the direction before starting the next concrete task.",
            "generic": "used the day to line up direction and priorities before pushing harder.",
        },
        "blocker": {
            "sqlite_test": "the SQLite-oriented test cleanup was still left to finish.",
            "error": "there were error signs that still needed verification in the real flow.",
            "auth": "an authentication check interrupted the flow for a moment.",
            "followup": "follow-up verification or cleanup was still unfinished.",
            "generic": "there were still a few loose ends to verify before calling it settled.",
        },
        "next_action": {
            "sqlite_test": "update the SQLite-oriented tests to match the current database flow",
            "integration": "verify the request shape and auth path against a real call",
            "workspace": "tighten the page structure around the real usage flow",
            "docs": "turn the confirmed document notes into a concrete implementation checklist",
            "subject": "narrow the follow-up around {subject} into a concrete execution item",
            "generic": "turn today's recovered context into one concrete implementation or cleanup step",
        },
        "timeline": {
            "update_modal": "checked the Codex update modal.",
            "context": "asked Codex to summarize the current work context.",
            "migration": "revisited the SQLite-to-MySQL migration context.",
            "tests": "noticed that SQLite-based test cleanup was still pending.",
            "workspace": "looked over the Notion workspace structure and planning pages.",
            "docs": "checked documentation or references for grounding.",
            "browser": "moved through browser-based AI tooling and related pages.",
            "integration": "looked through integration or authentication flow details.",
            "error": "noticed error signals or likely fix points.",
            "planning": "re-aligned the plan and MVP direction.",
            "subject": "continued reviewing the flow around {subject}.",
            "generic": "followed the visible work flow on screen.",
        },
    },
    "japanese": {
        "activity": {
            "backend_migration": "バックエンド移行と設定変更の流れを確認した。",
            "workspace": "ページ構成、タスク、資料の配置を見直した。",
            "docs": "必要な根拠を比べるために文書や参考資料を確認した。",
            "planning": "MVP の範囲と実装方針を整えた。",
            "integration": "連携方法と認証フローを確認した。",
            "error": "エラーの兆候と修正ポイントを見直した。",
            "context": "現在の作業文脈を復元し、状態を整理した。",
            "generic": "画面に出ていた作業の流れを丁寧に整理した。",
        },
        "decision": {
            "mvp": "バックエンド、フロント、デリバリーまで含めた MVP 基準で方向を整え直した。",
            "fallback": "主要連携が詰まった場合に備えて迂回経路も残しておいた。",
            "integration": "API 連携の流れと検証順序を先に固める必要があると整理した。",
            "subject": "次の具体的な作業に入る前に方向をもう一度そろえた。",
            "generic": "強く進めるより、方向と優先順位を先に合わせる日にした。",
        },
        "blocker": {
            "sqlite_test": "SQLite 前提のテスト整理がまだ残っていた。",
            "error": "実際の流れで確認が必要なエラーの兆候が残っていた。",
            "auth": "認証確認が入り、一度流れが切れた。",
            "followup": "後続の確認や整理がまだ終わっていなかった。",
            "generic": "落ち着く前に確認すべき細かい残りがまだあった。",
        },
        "next_action": {
            "sqlite_test": "SQLite 前提のテストを現在のデータベースフローに合わせて整理する",
            "integration": "実際の呼び出し基準でリクエスト形式と認証経路を検証する",
            "workspace": "実際の利用フローに合わせてページ構成を整える",
            "docs": "文書で確認した内容を実装チェックリストに固定する",
            "subject": "{subject} の後続作業を具体的な実行項目に絞る",
            "generic": "今日復元した文脈を一つの実装または整理作業にすぐつなげる",
        },
        "timeline": {
            "update_modal": "Codex のアップデート案内モーダルを確認した。",
            "context": "Codex に今の作業文脈を要約させた。",
            "migration": "SQLite から MySQL への移行文脈を見直した。",
            "tests": "SQLite 基準のテスト整理がまだ残っていると気づいた。",
            "workspace": "Notion ワークスペースの構成や企画ページを確認した。",
            "docs": "根拠のために文書や参考資料を確認した。",
            "browser": "ブラウザベースの AI ツールや関連ページを行き来した。",
            "integration": "連携や認証フローの詳細を確認した。",
            "error": "エラーの兆候や修正ポイントが見えた。",
            "planning": "計画と MVP の方向を整え直した。",
            "subject": "{subject} 周りの流れを続けて確認した。",
            "generic": "画面に見えていた作業の流れを追った。",
        },
    },
    "chinese": {
        "activity": {
            "backend_migration": "回看了后端迁移和配置变更的流程。",
            "workspace": "检查了页面结构、任务和资料摆放。",
            "docs": "查看了文档和参考资料来比较所需依据。",
            "planning": "收紧了 MVP 范围和实现方向。",
            "integration": "检查了集成方式和认证流程。",
            "error": "查看了错误迹象和可能的修复点。",
            "context": "重新恢复了当前工作语境并整理了状态。",
            "generic": "仔细整理了屏幕上出现的工作流程。",
        },
        "decision": {
            "mvp": "把方向重新对齐到仍然兼顾后端、前端和交付的 MVP 上。",
            "fallback": "为了防止主集成继续受阻，也把兜底路径一起保留了。",
            "integration": "明确了 API 流程和验证顺序需要先定下来。",
            "subject": "在开始下一个具体任务前先重新对齐了方向。",
            "generic": "今天更像是在先对齐方向和优先级，而不是继续猛推。",
        },
        "blocker": {
            "sqlite_test": "仍然有基于 SQLite 的测试整理没有完成。",
            "error": "还有一些错误迹象需要在真实流程里继续确认。",
            "auth": "认证检查打断了一次流程。",
            "followup": "后续验证或整理还没有收尾。",
            "generic": "在真正收住之前，还有一些零散项需要确认。",
        },
        "next_action": {
            "sqlite_test": "把基于 SQLite 的测试整理到符合当前数据库流程",
            "integration": "按真实调用去验证请求格式和认证路径",
            "workspace": "围绕真实使用流程继续收紧页面结构",
            "docs": "把文档里确认过的内容固化成实现清单",
            "subject": "把 {subject} 的后续工作收窄成一个具体执行项",
            "generic": "把今天恢复出来的语境立刻接到一个具体实现或整理动作上",
        },
        "timeline": {
            "update_modal": "查看了 Codex 更新提示弹窗。",
            "context": "让 Codex 总结当前工作语境。",
            "migration": "重新看了从 SQLite 到 MySQL 的迁移语境。",
            "tests": "注意到基于 SQLite 的测试整理还没结束。",
            "workspace": "查看了 Notion 工作区结构和规划页面。",
            "docs": "查看了文档或参考资料来补足依据。",
            "browser": "在浏览器里的 AI 工具和相关页面之间来回切换。",
            "integration": "查看了集成或认证流程细节。",
            "error": "看到了错误迹象或可能的修复点。",
            "planning": "重新对齐了计划和 MVP 方向。",
            "subject": "继续查看了与 {subject} 有关的流程。",
            "generic": "顺着屏幕上可见的工作流程往下看。",
        },
    },
    "french": {
        "activity": {
            "backend_migration": "a revu le flux de migration backend et les changements de configuration.",
            "workspace": "a relu la structure de la page, les taches et les ressources liees.",
            "docs": "a consulte la documentation et les references pour comparer les points d'appui utiles.",
            "planning": "a resserre le perimetre MVP et la direction d'implementation.",
            "integration": "a verifie le flux d'integration et d'authentification.",
            "error": "a relu les signaux d'erreur et les points de correction probables.",
            "context": "a retrouve le contexte de travail actuel et a remis l'etat au clair.",
            "generic": "a soigneusement remis en ordre le flux de travail visible a l'ecran.",
        },
        "decision": {
            "mvp": "a recadre la direction autour d'un MVP qui garde le backend, le frontend et la livraison en vue.",
            "fallback": "a garde une voie de secours ouverte au cas ou l'integration principale resterait bloquee.",
            "integration": "a clarifie qu'il fallait d'abord fixer le flux API et l'ordre de verification.",
            "subject": "a realigne la direction avant d'attaquer la tache suivante.",
            "generic": "a surtout servi a remettre la direction et les priorites d'equerre.",
        },
        "blocker": {
            "sqlite_test": "la remise a jour des tests orientes SQLite restait a terminer.",
            "error": "des signes d'erreur demandaient encore une verification dans le flux reel.",
            "auth": "une verification d'authentification a coupe le rythme un moment.",
            "followup": "la verification ou le rangement de suivi n'etait pas encore termine.",
            "generic": "quelques details restaient a verifier avant de pouvoir vraiment clore le sujet.",
        },
        "next_action": {
            "sqlite_test": "mettre a jour les tests orientes SQLite pour qu'ils suivent le flux de base de donnees actuel",
            "integration": "verifier le format de requete et le chemin d'authentification sur un appel reel",
            "workspace": "resserrer la structure de la page autour du vrai flux d'usage",
            "docs": "transformer les notes confirmees dans la documentation en checklist d'implementation",
            "subject": "resserrer la suite autour de {subject} en une action concrete",
            "generic": "transformer le contexte retrouve aujourd'hui en une etape concrete d'implementation ou de rangement",
        },
        "timeline": {
            "update_modal": "a verifie la fenetre de mise a jour de Codex.",
            "context": "a demande a Codex de resumer le contexte de travail actuel.",
            "migration": "a repasse sur le contexte de migration de SQLite vers MySQL.",
            "tests": "a remarque que le rangement des tests bases sur SQLite restait en attente.",
            "workspace": "a parcouru la structure du workspace Notion et les pages de planification.",
            "docs": "a consulte de la documentation ou des references pour s'ancrer.",
            "browser": "a circule dans des outils IA via le navigateur et des pages associees.",
            "integration": "a examine des details d'integration ou d'authentification.",
            "error": "a remarque des signaux d'erreur ou des points de correction probables.",
            "planning": "a realigne le plan et la direction MVP.",
            "subject": "a continue a revoir le flux autour de {subject}.",
            "generic": "a suivi le flux de travail visible a l'ecran.",
        },
    },
    "german": {
        "activity": {
            "backend_migration": "hat den Backend-Migrationsfluss und die Konfigurationsanderungen erneut gepruft.",
            "workspace": "hat Seitenstruktur, Aufgaben und verknupfte Materialien durchgesehen.",
            "docs": "hat Dokumentation und Referenzen gepruft, um die notigen Grundlagen zu vergleichen.",
            "planning": "hat MVP-Umfang und Implementierungsrichtung gestrafft.",
            "integration": "hat Integrations- und Authentifizierungsfluss gepruft.",
            "error": "hat Fehlersignale und wahrscheinliche Fix-Punkte durchgesehen.",
            "context": "hat den aktuellen Arbeitskontext wiederhergestellt und den Stand sortiert.",
            "generic": "hat den auf dem Bildschirm sichtbaren Arbeitsfluss sorgfaltig geordnet.",
        },
        "decision": {
            "mvp": "hat die Richtung an einem MVP neu ausgerichtet, das Backend, Frontend und Auslieferung weiter mitdenkt.",
            "fallback": "hat einen Ausweichpfad offen gehalten, falls die Hauptintegration blockiert bleibt.",
            "integration": "hat klargestellt, dass API-Fluss und Verifizierungsreihenfolge zuerst festgezogen werden mussen.",
            "subject": "hat die Richtung vor dem nachsten konkreten Schritt noch einmal ausgerichtet.",
            "generic": "hat den Tag eher genutzt, um Richtung und Prioritaten neu zu justieren.",
        },
        "blocker": {
            "sqlite_test": "die Bereinigung der SQLite-orientierten Tests war noch offen.",
            "error": "es gab Fehlersignale, die im realen Ablauf noch verifiziert werden mussten.",
            "auth": "eine Authentifizierungsprufung hat den Fluss kurz unterbrochen.",
            "followup": "Nachprufung oder Aufraumarbeit war noch nicht abgeschlossen.",
            "generic": "vor einem echten Abschluss blieben noch ein paar lose Enden zu verifizieren.",
        },
        "next_action": {
            "sqlite_test": "die SQLite-orientierten Tests an den aktuellen Datenbankfluss anpassen",
            "integration": "Request-Form und Auth-Pfad an einem echten Aufruf verifizieren",
            "workspace": "die Seitenstruktur enger an den realen Nutzungsfluss anpassen",
            "docs": "bestatigte Doku-Notizen in eine konkrete Implementierungs-Checkliste uberfuhren",
            "subject": "die Nacharbeit rund um {subject} auf einen konkreten Ausfuhrungsschritt zuschneiden",
            "generic": "den heute wiederhergestellten Kontext sofort in einen konkreten Implementierungs- oder Aufraumschritt uberfuhren",
        },
        "timeline": {
            "update_modal": "hat das Codex-Update-Modal gepruft.",
            "context": "hat Codex gebeten, den aktuellen Arbeitskontext zusammenzufassen.",
            "migration": "hat den Kontext der SQLite-zu-MySQL-Migration erneut angesehen.",
            "tests": "hat bemerkt, dass die SQLite-basierte Testbereinigung noch aussteht.",
            "workspace": "hat die Notion-Workspace-Struktur und Planungsseiten durchgesehen.",
            "docs": "hat Dokumentation oder Referenzen fur mehr Grundlage gepruft.",
            "browser": "hat sich durch browserbasierte KI-Tools und zugehorige Seiten bewegt.",
            "integration": "hat Integrations- oder Authentifizierungsdetails angesehen.",
            "error": "hat Fehlersignale oder wahrscheinliche Fix-Punkte wahrgenommen.",
            "planning": "hat Plan und MVP-Richtung neu ausgerichtet.",
            "subject": "hat den Fluss rund um {subject} weiter verfolgt.",
            "generic": "hat dem sichtbaren Arbeitsfluss auf dem Bildschirm gefolgt.",
        },
    },
    "spanish": {
        "activity": {
            "backend_migration": "reviso el flujo de migracion del backend y los cambios de configuracion.",
            "workspace": "reviso la estructura de la pagina, las tareas y los materiales enlazados.",
            "docs": "consulto documentos y referencias para comparar el contexto necesario.",
            "planning": "ajusto el alcance del MVP y la direccion de implementacion.",
            "integration": "reviso el flujo de integracion y autenticacion.",
            "error": "repaso senales de error y puntos probables de correccion.",
            "context": "recupero el contexto actual de trabajo y ordeno el estado.",
            "generic": "ordeno con cuidado el flujo de trabajo visible en pantalla.",
        },
        "decision": {
            "mvp": "reencuadro la direccion alrededor de un MVP que sigue manteniendo backend, frontend y entrega en la vista.",
            "fallback": "dejo abierta una ruta alternativa por si la integracion principal seguia bloqueada.",
            "integration": "dejo claro que primero habia que fijar el flujo de API y el orden de verificacion.",
            "subject": "volvio a alinear la direccion antes de entrar en la siguiente tarea concreta.",
            "generic": "uso el dia para volver a alinear direccion y prioridades antes de empujar mas fuerte.",
        },
        "blocker": {
            "sqlite_test": "la limpieza de pruebas orientadas a SQLite seguia pendiente.",
            "error": "quedaban senales de error que aun habia que verificar en el flujo real.",
            "auth": "una comprobacion de autenticacion corto el flujo por un momento.",
            "followup": "la verificacion o el orden posterior seguian sin cerrarse.",
            "generic": "antes de darlo por cerrado aun quedaban algunos cabos sueltos por verificar.",
        },
        "next_action": {
            "sqlite_test": "ajustar las pruebas orientadas a SQLite al flujo actual de base de datos",
            "integration": "verificar el formato de la peticion y la ruta de autenticacion en una llamada real",
            "workspace": "apretar la estructura de la pagina alrededor del flujo real de uso",
            "docs": "convertir las notas confirmadas en la documentacion en una checklist concreta de implementacion",
            "subject": "acotar el seguimiento alrededor de {subject} a una accion concreta",
            "generic": "convertir de inmediato el contexto recuperado hoy en un paso concreto de implementacion o limpieza",
        },
        "timeline": {
            "update_modal": "reviso el modal de actualizacion de Codex.",
            "context": "pidio a Codex que resumiera el contexto actual del trabajo.",
            "migration": "volvio a pasar por el contexto de migracion de SQLite a MySQL.",
            "tests": "noto que la limpieza de pruebas basadas en SQLite seguia pendiente.",
            "workspace": "reviso la estructura del workspace de Notion y las paginas de planificacion.",
            "docs": "consulto documentacion o referencias para afianzar el contexto.",
            "browser": "se movio por herramientas de IA en el navegador y paginas relacionadas.",
            "integration": "reviso detalles de integracion o autenticacion.",
            "error": "vio senales de error o puntos probables de correccion.",
            "planning": "volvio a alinear el plan y la direccion del MVP.",
            "subject": "siguio revisando el flujo alrededor de {subject}.",
            "generic": "siguio el flujo de trabajo visible en pantalla.",
        },
    },
    "vietnamese": {
        "activity": {
            "backend_migration": "da xem lai dong di cua viec migration backend va cac thay doi cau hinh.",
            "workspace": "da xem lai cau truc trang, cac viec can lam va tai lieu lien ket.",
            "docs": "da xem tai lieu va tham khao de doi chieu nen tang can thiet.",
            "planning": "da thu gon pham vi MVP va huong implement.",
            "integration": "da kiem tra luong tich hop va xac thuc.",
            "error": "da xem lai dau hieu loi va diem sua kha nang cao.",
            "context": "da phuc hoi boi canh cong viec hien tai va sap xep lai trang thai.",
            "generic": "da can than sap xep lai dong cong viec hien tren man hinh.",
        },
        "decision": {
            "mvp": "da can chinh huong di quanh mot MVP van giu backend, frontend va huong giao hang trong tam nhin.",
            "fallback": "da giu san mot lo trinh du phong neu tich hop chinh van bi nghen.",
            "integration": "da lam ro rang rang luong API va thu tu xac minh can duoc chot truoc.",
            "subject": "da can chinh lai huong di truoc khi vao tac vu cu the tiep theo.",
            "generic": "da dung ngay nay de can lai huong di va uu tien truoc khi day manh hon.",
        },
        "blocker": {
            "sqlite_test": "viec don dep test theo huong SQLite van con dang do.",
            "error": "van con dau hieu loi can xac minh trong luong thuc te.",
            "auth": "mot buoc kiem tra xac thuc da lam ngat dong chay trong choc lat.",
            "followup": "viec xac minh hoac don dep tiep theo van chua khop lai.",
            "generic": "truoc khi co the coi la xong van con vai dau moi can xac minh.",
        },
        "next_action": {
            "sqlite_test": "cap nhat cac bai test theo huong SQLite cho khop voi luong co so du lieu hien tai",
            "integration": "xac minh hinh dang request va duong xac thuc bang mot lan goi thuc",
            "workspace": "thu gon cau truc trang xoay quanh luong su dung thuc te",
            "docs": "bien cac ghi chu da xac nhan trong tai lieu thanh checklist implement cu the",
            "subject": "thu gon phan viec tiep theo quanh {subject} thanh mot muc hanh dong cu the",
            "generic": "bien boi canh da phuc hoi hom nay thanh mot buoc implement hoac don dep cu the ngay",
        },
        "timeline": {
            "update_modal": "da kiem tra modal cap nhat Codex.",
            "context": "da nhờ Codex tom tat boi canh cong viec hien tai.",
            "migration": "da xem lai boi canh migration tu SQLite sang MySQL.",
            "tests": "da thay rang viec don dep test dua tren SQLite van con treo.",
            "workspace": "da xem cau truc workspace Notion va cac trang lap ke hoach.",
            "docs": "da xem tai lieu hoac tham khao de bo sung nen tang.",
            "browser": "da di qua cac cong cu AI tren trinh duyet va cac trang lien quan.",
            "integration": "da xem chi tiet luong tich hop hoac xac thuc.",
            "error": "da thay dau hieu loi hoac diem sua kha nang cao.",
            "planning": "da can lai ke hoach va huong MVP.",
            "subject": "da tiep tuc xem luong cong viec quanh {subject}.",
            "generic": "da di theo dong cong viec dang hien tren man hinh.",
        },
    },
    "thai": {
        "activity": {
            "backend_migration": "ได้ทบทวนภาพรวมการย้าย backend และการเปลี่ยน config อีกครั้ง",
            "workspace": "ได้ดูโครงสร้างหน้า งานที่ค้าง และลิงก์ข้อมูลประกอบ",
            "docs": "ได้เปิดเอกสารและข้อมูลอ้างอิงเพื่อเทียบฐานข้อมูลที่ต้องใช้",
            "planning": "ได้กระชับขอบเขต MVP และทิศทางการ implement",
            "integration": "ได้ตรวจ flow การเชื่อมต่อและการยืนยันตัวตน",
            "error": "ได้ไล่ดูสัญญาณ error และจุดที่น่าจะแก้ต่อ",
            "context": "ได้กู้บริบทงานปัจจุบันกลับมาและจัดสถานะให้ชัดขึ้น",
            "generic": "ได้ค่อยๆ จัดระเบียบ flow งานที่มองเห็นบนหน้าจอ",
        },
        "decision": {
            "mvp": "ได้จัดทิศทางใหม่รอบ MVP ที่ยังมองทั้ง backend frontend และการส่งมอบไว้พร้อมกัน",
            "fallback": "ได้เผื่อทาง fallback ไว้ด้วย เผื่อ integration หลักยังติดอยู่",
            "integration": "ได้ทำให้ชัดว่าควรล็อก flow API และลำดับการตรวจสอบก่อน",
            "subject": "ได้ปรับทิศทางให้ตรงกันอีกครั้งก่อนเริ่มงานถัดไป",
            "generic": "วันนี้เหมือนใช้ไปกับการจัดทิศทางและลำดับความสำคัญให้ตรงกันมากกว่าเร่งต่อ",
        },
        "blocker": {
            "sqlite_test": "งานเก็บ test ที่ยังอิง SQLite ยังเหลืออยู่",
            "error": "ยังมีสัญญาณ error ที่ต้องกลับไปตรวจใน flow จริง",
            "auth": "มีจังหวะตรวจ auth เข้ามาคั่น flow อยู่ช่วงหนึ่ง",
            "followup": "งานตรวจหรืองานเก็บต่อยังไม่ปิดสนิท",
            "generic": "ก่อนจะถือว่าจบ ยังมีปลายงานเล็กๆ ที่ต้องตรวจอีกนิด",
        },
        "next_action": {
            "sqlite_test": "ปรับ test ที่อิง SQLite ให้ตรงกับ flow ฐานข้อมูลปัจจุบัน",
            "integration": "ตรวจรูปแบบ request และเส้นทาง auth กับการเรียกจริง",
            "workspace": "กระชับโครงสร้างหน้าให้ตรงกับ flow การใช้งานจริง",
            "docs": "ตรึงโน้ตจากเอกสารที่ยืนยันแล้วให้กลายเป็น checklist implement",
            "subject": "บีบงานต่อของ {subject} ให้เหลือ action ที่ลงมือได้ชัดเจนหนึ่งข้อ",
            "generic": "เปลี่ยนบริบทที่กู้ได้วันนี้ให้เป็นงาน implement หรือเก็บงานที่ทำต่อได้ทันทีหนึ่งข้อ",
        },
        "timeline": {
            "update_modal": "ได้เช็กหน้าต่างแจ้งอัปเดตของ Codex",
            "context": "ได้ให้ Codex ช่วยสรุปบริบทงานตอนนี้",
            "migration": "ได้ย้อนดูบริบทการย้ายจาก SQLite ไป MySQL",
            "tests": "สังเกตเห็นว่างานเก็บ test ที่อิง SQLite ยังไม่จบ",
            "workspace": "ได้ดูโครงสร้าง workspace ใน Notion และหน้าวางแผนต่างๆ",
            "docs": "ได้เปิดเอกสารหรือข้อมูลอ้างอิงเพื่อยึดพื้นฐานให้แน่นขึ้น",
            "browser": "ได้ไล่ดูเครื่องมือ AI บนเบราว์เซอร์และหน้าที่เกี่ยวข้อง",
            "integration": "ได้ดูรายละเอียดของ flow การเชื่อมต่อหรือ auth",
            "error": "เห็นสัญญาณ error หรือจุดที่น่าจะต้องแก้ต่อ",
            "planning": "ได้จัดแผนและทิศทาง MVP ให้ตรงกันอีกครั้ง",
            "subject": "ได้ตามดู flow รอบ {subject} ต่อ",
            "generic": "ได้ไล่ตาม flow งานที่เห็นอยู่บนหน้าจอ",
        },
    },
    "russian": {
        "activity": {
            "backend_migration": "пересмотрел ход миграции бэкенда и изменения конфигурации.",
            "workspace": "просмотрел структуру страницы, задачи и связанные материалы.",
            "docs": "проверил документацию и справочные материалы, чтобы сверить нужную опору.",
            "planning": "сузил рамки MVP и направление реализации.",
            "integration": "проверил поток интеграции и аутентификации.",
            "error": "просмотрел сигналы ошибок и вероятные точки исправления.",
            "context": "восстановил текущий рабочий контекст и привел состояние в порядок.",
            "generic": "аккуратно упорядочил рабочий поток, видимый на экране.",
        },
        "decision": {
            "mvp": "заново выровнял направление вокруг MVP, который все еще держит в поле зрения backend, frontend и доставку.",
            "fallback": "оставил открытым обходной путь на случай, если основная интеграция останется заблокированной.",
            "integration": "зафиксировал, что сначала нужно определить поток API и порядок проверки.",
            "subject": "перед следующим конкретным шагом еще раз выровнял направление.",
            "generic": "использовал день скорее для выравнивания направления и приоритетов, чем для резкого продвижения вперед.",
        },
        "blocker": {
            "sqlite_test": "очистка тестов, ориентированных на SQLite, все еще оставалась незавершенной.",
            "error": "оставались признаки ошибок, которые еще нужно проверить в реальном потоке.",
            "auth": "проверка аутентификации на время прервала ход работы.",
            "followup": "последующая проверка или доводка еще не была закрыта.",
            "generic": "до полного завершения еще оставалось несколько концов, которые нужно проверить.",
        },
        "next_action": {
            "sqlite_test": "привести тесты, ориентированные на SQLite, в соответствие с текущим потоком базы данных",
            "integration": "проверить форму запроса и путь аутентификации на реальном вызове",
            "workspace": "поджать структуру страницы вокруг реального пользовательского потока",
            "docs": "превратить подтвержденные заметки из документации в конкретный чек-лист реализации",
            "subject": "сузить дальнейшую работу по {subject} до одного конкретного шага",
            "generic": "сразу превратить восстановленный сегодня контекст в один конкретный шаг по реализации или наведению порядка",
        },
        "timeline": {
            "update_modal": "проверил модальное окно обновления Codex.",
            "context": "попросил Codex кратко восстановить текущий рабочий контекст.",
            "migration": "снова прошелся по контексту миграции с SQLite на MySQL.",
            "tests": "заметил, что cleanup тестов на SQLite все еще не завершен.",
            "workspace": "просмотрел структуру workspace в Notion и страницы планирования.",
            "docs": "проверил документацию или справочные материалы, чтобы укрепить опору.",
            "browser": "походил по браузерным AI-инструментам и связанным страницам.",
            "integration": "посмотрел детали интеграции или аутентификации.",
            "error": "заметил сигналы ошибок или вероятные точки исправления.",
            "planning": "снова выровнял план и направление MVP.",
            "subject": "продолжил смотреть поток вокруг {subject}.",
            "generic": "следовал за видимым рабочим потоком на экране.",
        },
    },
    "hindi": {
        "activity": {
            "backend_migration": "backend migration और configuration बदलावों की धारा को फिर से देखा।",
            "workspace": "page structure, tasks और linked materials को दोबारा देखा।",
            "docs": "ज़रूरी आधार की तुलना करने के लिए documents और references देखे।",
            "planning": "MVP scope और implementation direction को थोड़ा और कसकर तय किया।",
            "integration": "integration और authentication flow की जांच की।",
            "error": "error संकेतों और संभावित fix points को देखा।",
            "context": "मौजूदा work context को फिर से उठाया और state को व्यवस्थित किया।",
            "generic": "स्क्रीन पर दिख रहे काम के flow को ध्यान से व्यवस्थित किया।",
        },
        "decision": {
            "mvp": "दिशा को फिर से ऐसे MVP के आसपास जमाया जिसमें backend, frontend और delivery तीनों दिखते रहें।",
            "fallback": "मुख्य integration अटका रहे तो fallback path भी खुला रखा।",
            "integration": "यह साफ किया कि API flow और verification order पहले तय होना चाहिए।",
            "subject": "अगले concrete task से पहले दिशा को फिर से align किया।",
            "generic": "आज का जोर आगे धकेलने से ज्यादा direction और priorities को align करने पर रहा।",
        },
        "blocker": {
            "sqlite_test": "SQLite-आधारित tests की सफाई अभी बाकी थी।",
            "error": "कुछ error संकेत अभी भी real flow में verify करने बाकी थे।",
            "auth": "एक authentication check ने flow को थोड़ी देर रोका।",
            "followup": "follow-up verification या cleanup अभी पूरा नहीं हुआ था।",
            "generic": "पूरी तरह settle मानने से पहले कुछ ढीले सिरे अभी भी जांचने बाकी थे।",
        },
        "next_action": {
            "sqlite_test": "SQLite-आधारित tests को मौजूदा database flow के हिसाब से update करना",
            "integration": "request shape और auth path को real call के खिलाफ verify करना",
            "workspace": "page structure को real usage flow के आसपास और कसना",
            "docs": "documentation से confirm हुए notes को concrete implementation checklist में बदलना",
            "subject": "{subject} से जुड़ी अगली work item को एक concrete action तक सीमित करना",
            "generic": "आज recovered context को तुरंत किसी एक concrete implementation या cleanup step में बदलना",
        },
        "timeline": {
            "update_modal": "Codex update modal देखा।",
            "context": "Codex से मौजूदा work context का सार निकलवाया।",
            "migration": "SQLite से MySQL migration context को फिर से देखा।",
            "tests": "ध्यान गया कि SQLite-based test cleanup अभी भी pending है।",
            "workspace": "Notion workspace structure और planning pages देखे।",
            "docs": "आधार मजबूत करने के लिए docs या references देखे।",
            "browser": "browser-based AI tooling और related pages के बीच घूमता रहा।",
            "integration": "integration या auth flow के details देखे।",
            "error": "error संकेत या संभावित fix points दिखे।",
            "planning": "plan और MVP direction को फिर से align किया।",
            "subject": "{subject} के आसपास का flow देखना जारी रखा।",
            "generic": "स्क्रीन पर दिख रहे work flow का पीछा किया।",
        },
    },
}


def supported_output_languages() -> list[dict[str, str]]:
    return [
        {"value": key, "label": spec["label"]}
        for key, spec in OUTPUT_LANGUAGE_SPECS.items()
    ]


def normalize_output_language(
    value: str | None,
    *,
    default: str = DEFAULT_OUTPUT_LANGUAGE,
) -> str:
    if value is None:
    return default


def normalize_diary_length_code(
    value: str | None,
    *,
    default: str = DEFAULT_DIARY_LENGTH_CODE,
) -> str:
    return normalize_diary_length(value, default=default) or default


def diary_length_profile(length: str | None) -> dict[str, Any]:
    code = normalize_diary_length_code(length)
    return DIARY_LENGTH_PROFILES[code]


def raise_if_cancelled(should_cancel: Optional[CancellationCheck]) -> None:
    if should_cancel is not None and should_cancel():
        raise GenerationCancelledError("생성을 취소했어요.")
    normalized = str(value).strip().lower()
    if not normalized:
        return default
    resolved = OUTPUT_LANGUAGE_ALIAS_MAP.get(normalized)
    if not resolved:
        supported = ", ".join(spec["label"] for spec in OUTPUT_LANGUAGE_SPECS.values())
        raise ValueError(f"지원하지 않는 출력 언어입니다: {value}. 지원 언어: {supported}")
    return resolved


def output_language_label(output_language: str) -> str:
    language = normalize_output_language(output_language)
    return OUTPUT_LANGUAGE_SPECS[language]["label"]


def language_spec(output_language: str) -> dict[str, Any]:
    language = normalize_output_language(output_language)
    return OUTPUT_LANGUAGE_SPECS[language]


def phrase_pack(output_language: str) -> dict[str, Any]:
    language = normalize_output_language(output_language)
    if language == "korean":
        language = "english"
    return PHRASE_PACKS[language]


def detect_output_language_from_markdown(markdown: str) -> Optional[str]:
    lines = [line.strip() for line in markdown.splitlines() if line.strip()]
    for line in lines:
        for key, spec in OUTPUT_LANGUAGE_SPECS.items():
            if line == spec["report_heading"] or line == spec["diary_heading"]:
                return key
    return None


def normalize_for_similarity(text: str) -> str:
    lowered = text.lower()
    lowered = re.sub(r"`([^`]+)`", r"\1", lowered)
    lowered = re.sub(r"[^0-9a-zA-Z가-힣/._-]+", " ", lowered)
    return re.sub(r"\s+", " ", lowered).strip()


def token_set(text: str) -> set[str]:
    normalized = normalize_for_similarity(text)
    normalized = normalized.replace("documentation", "docs")
    tokens = set()
    for token in normalized.split():
        cleaned = token.strip("._-")
        if len(cleaned) > 2 and cleaned not in TEXT_STOPWORDS:
            tokens.add(cleaned)
    return tokens


def are_events_similar(left: Event, right: Event) -> bool:
    left_norm = normalize_for_similarity(left.text)
    right_norm = normalize_for_similarity(right.text)
    left_tokens = token_set(left_norm)
    right_tokens = token_set(right_norm)
    return are_events_similar_preprocessed(left_norm, left_tokens, right_norm, right_tokens)


def are_events_similar_preprocessed(
    left_norm: str,
    left_tokens: set[str],
    right_norm: str,
    right_tokens: set[str],
) -> bool:
    if not left_norm or not right_norm:
        return False
    if left_norm == right_norm:
        return True
    if left_norm in right_norm or right_norm in left_norm:
        return True
    if not left_tokens or not right_tokens:
        ratio = SequenceMatcher(None, left_norm, right_norm).ratio()
        return ratio >= 0.9
    intersection = len(left_tokens & right_tokens)
    if not intersection:
        return False
    overlap = intersection / len(left_tokens | right_tokens)
    coverage = intersection / min(len(left_tokens), len(right_tokens))
    if overlap >= 0.75 or coverage >= 0.66:
        return True
    if overlap <= 0.2 and coverage <= 0.34:
        return False
    if abs(len(left_norm) - len(right_norm)) > 48 and coverage < 0.5:
        return False
    ratio = SequenceMatcher(None, left_norm, right_norm).ratio()
    return ratio >= 0.9


def source_priority(source: ChronicleSource) -> int:
    return 2 if source.granularity == "10min" else 1


def similarity_signatures(normalized: str, tokens: set[str]) -> tuple[tuple[str, str], ...]:
    signatures: list[tuple[str, str]] = []
    if normalized:
        signatures.append(("exact", normalized))
        window = 28
        signatures.append(("prefix", normalized[:window]))
        signatures.append(("suffix", normalized[-window:]))
    ranked_tokens = sorted(tokens, key=lambda token: (-len(token), token))
    if ranked_tokens:
        signatures.append(("token", ranked_tokens[0]))
    if len(ranked_tokens) >= 2:
        signatures.append(("pair", "|".join(ranked_tokens[:2])))
    return tuple(dict.fromkeys(signatures))


def event_sort_key(event: Event) -> tuple[datetime, int, str]:
    return (
        event.source.recorded_at_local,
        event.order,
        event.source.path.as_posix(),
    )


def event_gap_minutes(left: Event, right: Event) -> float:
    delta = left.source.recorded_at_local - right.source.recorded_at_local
    return abs(delta.total_seconds()) / 60


def dedupe_window_minutes(left: Event, right: Event) -> int:
    if left.source.path == right.source.path:
        return DEDUPLICATION_WINDOW_WITH_6H_MINUTES
    if "6h" in {left.source.granularity, right.source.granularity}:
        return DEDUPLICATION_WINDOW_WITH_6H_MINUTES
    return DEDUPLICATION_WINDOW_MINUTES


def dedupe_events(events: Iterable[Event]) -> list[Event]:
    ordered = sorted(
        events,
        key=lambda event: (
            -source_priority(event.source),
            event.source.recorded_at_utc,
            event.order,
            -len(event.text),
        ),
    )
    unique: list[Event] = []
    unique_meta: list[tuple[str, set[str]]] = []
    buckets: dict[tuple[str, str], list[int]] = {}
    for candidate in ordered:
        normalized = normalize_for_similarity(candidate.text)
        tokens = token_set(normalized)
        candidate_indices: set[int] = set()
        for signature in similarity_signatures(normalized, tokens):
            candidate_indices.update(buckets.get(signature, ()))

        duplicate = any(
            event_gap_minutes(candidate, unique[index]) <= dedupe_window_minutes(candidate, unique[index])
            and are_events_similar_preprocessed(
                normalized,
                tokens,
                unique_meta[index][0],
                unique_meta[index][1],
            )
            for index in candidate_indices
        )
        if duplicate:
            continue
        for signature in similarity_signatures(normalized, tokens):
            buckets.setdefault(signature, []).append(len(unique))
        unique.append(candidate)
        unique_meta.append((normalized, tokens))
    return sorted(unique, key=event_sort_key)


def load_events(
    sources: Iterable[ChronicleSource],
    *,
    on_source_loaded: Optional[Callable[[ChronicleSource, int, int], None]] = None,
) -> list[Event]:
    ordered_sources = list(sources)
    events: list[Event] = []
    total = len(ordered_sources)
    for index, source in enumerate(ordered_sources, start=1):
        markdown = source.path.read_text(encoding="utf-8")
        events.extend(extract_events(source, markdown))
        if on_source_loaded is not None:
            on_source_loaded(source, index, total)
    return events


def source_bucket_key(source: ChronicleSource) -> int:
    minute_of_day = source.recorded_at_local.hour * 60 + source.recorded_at_local.minute
    return minute_of_day // PRIMARY_COVERAGE_BUCKET_MINUTES


def source_span_hours(sources: list[ChronicleSource]) -> float:
    if len(sources) < 2:
        return 0.0
    ordered = sorted(sources, key=lambda source: source.recorded_at_local)
    delta = ordered[-1].recorded_at_local - ordered[0].recorded_at_local
    return delta.total_seconds() / 3600


def has_sufficient_primary_coverage(sources: list[ChronicleSource], events: list[Event]) -> bool:
    if len(events) < MIN_PRIMARY_EVENTS or not sources:
        return False
    bucket_count = len({source_bucket_key(source) for source in sources})
    return bucket_count >= 3 or source_span_hours(sources) >= MIN_PRIMARY_SPAN_HOURS


def choose_events(
    sources: list[ChronicleSource],
    *,
    progress: Optional[ProgressCallback] = None,
    should_cancel: Optional[CancellationCheck] = None,
) -> tuple[list[Event], dict[str, int]]:
    ten_minute_sources, six_hour_sources = split_sources_by_granularity(sources)
    total_sources = len(sources)
    loaded_sources = 0

    def emit_collect_update(source: ChronicleSource, _: int, __: int) -> None:
        nonlocal loaded_sources
        loaded_sources += 1
        raise_if_cancelled(should_cancel)
        if progress is None:
            return
        ratio = loaded_sources / max(1, total_sources)
        progress(
            {
                "status": "running",
                "phase": "collect",
                "step_key": "loading.step.collect",
                "detail_key": "loading.detail.collect",
                "current": loaded_sources,
                "total": total_sources,
                "percent": min(36, 10 + round(ratio * 26)),
                "stats": {
                    "sources_total": total_sources,
                    "sources_10min": len(ten_minute_sources),
                    "sources_6h": len(six_hour_sources),
                    "last_granularity": source.granularity,
                },
            }
        )

    ten_minute_events = dedupe_events(
        load_events(ten_minute_sources, on_source_loaded=emit_collect_update)
    )

    stats = {
        "sources_total": len(sources),
        "sources_10min": len(ten_minute_sources),
        "sources_6h": len(six_hour_sources),
        "used_10min": len(ten_minute_sources),
        "used_6h": 0,
    }

    if progress is not None:
        progress(
            {
                "status": "running",
                "phase": "organize",
                "step_key": "loading.step.organize",
                "detail_key": "loading.detail.organize",
                "percent": 44,
                "stats": {**stats, "events_selected": len(ten_minute_events)},
            }
        )

    if ten_minute_events and (not six_hour_sources or has_sufficient_primary_coverage(ten_minute_sources, ten_minute_events)):
        return ten_minute_events, stats

    raise_if_cancelled(should_cancel)
    six_hour_events = dedupe_events(load_events(six_hour_sources, on_source_loaded=emit_collect_update))
    merged = dedupe_events([*ten_minute_events, *six_hour_events])
    used_six_hour = {event.source.path for event in merged if event.source.granularity == "6h"}
    stats["used_6h"] = len(used_six_hour)
    if progress is not None:
        progress(
            {
                "status": "running",
                "phase": "organize",
                "step_key": "loading.step.organize",
                "detail_key": "loading.detail.organize",
                "percent": 58,
                "stats": {**stats, "events_selected": len(merged)},
            }
        )
    return merged, stats


def choose_subject(event: Event) -> Optional[str]:
    for hint in SUBJECT_HINTS:
        if hint.lower() in event.text.lower():
            return hint
    for entity in event.entities:
        if entity in APP_STOPWORDS:
            continue
        if "." in entity and not entity.startswith("/"):
            continue
        if "/" in entity:
            continue
        if entity.startswith("GMT") or entity.startswith("UTC"):
            continue
        if len(entity.split()) > 4:
            continue
        if any(char.isdigit() for char in entity) and not re.search(r"[A-Za-z가-힣]", entity):
            continue
        if entity.isupper() and len(entity) > 4:
            continue
        return entity
    return None


def is_noise_event(event: Event) -> bool:
    text = event.text.lower()
    stripped = event.text.strip().strip("`")
    if len(stripped) <= 12:
        return True
    if len(event.entities) == 1 and stripped == event.entities[0]:
        return True
    noisy_prefixes = (
        "at the start of the window",
        "the visible prompt asked",
        "a later visible state showed",
        "one codex response explicitly summarized",
        "while codex remained open",
        "the user visited:",
        "the left sidebar showed",
        "the preview panel showed",
        "the user then viewed",
        "the user then moved to",
        "the overall behavior in this window",
    )
    if any(text.startswith(prefix) for prefix in noisy_prefixes):
        return True
    return False


def event_information_score(event: Event) -> int:
    text = event.text.lower()
    score = 0
    if len(event.text) > 60:
        score += 2
    elif len(event.text) > 30:
        score += 1
    if event.entities:
        score += min(2, len(event.entities))
    if any(tag in event.tags for tag in ("decision", "blocker", "next_action")):
        score += 2
    if any(
        keyword in text
        for keyword in (
            "mysql",
            "sqlite",
            "docker",
            "notion",
            "calendar",
            "todo",
            "kanana",
            "api",
            "auth",
            "chronicle",
            "mvp",
            "test",
            "error",
        )
    ):
        score += 2
    if is_noise_event(event):
        score -= 3
    return score


def korean_detail_phrase(event: Event) -> str:
    text = event.text.lower()
    if any(keyword in text for keyword in ("migration", "mysql", "sqlite", "docker", "database", "config", "dependency", "backend")):
        return "백엔드 마이그레이션과 설정 변경 흐름을 다시 확인했다."
    if any(keyword in text for keyword in ("notion", "todo", "calendar", "workspace", "cleanup", "materials section")):
        return "페이지 구조와 할 일, 자료 배치를 검토했다."
    if any(keyword in text for keyword in ("docs", "documentation", "reference", "reviewed", "visited", "scrolled", "browsing")):
        return "문서와 레퍼런스를 확인하면서 필요한 근거를 비교했다."
    if any(keyword in text for keyword in ("mvp", "plan", "planned", "proposed", "direction", "framed")):
        return "MVP 범위와 구현 방향을 정리했다."
    if any(keyword in text for keyword in ("api", "endpoint", "integration", "modalities", "streaming", "auth", "login")):
        return "연동 방식과 인증 흐름을 점검했다."
    if any(keyword in text for keyword in ("error", "warning", "fix")):
        return "오류 징후와 후속 수정 포인트를 확인했다."
    if any(keyword in text for keyword in ("summary", "context", "recovering", "describe current work")):
        return "작업 맥락을 다시 복구하고 현재 상태를 정리했다."
    return "화면에 나온 작업 흐름을 차분히 정리했다."


def to_korean_sentence(event: Event) -> str:
    subject = choose_subject(event)
    detail = korean_detail_phrase(event)
    if subject:
        return f"{subject}에서는 {detail}"
    return detail


def to_korean_decision(event: Event) -> str:
    text = event.text.lower()
    subject = choose_subject(event)
    if any(keyword in text for keyword in ("mvp", "proposed", "planned")):
        prefix = f"{subject}는 " if subject else ""
        return f"{prefix}백엔드, 프론트, 배포 흐름을 포함한 MVP 기준으로 다시 정리하는 쪽이 맞아 보였다.".strip()
    if "fallback" in text:
        prefix = f"{subject}는 " if subject else ""
        return f"{prefix}주요 연동이 막힐 경우를 대비한 우회 경로까지 같이 열어두는 판단이 중요했다.".strip()
    if any(keyword in text for keyword in ("api", "integration", "auth", "modalities", "streaming")):
        prefix = f"{subject}는 " if subject else ""
        return f"{prefix}API 연동 방향과 검증 순서를 먼저 분명히 해 두는 편이 좋았다.".strip()
    if subject:
        return f"{subject}는 다음 작업을 시작하기 전에 방향을 다시 맞춰 두는 쪽으로 정리됐다."
    return "새로운 구현을 밀어붙이기보다 방향과 우선순위를 먼저 정리하는 쪽으로 흐름이 잡혔다."


def to_korean_blocker(event: Event) -> str:
    text = event.text.lower()
    subject = choose_subject(event)
    if "test.sqlite" in text or all(keyword in text for keyword in ("test", "sqlite")):
        prefix = f"{subject}에서는 " if subject else ""
        return f"{prefix}아직 SQLite 기준 테스트 정리가 남아 있었다.".strip()
    if "error" in text:
        prefix = f"{subject}에서는 " if subject else ""
        return f"{prefix}실행 오류 징후가 보여 실제 수정 여부를 더 확인해야 했다.".strip()
    if any(keyword in text for keyword in ("auth", "login", "confirmation")):
        return "인증 확인 단계가 끼어 있어 흐름이 한 번 끊겼다."
    if any(keyword in text for keyword in ("follow-up", "still needing", "still appeared")):
        prefix = f"{subject}에서는 " if subject else ""
        return f"{prefix}후속 검증이나 정리가 아직 끝나지 않았다.".strip()
    return to_korean_sentence(event)


def to_korean_next_action(event: Event) -> str:
    text = event.text.lower()
    subject = choose_subject(event)
    if all(keyword in text for keyword in ("test", "sqlite")) or ("test.sqlite" in text):
        prefix = f"{subject}의 " if subject else ""
        return f"{prefix}SQLite 기준 테스트를 현재 데이터베이스 흐름에 맞게 정리하기"
    if any(keyword in text for keyword in ("api", "auth", "login", "modalities", "streaming")):
        prefix = f"{subject} " if subject else ""
        return f"{prefix}연동 요청 형식과 인증 경로를 실제 호출 기준으로 검증하기".strip()
    if any(keyword in text for keyword in ("notion", "todo", "calendar", "workspace")):
        prefix = f"{subject} " if subject else ""
        return f"{prefix}페이지 구조를 실제 사용 흐름에 맞게 다듬기".strip()
    if any(keyword in text for keyword in ("docs", "documentation", "reference")):
        return "문서에서 확인한 내용을 구현 체크리스트로 고정하기"
    if subject:
        return f"{subject} 관련 후속 작업을 구체적인 실행 항목으로 좁히기"
    return "확인한 맥락을 실제 구현 또는 정리 작업으로 이어가기"


def to_korean_timeline_phrase(event: Event) -> str:
    text = event.text.lower()
    subject = choose_subject(event)

    if "modal asked whether to update codex" in text:
        return "Codex 업데이트 안내 모달을 확인했다"
    if "describe what the user was working on" in text:
        return "Codex에 지금까지 하던 일을 요약해 달라고 요청한 흐름이 보였다"
    if "inspect local context" in text or ".codex/task.md" in text:
        return "Codex가 `.codex/TASK.md`와 작업 상태를 읽어 맥락을 정리하려고 했다"
    if "follow-up asking" in text and "codex knew" in text:
        return "방금 한 작업을 Codex가 얼마나 알고 있는지 다시 확인하려는 흐름이 있었다"
    if "visible task label" in text:
        return "현재 작업 라벨로 `Migrate ChargeCat database from SQLite to MYSQL`가 떠 있었다"
    if "migration framing" in text or all(keyword in text for keyword in ("sqlite", "mysql")):
        prefix = f"{subject} " if subject else ""
        return f"{prefix}백엔드가 SQLite에서 MySQL 쪽으로 옮겨가는 흐름을 다시 확인했다".strip()
    if "dependency/config changes" in text:
        return "의존성과 환경설정 변경 내용도 같이 훑어봤다"
    if "code files mentioned" in text:
        return "관련 코드 파일 이름들을 다시 확인했다"
    if "test.sqlite" in text or all(keyword in text for keyword in ("test", "sqlite")):
        return "테스트 쪽에 아직 SQLite 기준 정리가 남아 있다는 점이 보였다"
    if "file-change trail" in text:
        return "최근 변경 파일 목록을 타임라인처럼 다시 읽어봤다"
    if event.text.strip().startswith("`") and event.text.strip().endswith("`"):
        return f"{event.text.strip()} 같은 파일명도 작업 맥락으로 다시 확인했다"
    if "read `agents.md`" in text:
        return "`AGENTS.md`와 이전 작업 문맥을 바탕으로 현재 상태를 다시 읽는 흐름이 있었다"
    if "chrome was also visible" in text:
        return "Codex를 띄운 채 Chrome 탭도 함께 열어 두었다"
    if "developer documentation page about chronicle" in text or "chronicle page view" in text:
        return "Chrome에서 Chronicle 관련 문서를 짧게 읽었다"
    if "social-media" in text or "feed discussing recent ai model developments" in text:
        return "AI 모델 관련 피드도 잠깐 훑어봤다"
    if "switched into notion" in text:
        return "중간에 Notion으로 옮겨 갔다"
    if "mentor list database" in text:
        return "Notion에서 멘토 목록 데이터베이스 형태의 페이지를 확인했다"
    if "ai/sw maestro mentor list" in text:
        return "AI/SW maestro 멘토 목록 페이지 제목도 확인했다"
    if "workspace/page titled `triples`" in text:
        return "`TripleS` 메인 페이지로 이동했다"
    if "calendar occupied the top section" in text:
        return "페이지 상단 캘린더 배치를 봤다"
    if "todo" in text and "mentor-matching" in text:
        return "TODO 항목과 멘토 매칭 관련 할 일을 읽어봤다"
    if "scheduling section" in text or "scheduling link" in text:
        return "일정 구간과 스케줄링 링크도 같이 확인했다"
    if "materials section" in text:
        return "자료 링크와 하위 페이지 연결 상태를 살폈다"
    if "left sidebar showed related planning pages" in text:
        return "왼쪽 사이드바에 연결된 관련 기획 페이지들도 함께 보였다"
    if "chat titled `노션 페이지 개선`" in text:
        return "Codex의 `노션 페이지 개선` 대화로 다시 돌아왔다"
    if "looked clean" in text or "clutter" in text:
        return "Notion 페이지가 얼마나 깔끔한지 피드백 받으려는 흐름이 있었다"
    if "computer use mode" in text:
        return "Codex가 Computer Use로 페이지 정리 방향을 잡고 있었다"
    if "identified the page context" in text:
        return "Codex가 현재 열린 Notion 페이지 문맥을 파악한 상태였다"
    if "viewed the `triples` page directly" in text:
        return "`TripleS` 페이지를 다시 직접 열어 구조를 훑어봤다"
    if "final frames stayed on that page" in text:
        return "마지막까지 그 페이지를 띄운 채 배치를 검토했다"
    if any(keyword in text for keyword in ("app builder", "google ai studio")):
        return "브라우저 기반 AI 앱 빌더 화면도 같이 오가며 봤다"
    if any(keyword in text for keyword in ("kanana", "api", "auth", "login", "streaming")):
        return "연동 방식이나 인증 관련 화면도 확인했다"
    if any(keyword in text for keyword in ("error", "warning", "fix")):
        return "실행 오류나 수정 포인트도 눈에 들어왔다"
    if any(keyword in text for keyword in ("plan", "planned", "mvp", "proposed", "direction")):
        return "구현 계획과 MVP 방향을 다시 정리하는 흐름이 있었다"
    if any(keyword in text for keyword in ("docs", "documentation", "reference", "reviewed", "visited", "scrolled")):
        return "문서나 레퍼런스를 확인했다"
    if subject:
        return f"{subject} 관련 화면 흐름을 이어서 확인했다"
    return "화면에 보인 자잘한 흐름도 그대로 따라갔다"


def unique_sentences(sentences: Iterable[str]) -> list[str]:
    results: list[str] = []
    result_meta: list[tuple[str, set[str]]] = []
    buckets: dict[tuple[str, str], list[int]] = {}
    for sentence in sentences:
        normalized = normalize_for_similarity(sentence)
        if not normalized:
            continue
        tokens = token_set(normalized)
        candidate_indices: set[int] = set()
        for signature in similarity_signatures(normalized, tokens):
            candidate_indices.update(buckets.get(signature, ()))
        duplicate = any(
            are_events_similar_preprocessed(
                normalized,
                tokens,
                result_meta[index][0],
                result_meta[index][1],
            )
            for index in candidate_indices
        )
        if duplicate:
            continue
        for signature in similarity_signatures(normalized, tokens):
            buckets.setdefault(signature, []).append(len(results))
        results.append(sentence)
        result_meta.append((normalized, tokens))
    return results


def select_representative_events(events: list[Event], *, limit: int, required_tag: Optional[str] = None) -> list[Event]:
    filtered = []
    for event in events:
        if required_tag and required_tag not in event.tags:
            continue
        if required_tag is None and is_noise_event(event):
            continue
        filtered.append(event)

    ranked = sorted(
        filtered,
        key=lambda event: (
            -event_information_score(event),
            event.source.recorded_at_local,
            event.order,
        ),
    )
    selected: list[Event] = []
    subject_counts: Counter[str] = Counter()
    section_counts: Counter[str] = Counter()
    for event in ranked:
        subject = choose_subject(event) or event.section_title
        if subject_counts[subject] >= 2:
            continue
        if section_counts[event.section_title] >= 2:
            continue
        selected.append(event)
        subject_counts[subject] += 1
        section_counts[event.section_title] += 1
        if len(selected) >= limit:
            break
    return sorted(selected, key=lambda event: (event.source.recorded_at_local, event.order))


def classify_activity_key(event: Event) -> str:
    text = event.text.lower()
    if any(
        keyword in text
        for keyword in ("migration", "mysql", "sqlite", "docker", "database", "config", "dependency", "backend")
    ):
        return "backend_migration"
    if any(keyword in text for keyword in ("notion", "todo", "calendar", "workspace", "cleanup", "materials section")):
        return "workspace"
    if any(keyword in text for keyword in ("docs", "documentation", "reference", "reviewed", "visited", "browsing")):
        return "docs"
    if any(keyword in text for keyword in ("mvp", "plan", "planned", "proposed", "direction", "framed")):
        return "planning"
    if any(keyword in text for keyword in ("api", "endpoint", "integration", "modalities", "streaming", "auth", "login")):
        return "integration"
    if any(keyword in text for keyword in ("error", "warning", "fix")):
        return "error"
    if any(keyword in text for keyword in ("summary", "context", "recovering", "describe current work")):
        return "context"
    return "generic"


def classify_decision_key(event: Event) -> str:
    text = event.text.lower()
    if any(keyword in text for keyword in ("mvp", "proposed", "planned")):
        return "mvp"
    if "fallback" in text:
        return "fallback"
    if any(keyword in text for keyword in ("api", "integration", "auth", "modalities", "streaming")):
        return "integration"
    return "subject" if choose_subject(event) else "generic"


def classify_blocker_key(event: Event) -> str:
    text = event.text.lower()
    if "test.sqlite" in text or all(keyword in text for keyword in ("test", "sqlite")):
        return "sqlite_test"
    if "error" in text:
        return "error"
    if any(keyword in text for keyword in ("auth", "login", "confirmation")):
        return "auth"
    if any(keyword in text for keyword in ("follow-up", "still needing", "still appeared")):
        return "followup"
    return "generic"


def classify_next_action_key(event: Event) -> str:
    text = event.text.lower()
    if all(keyword in text for keyword in ("test", "sqlite")) or ("test.sqlite" in text):
        return "sqlite_test"
    if any(keyword in text for keyword in ("api", "auth", "login", "modalities", "streaming")):
        return "integration"
    if any(keyword in text for keyword in ("notion", "todo", "calendar", "workspace")):
        return "workspace"
    if any(keyword in text for keyword in ("docs", "documentation", "reference")):
        return "docs"
    return "subject" if choose_subject(event) else "generic"


def classify_timeline_key(event: Event) -> str:
    text = event.text.lower()
    if "modal asked whether to update codex" in text:
        return "update_modal"
    if any(keyword in text for keyword in ("describe what the user was working on", "inspect local context", ".codex/task.md")):
        return "context"
    if "migration framing" in text or all(keyword in text for keyword in ("sqlite", "mysql")):
        return "migration"
    if "test.sqlite" in text or all(keyword in text for keyword in ("test", "sqlite")):
        return "tests"
    if any(keyword in text for keyword in ("notion", "mentor", "triples", "calendar", "todo", "materials section")):
        return "workspace"
    if any(keyword in text for keyword in ("docs", "documentation", "reference", "reviewed", "visited", "scrolled")):
        return "docs"
    if any(keyword in text for keyword in ("app builder", "google ai studio", "social-media", "feed discussing recent ai model developments")):
        return "browser"
    if any(keyword in text for keyword in ("kanana", "api", "auth", "login", "streaming")):
        return "integration"
    if any(keyword in text for keyword in ("error", "warning", "fix")):
        return "error"
    if any(keyword in text for keyword in ("plan", "planned", "mvp", "proposed", "direction")):
        return "planning"
    return "subject" if choose_subject(event) else "generic"


def prefix_subject(subject: Optional[str], phrase: str) -> str:
    if subject:
        return f"{subject}: {phrase}"
    return phrase[:1].upper() + phrase[1:] if phrase else phrase


def to_localized_sentence(event: Event, output_language: str) -> str:
    if normalize_output_language(output_language, default=COMPATIBILITY_FALLBACK_LANGUAGE) == "korean":
        return to_korean_sentence(event)
    pack = phrase_pack(output_language)
    return prefix_subject(choose_subject(event), pack["activity"][classify_activity_key(event)])


def to_localized_decision(event: Event, output_language: str) -> str:
    if normalize_output_language(output_language, default=COMPATIBILITY_FALLBACK_LANGUAGE) == "korean":
        return to_korean_decision(event)
    pack = phrase_pack(output_language)
    key = classify_decision_key(event)
    phrase = pack["decision"][key]
    return prefix_subject(choose_subject(event) if key == "subject" else None, phrase)


def to_localized_blocker(event: Event, output_language: str) -> str:
    if normalize_output_language(output_language, default=COMPATIBILITY_FALLBACK_LANGUAGE) == "korean":
        return to_korean_blocker(event)
    pack = phrase_pack(output_language)
    key = classify_blocker_key(event)
    phrase = pack["blocker"][key]
    return prefix_subject(choose_subject(event) if key in {"sqlite_test", "error", "followup", "generic"} else None, phrase)


def to_localized_next_action(event: Event, output_language: str) -> str:
    if normalize_output_language(output_language, default=COMPATIBILITY_FALLBACK_LANGUAGE) == "korean":
        return to_korean_next_action(event)
    pack = phrase_pack(output_language)
    key = classify_next_action_key(event)
    phrase = pack["next_action"][key]
    if "{subject}" in phrase:
        phrase = phrase.format(subject=choose_subject(event) or event.section_title)
    return phrase


def to_localized_timeline_phrase(event: Event, output_language: str) -> str:
    if normalize_output_language(output_language, default=COMPATIBILITY_FALLBACK_LANGUAGE) == "korean":
        return to_korean_timeline_phrase(event)
    pack = phrase_pack(output_language)
    phrase = pack["timeline"][classify_timeline_key(event)]
    if "{subject}" in phrase:
        phrase = phrase.format(subject=choose_subject(event) or event.section_title)
    return phrase


def build_minor_timeline(
    events: list[Event],
    output_language: str = COMPATIBILITY_FALLBACK_LANGUAGE,
    diary_length: str = DEFAULT_DIARY_LENGTH_CODE,
) -> list[str]:
    profile = diary_length_profile(diary_length)
    timeline = []
    for event in events:
        phrase = to_localized_timeline_phrase(event, output_language).strip()
        if not phrase:
            continue
        prefix = event.source.recorded_at_local.strftime("%H:%M")
        timeline.append(f"[{prefix}] {phrase}")
    return unique_sentences(timeline)[: profile["timeline_limit"]]


def extract_lists(
    events: list[Event],
    output_language: str = COMPATIBILITY_FALLBACK_LANGUAGE,
    diary_length: str = DEFAULT_DIARY_LENGTH_CODE,
) -> tuple[list[str], list[str], list[str], list[str]]:
    language = normalize_output_language(output_language, default=COMPATIBILITY_FALLBACK_LANGUAGE)
    profile = diary_length_profile(diary_length)
    activities = unique_sentences(
        to_localized_sentence(event, language)
        for event in select_representative_events(events, limit=profile["activity_limit"])
    )
    decisions = unique_sentences(
        to_localized_decision(event, language)
        for event in select_representative_events(events, limit=profile["decision_limit"], required_tag="decision")
    )
    blockers = unique_sentences(
        to_localized_blocker(event, language)
        for event in select_representative_events(events, limit=profile["blocker_limit"], required_tag="blocker")
    )
    next_actions = unique_sentences(
        to_localized_next_action(event, language)
        for event in select_representative_events(events, limit=profile["next_action_limit"], required_tag="next_action")
    )
    if not next_actions:
        next_actions = unique_sentences(
            to_localized_next_action(event, language)
            for event in select_representative_events(events, limit=profile["next_action_limit"], required_tag="blocker")
        )

    if language == "korean":
        if not decisions and events:
            decisions = ["새로운 결정보다도 현재 작업 맥락과 우선순위를 다시 맞추는 데 의미가 있었던 날이었다."]
        if not blockers:
            blockers = ["당장 작업이 멈출 정도의 치명적인 장애는 보이지 않았지만, 후속 검증이 남아 있는 항목은 있었다."]
        if not next_actions:
            next_actions = ["오늘 확인한 맥락을 기준으로 가장 가까운 구현 또는 정리 작업 하나를 먼저 확정하기"]
    else:
        spec = language_spec(language)
        if not decisions and events:
            decisions = list(spec["default_decision"])
        if not blockers:
            blockers = list(spec["default_blocker"])
        if not next_actions:
            next_actions = list(spec["default_next_action"])
    return (
        activities[: profile["activity_limit"]],
        decisions[: profile["decision_limit"]],
        blockers[: profile["blocker_limit"]],
        next_actions[: profile["next_action_limit"]],
    )


def format_today_section(
    activities: list[str],
    output_language: str = COMPATIBILITY_FALLBACK_LANGUAGE,
) -> str:
    language = normalize_output_language(output_language, default=COMPATIBILITY_FALLBACK_LANGUAGE)
    if language == "korean":
        if not activities:
            return "기록이 많지 않아 세부 흐름은 제한적이었지만, 화면에 남은 Chronicle 요약을 바탕으로 오늘의 작업 맥락을 다시 정리했다."
        connectors = ["초반에는", "이어서", "중간에는", "마지막으로", "끝무렵에는"]
        sentences = []
        for index, activity in enumerate(activities):
            prefix = connectors[index] if index < len(connectors) else "또"
            trimmed = activity[:-1] if activity.endswith(".") else activity
            sentences.append(f"{prefix} {trimmed}.")
        return " ".join(sentences)

    spec = language_spec(language)
    if not activities:
        return spec["today_empty"]
    connectors = spec["connectors"]
    sentences = []
    for index, activity in enumerate(activities):
        prefix = connectors[index] if index < len(connectors) else connectors[-1]
        sentences.append(f"{prefix} {activity}")
    return " ".join(sentences)


def format_bullets(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


def format_report_section(
    *,
    activities: list[str],
    timeline: list[str],
    decisions: list[str],
    blockers: list[str],
    next_actions: list[str],
    reflection: str,
    output_language: str = COMPATIBILITY_FALLBACK_LANGUAGE,
) -> str:
    language = normalize_output_language(output_language, default=COMPATIBILITY_FALLBACK_LANGUAGE)
    if language == "korean":
        return "\n".join(
            [
                "## 금일 작업 보고서",
                "",
                "### 오늘 한 일",
                format_today_section(activities, language),
                "",
                "### 사소한 흐름까지 포함한 시간순 메모",
                format_bullets(timeline) if timeline else "- 세세한 흐름으로 남길 만한 추가 메모는 많지 않았다.",
                "",
                "### 중요하게 확인하거나 결정한 것",
                format_bullets(decisions),
                "",
                "### 막혔던 점 또는 미해결 이슈",
                format_bullets(blockers),
                "",
                "### 내일 할 일",
                format_bullets(next_actions),
                "",
                "### 짧은 회고",
                reflection,
                "",
            ]
        )

    spec = language_spec(language)
    sections = spec["sections"]
    return "\n".join(
        [
            spec["report_heading"],
            "",
            sections["today"],
            format_today_section(activities, language),
            "",
            sections["timeline"],
            format_bullets(timeline) if timeline else spec["timeline_empty"],
            "",
            sections["decisions"],
            format_bullets(decisions),
            "",
            sections["blockers"],
            format_bullets(blockers),
            "",
            sections["tomorrow"],
            format_bullets(next_actions),
            "",
            sections["reflection"],
            reflection,
            "",
        ]
    )


def soften_activity_for_diary(text: str) -> str:
    cleaned = text.strip().rstrip(".")
    return cleaned.replace("에서는 ", " 쪽에서 ")


def extract_activity_subject(text: str) -> Optional[str]:
    cleaned = text.strip().rstrip(".")
    if "에서는 " in cleaned:
        return cleaned.split("에서는 ", 1)[0]
    if " 쪽에서 " in cleaned:
        return cleaned.split(" 쪽에서 ", 1)[0]
    return None


def extract_activity_subject_localized(text: str) -> Optional[str]:
    cleaned = text.strip().rstrip(".。")
    if ":" not in cleaned:
        return None
    subject, _, remainder = cleaned.partition(":")
    if not subject.strip() or not remainder.strip():
        return None
    return subject.strip()


def build_diary_intro(activities: list[str], timeline: list[str]) -> str:
    if not activities:
        return "오늘은 화면에 남은 기록을 다시 모아 보면서, 작게라도 흐름을 정리해 둔 하루였다."

    mood = "이것저것 화면을 오가며 맥락을 붙잡아 둔 날" if len(timeline) >= 8 else "작업 흐름을 차분히 이어 간 날"
    first_subject = extract_activity_subject(activities[0])
    if first_subject:
        return f"오늘은 {mood}이었다. 시작은 {first_subject} 쪽 흐름을 다시 확인하는 데서 잡혔고, 그 흐름이 하루 전체를 천천히 이어 준 느낌이었다."
    return f"오늘은 {mood}이었다. 시작부터 지금 하고 있는 흐름을 다시 붙잡아 두는 데 시간을 쓴 편이었다."


def build_diary_body(activities: list[str], timeline: list[str], decisions: list[str]) -> str:
    snippets = []
    if timeline:
        snippets.append("중간중간 앱을 옮겨 다니고 문서도 짧게 확인하면서, 큰 작업만 한 건 아니어도 흐름을 계속 이어 가려고 했다.")
    if len(activities) >= 2:
        second_subject = extract_activity_subject(activities[1])
        if second_subject:
            snippets.append(f"한 가지에만 머물기보다 {second_subject} 쪽 흐름까지 같이 챙긴 점이 오늘 기록에 꽤 또렷하게 남았다.")
        else:
            second = soften_activity_for_diary(activities[1])
            snippets.append(f"한 가지에만 머물기보다 {second} 흐름까지 같이 챙긴 점이 오늘 기록에 꽤 또렷하게 남았다.")
    if decisions:
        first_decision = decisions[0].strip().rstrip(".")
        snippets.append(f"무언가를 확 세게 밀었다기보다는, {first_decision} 정도로 방향을 다시 다잡은 하루에 가까웠다.")
    if not snippets:
        snippets.append("화면에 찍힌 자잘한 흔적까지 모아 보니, 생각보다 손을 자주 옮겨 가며 하루를 보낸 편이었다.")
    return " ".join(snippets)


def build_diary_close(blockers: list[str], next_actions: list[str]) -> str:
    blocker_line = (
        blockers[0].strip().rstrip(".")
        if blockers
        else "크게 막히는 일은 없었지만 마무리할 조각은 조금 남아 있었다"
    )
    next_line = (
        next_actions[0].strip().rstrip(".")
        if next_actions
        else "내일은 오늘 모은 맥락을 작은 실행 항목으로 바로 옮기면 좋겠다"
    )
    return (
        f"다만 {blocker_line} 부분은 가볍게 남아 있었다. "
        f"내일은 {next_line} 정도부터 붙잡으면 하루가 좀 더 산뜻하게 굴러갈 것 같다."
    )


def build_diary_tail(reflection: str) -> str:
    softened = reflection.replace("비중이 컸다", "느낌이 있었다").replace("효율적이다", "좋아 보인다")
    return f"한 줄로 적어 두면, {softened}"


def build_localized_diary_intro(activities: list[str], timeline: list[str], output_language: str) -> str:
    spec = language_spec(output_language)
    if not activities:
        return spec["diary_intro_empty"]
    mood = spec["diary_mood_dense"] if len(timeline) >= 8 else spec["diary_mood_calm"]
    first_subject = extract_activity_subject_localized(activities[0])
    if first_subject:
        return spec["diary_intro_with_subject"].format(subject=first_subject, mood=mood)
    return spec["diary_intro_generic"].format(mood=mood)


def build_localized_diary_body(
    activities: list[str],
    timeline: list[str],
    decisions: list[str],
    output_language: str,
) -> str:
    spec = language_spec(output_language)
    snippets = []
    if timeline:
        snippets.append(spec["diary_body_timeline"])
    if len(activities) >= 2:
        second_subject = extract_activity_subject_localized(activities[1])
        if second_subject:
            snippets.append(spec["diary_body_subject"].format(subject=second_subject))
        else:
            snippets.append(spec["diary_body_activity"].format(activity=activities[1].strip().rstrip(".。")))
    if decisions:
        snippets.append(spec["diary_body_decision"].format(decision=decisions[0].strip().rstrip(".。")))
    if not snippets:
        snippets.append(spec["diary_body_fallback"])
    return " ".join(snippets)


def build_localized_diary_close(blockers: list[str], next_actions: list[str], output_language: str) -> str:
    spec = language_spec(output_language)
    blocker_line = blockers[0].strip().rstrip(".。") if blockers else spec["default_blocker"][0].rstrip(".。")
    next_line = next_actions[0].strip().rstrip(".。") if next_actions else spec["default_next_action"][0].rstrip(".。")
    return spec["diary_close"].format(blocker=blocker_line, next_action=next_line)


def build_localized_diary_tail(reflection: str, output_language: str) -> str:
    spec = language_spec(output_language)
    return spec["diary_tail"].format(reflection=reflection)


def format_diary_section(
    *,
    activities: list[str],
    timeline: list[str],
    decisions: list[str],
    blockers: list[str],
    next_actions: list[str],
    reflection: str,
    output_language: str = COMPATIBILITY_FALLBACK_LANGUAGE,
) -> str:
    language = normalize_output_language(output_language, default=COMPATIBILITY_FALLBACK_LANGUAGE)
    if language == "korean":
        return "\n".join(
            [
                "## 오늘의 일기 버전",
                "",
                build_diary_intro(activities, timeline),
                "",
                build_diary_body(activities, timeline, decisions),
                "",
                build_diary_close(blockers, next_actions),
                "",
                build_diary_tail(reflection),
                "",
            ]
        )

    spec = language_spec(language)
    return "\n".join(
        [
            spec["diary_heading"],
            "",
            build_localized_diary_intro(activities, timeline, language),
            "",
            build_localized_diary_body(activities, timeline, decisions, language),
            "",
            build_localized_diary_close(blockers, next_actions, language),
            "",
            build_localized_diary_tail(reflection, language),
            "",
        ]
    )


def build_reflection(
    events: list[Event],
    activities: list[str],
    blockers: list[str],
    output_language: str = COMPATIBILITY_FALLBACK_LANGUAGE,
) -> str:
    language = normalize_output_language(output_language, default=COMPATIBILITY_FALLBACK_LANGUAGE)
    projects = Counter(subject for event in events if (subject := choose_subject(event)))
    multi_project = len(projects) >= 2
    research_heavy = sum(1 for event in events if "research" in event.tags) >= max(2, len(events) // 3)
    if language == "korean":
        blocker_heavy = blockers and "치명적인 장애" not in blockers[0]
    else:
        default_blocker = language_spec(language)["default_blocker"][0]
        blocker_heavy = bool(blockers and blockers[0] != default_blocker)

    parts = []
    if language == "korean":
        if multi_project:
            parts.append("한 가지 구현만 밀기보다 여러 프로젝트와 문서를 오가며 맥락을 복구하고 비교 검토하는 비중이 컸다.")
        else:
            parts.append("직접 구현보다 현재 상태를 다시 정리하고 다음 수를 고르는 데 시간을 쓴 흐름이 보였다.")
        if research_heavy:
            parts.append("문서와 레퍼런스를 함께 확인한 덕분에 바로 착수하기 전에 필요한 판단 근거는 어느 정도 모였다.")
        if blocker_heavy:
            parts.append("다만 남은 검증 항목을 미루면 다음 작업이 다시 탐색 위주로 흐를 수 있어, 후속 실행 항목을 더 작게 쪼개는 편이 좋아 보인다.")
        else:
            parts.append("이제는 정리한 맥락을 실제 구현이나 정리 작업 한두 개로 바로 연결하는 게 효율적이다.")
        return " ".join(parts)

    reflection_pack = language_spec(language)["reflection"]
    parts.append(reflection_pack["multi_project"] if multi_project else reflection_pack["single_project"])
    if research_heavy:
        parts.append(reflection_pack["research"])
    parts.append(reflection_pack["blocker"] if blocker_heavy else reflection_pack["clear"])
    return " ".join(parts)


def evenly_spaced_indices(total: int, limit: int) -> list[int]:
    if total <= 0 or limit <= 0:
        return []
    if limit >= total:
        return list(range(total))
    if limit == 1:
        return [0]

    last_index = total - 1
    step = last_index / (limit - 1)
    indices: list[int] = []
    seen: set[int] = set()

    for offset in range(limit):
        index = round(offset * step)
        if index in seen:
            continue
        indices.append(index)
        seen.add(index)

    if len(indices) < limit:
        for index in range(total):
            if index in seen:
                continue
            indices.append(index)
            seen.add(index)
            if len(indices) >= limit:
                break

    return sorted(indices)


def group_events_by_source(events: list[Event]) -> list[list[Event]]:
    ordered = sorted(events, key=event_sort_key)
    groups: list[list[Event]] = []
    current_group: list[Event] = []
    current_path: Optional[Path] = None

    for event in ordered:
        if current_path != event.source.path:
            if current_group:
                groups.append(current_group)
            current_group = [event]
            current_path = event.source.path
            continue
        current_group.append(event)

    if current_group:
        groups.append(current_group)

    return groups


def select_priority_prompt_events(events: list[Event], *, max_events: int) -> list[Event]:
    if max_events <= 0 or not events:
        return []

    selected: list[Event] = []
    seen: set[Event] = set()

    def add(event: Event) -> None:
        if event in seen or len(selected) >= max_events:
            return
        selected.append(event)
        seen.add(event)

    add(events[0])
    add(events[-1])

    for tag in PROMPT_PRIORITY_TAGS:
        tagged = [event for event in events if tag in event.tags and event not in seen]
        tagged.sort(
            key=lambda event: (
                -event_information_score(event),
                event.source.recorded_at_local,
                event.order,
            )
        )
        for event in tagged[:LLM_PROMPT_PINNED_PER_TAG]:
            add(event)

    return sorted(selected, key=event_sort_key)


def sample_events_for_prompt(events: list[Event], *, max_events: int = LLM_PROMPT_EVENT_LIMIT) -> list[Event]:
    if max_events <= 0 or not events:
        return []
    ordered = sorted(events, key=event_sort_key)
    if len(ordered) <= max_events:
        return ordered
    if max_events == 1:
        return [ordered[0]]

    selected = select_priority_prompt_events(ordered, max_events=max_events)
    seen = set(selected)
    remaining_slots = max_events - len(selected)

    if remaining_slots <= 0:
        return sorted(selected, key=event_sort_key)

    grouped = [
        deque(event for event in group if event not in seen)
        for group in group_events_by_source(ordered)
    ]

    while remaining_slots > 0:
        active_indices = [index for index, queue in enumerate(grouped) if queue]
        if not active_indices:
            break

        bucket_pick_count = min(len(active_indices), remaining_slots)
        for active_position in evenly_spaced_indices(len(active_indices), bucket_pick_count):
            queue = grouped[active_indices[active_position]]
            while queue and queue[0] in seen:
                queue.popleft()
            if not queue:
                continue
            event = queue.popleft()
            selected.append(event)
            seen.add(event)
            remaining_slots -= 1
            if remaining_slots <= 0:
                break

    return sorted(selected, key=event_sort_key)


def collapse_prompt_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def truncate_prompt_fragment(text: str, *, max_chars: int) -> str:
    normalized = collapse_prompt_whitespace(text)
    if len(normalized) <= max_chars:
        return normalized
    clipped = normalized[: max_chars - 3].rstrip()
    if " " in clipped:
        clipped = clipped.rsplit(" ", 1)[0].rstrip()
    if not clipped:
        clipped = normalized[: max_chars - 3].rstrip()
    return f"{clipped}..."


def build_prompt_event_lines(
    events: list[Event],
    *,
    char_budget: int = LLM_PROMPT_CHAR_BUDGET,
) -> tuple[list[str], list[Event]]:
    lines: list[str] = []
    included: list[Event] = []
    used_chars = 0

    for event in events:
        section_title = truncate_prompt_fragment(event.section_title, max_chars=LLM_PROMPT_SECTION_TITLE_LIMIT)
        text = truncate_prompt_fragment(event.text, max_chars=LLM_PROMPT_EVENT_TEXT_LIMIT)
        line = (
            f"- [{event.source.recorded_at_local.strftime('%H:%M')}] "
            f"{event.source.granularity} | {section_title} | tags={','.join(event.tags)} | {text}"
        )
        projected = used_chars + len(line) + (1 if lines else 0)
        if lines and projected > char_budget:
            break
        if not lines and projected > char_budget:
            line = truncate_prompt_fragment(line, max_chars=char_budget)
            projected = len(line)
        lines.append(line)
        included.append(event)
        used_chars = projected

    return lines, included


def build_llm_prompt(
    *,
    mode: str,
    target_date: str,
    day_boundary_hour: int,
    stats: dict[str, int],
    events: list[Event],
    output_language: str,
    diary_length: str = DEFAULT_DIARY_LENGTH_CODE,
) -> str:
    language = normalize_output_language(output_language)
    normalized_length = normalize_diary_length_code(diary_length)
    profile = diary_length_profile(normalized_length)
    spec = language_spec(language)
    sections = spec["sections"]
    prompt_events = sample_events_for_prompt(events, max_events=profile["prompt_event_limit"])
    prompt_event_lines, included_prompt_events = build_prompt_event_lines(
        prompt_events,
        char_budget=profile["prompt_char_budget"],
    )
    if language == "korean":
        title_suffix = "작업 일기 초안" if mode == "draft-update" else "작업 일기"
        source_note = (
            f"> Chronicle 10분 요약 {stats.get('used_10min', 0)}개"
            f"{'와 6시간 요약 ' + str(stats.get('used_6h', 0)) + '개' if stats.get('used_6h', 0) else ''}"
            "를 바탕으로 정리했다."
        )
    else:
        title_key = "draft" if mode == "draft-update" else "final"
        title_suffix = spec["title"][title_key]
        six_hour = (
            spec["source_note_six_hour"].format(count=stats.get("used_6h", 0))
            if stats.get("used_6h", 0)
            else ""
        )
        source_note = spec["source_note"].format(
            ten_minute=stats.get("used_10min", 0),
            six_hour=six_hour,
        )
    exact_title = f"# {target_date} {title_suffix}"
    lines = [
        f"Target date: {target_date}",
        f"Mode: {mode}",
        f"Day-boundary hour: {day_boundary_hour}:00 local time",
        f"Output language: {spec['label']}",
        f"Diary length: {normalized_length}",
        f"10-minute summaries used: {stats.get('used_10min', 0)}",
        f"6-hour summaries used: {stats.get('used_6h', 0)}",
        f"Total extracted events: {len(events)}",
        f"Prompt events sampled: {len(prompt_events)}",
        f"Prompt events included: {len(included_prompt_events)}",
        f"Prompt source windows represented: {len({event.source.path for event in included_prompt_events})}",
        "",
        "Writing rules:",
        f"- Write the entire markdown in {spec['label']}.",
        "- Do not invent unseen facts, projects, actions, or emotions.",
        "- Only reflect emotion if it is explicit; otherwise stay restrained and describe focus, comparison, review, or context recovery.",
        "- Do not quote the source text at length; summarize instead.",
        "- Never restore or repeat sensitive data.",
        "- Even if they feel low-signal, keep real app switches, short document checks, confirmation clicks, waiting states, and auth flows if they were actually visible.",
        f"- Length target: {normalized_length}. {profile['guidance']}",
        "- Include both the report section and the diary section in the same document.",
        "- The diary section should not copy the report verbatim; it should sound softer and a little more personal while staying factual.",
        f"- The first line must be exactly: {exact_title}",
        f"- The second block must be a blockquote line consistent with the source counts, for example: {source_note}",
        "- Do not emit placeholders such as `제목`, `title`, `one-line short meta note`, or bracketed instructions.",
        "- Keep the following Markdown structure and section headings exactly:",
        f"  {exact_title}",
        f"  {source_note}",
        f"  {spec['report_heading']}",
        f"  {sections['today']}",
        f"  {sections['timeline']}",
        f"  {sections['decisions']}",
        f"  {sections['blockers']}",
        f"  {sections['tomorrow']}",
        f"  {sections['reflection']}",
        f"  {spec['diary_heading']}",
        f"  ({profile['diary_paragraph_instruction']})",
        "",
        "- Treat the event list as chronological coverage of the whole day. If there are many events, it is balanced across source windows instead of taking only the earliest dense cluster.",
        f"- If the day has many events, keep the timeline section concrete and appropriately detailed for the {normalized_length} setting instead of compressing it too aggressively.",
        "- When visible, decision, blocker, and next_action events are pinned into the prompt even if the day is otherwise noisy.",
        "- Event lines may be trimmed to keep the prompt within a bounded size.",
        "",
        "Event list:",
    ]
    lines.extend(prompt_event_lines)
    return "\n".join(lines)


def fallback_markdown(
    *,
    target_date: str,
    mode: str,
    stats: dict[str, int],
    events: list[Event],
    output_language: str = COMPATIBILITY_FALLBACK_LANGUAGE,
    diary_length: str = DEFAULT_DIARY_LENGTH_CODE,
) -> str:
    language = normalize_output_language(output_language, default=COMPATIBILITY_FALLBACK_LANGUAGE)
    activities, decisions, blockers, next_actions = extract_lists(
        events,
        language,
        diary_length=diary_length,
    )
    timeline = build_minor_timeline(events, language, diary_length=diary_length)
    reflection = build_reflection(events, activities, blockers, language)

    if language == "korean":
        title_suffix = "작업 일기 초안" if mode == "draft-update" else "작업 일기"
        source_note = (
            f"> Chronicle 10분 요약 {stats.get('used_10min', 0)}개"
            f"{'와 6시간 요약 ' + str(stats.get('used_6h', 0)) + '개' if stats.get('used_6h', 0) else ''}"
            "를 바탕으로 정리했다."
        )
    else:
        spec = language_spec(language)
        title_key = "draft" if mode == "draft-update" else "final"
        title_suffix = spec["title"][title_key]
        six_hour = (
            spec["source_note_six_hour"].format(count=stats.get("used_6h", 0))
            if stats.get("used_6h", 0)
            else ""
        )
        source_note = spec["source_note"].format(
            ten_minute=stats.get("used_10min", 0),
            six_hour=six_hour,
        )
    return "\n".join(
        [
            f"# {target_date} {title_suffix}",
            "",
            source_note,
            "",
            format_report_section(
                activities=activities,
                timeline=timeline,
                decisions=decisions,
                blockers=blockers,
                next_actions=next_actions,
                reflection=reflection,
                output_language=language,
            ),
            format_diary_section(
                activities=activities,
                timeline=timeline,
                decisions=decisions,
                blockers=blockers,
                next_actions=next_actions,
                reflection=reflection,
                output_language=language,
            ),
        ]
    )


def generate_markdown(
    *,
    target_date: str,
    mode: str,
    day_boundary_hour: int,
    stats: dict[str, int],
    events: list[Event],
    provider: Optional[LLMProvider],
    output_language: str,
    progress: Optional[ProgressCallback] = None,
    diary_length: str = DEFAULT_DIARY_LENGTH_CODE,
    should_cancel: Optional[CancellationCheck] = None,
) -> tuple[str, bool, list[str]]:
    raise_if_cancelled(should_cancel)
    if progress is not None:
        progress(
            {
                "status": "running",
                "phase": "write",
                "step_key": "loading.step.write",
                "detail_key": "loading.detail.writePrepare",
                "percent": 72,
                "indeterminate": False,
                "stats": {"events_selected": len(events)},
            }
        )
    if provider is None:
        if progress is not None:
            progress(
                {
                    "status": "failed",
                    "phase": "write",
                    "step_key": "loading.step.write",
                    "detail_key": "loading.detail.write",
                    "percent": 72,
                    "indeterminate": False,
                    "error": "먼저 codex를 연결해주세요. ChatGPT 로그인이 확인되지 않았습니다.",
                    "stats": {"events_selected": len(events)},
                }
            )
        raise LLMError("먼저 codex를 연결해주세요. ChatGPT 로그인이 확인되지 않았습니다.")

    prompt = build_llm_prompt(
        mode=mode,
        target_date=target_date,
        day_boundary_hour=day_boundary_hour,
        stats=stats,
        events=events,
        output_language=output_language,
        diary_length=diary_length,
    )
    generate_method = provider.generate_markdown
    signature = inspect.signature(generate_method)
    call_kwargs = {
        "output_language": output_language_label(output_language),
    }
    if "progress" in signature.parameters:
        call_kwargs["progress"] = progress
    if "should_cancel" in signature.parameters:
        call_kwargs["should_cancel"] = should_cancel
    markdown = generate_method(prompt, **call_kwargs)
    raise_if_cancelled(should_cancel)
    if progress is not None:
        progress(
            {
                "status": "running",
                "phase": "finish",
                "step_key": "loading.step.finish",
                "detail_key": "loading.detail.finish",
                "percent": 90,
                "stats": {"events_selected": len(events)},
            }
        )
    return markdown.strip() + "\n", True, []


def resolve_output_path(out_dir: Path, mode: str, target_date: str) -> Path:
    return out_dir / f"{target_date}.md"


def legacy_output_paths(out_dir: Path, target_date: str) -> list[Path]:
    return [out_dir / "drafts" / f"{target_date}.md"]


def build_diary(
    *,
    target_date,
    mode: str,
    source_dir: Path,
    out_dir: Path,
    day_boundary_hour: int,
    output_language: str = DEFAULT_OUTPUT_LANGUAGE,
    diary_length: str = DEFAULT_DIARY_LENGTH_CODE,
    provider: Optional[LLMProvider] = None,
    progress: Optional[ProgressCallback] = None,
    should_cancel: Optional[CancellationCheck] = None,
) -> DiaryBuildResult:
    local_tz = get_local_timezone()
    normalized_output_language = normalize_output_language(output_language)
    normalized_diary_length = normalize_diary_length_code(diary_length)
    target_date_iso = target_date.isoformat()

    def emit_progress(update: dict[str, Any]) -> None:
        if progress is None:
            return
        snapshot = {
            "status": update.get("status", "running"),
            "phase": update.get("phase"),
            "percent": update.get("percent"),
            "current": update.get("current"),
            "total": update.get("total"),
            "step_key": update.get("step_key"),
            "detail_key": update.get("detail_key"),
            "indeterminate": bool(update.get("indeterminate", False)),
            "error": update.get("error"),
            "target_date": target_date_iso,
            "mode": mode,
            "output_language_code": normalized_output_language,
            "stats": dict(update.get("stats") or {}),
        }
        progress(snapshot)

    emit_progress(
        {
            "status": "running",
            "phase": "collect",
            "step_key": "loading.step.collect",
            "detail_key": "loading.detail.collect",
            "percent": 6,
        }
    )
    raise_if_cancelled(should_cancel)
    sources = discover_sources(
        source_dir,
        target_date=target_date,
        day_boundary_hour=day_boundary_hour,
        local_tz=local_tz,
    )
    if not sources:
        message = (
            f"{target_date_iso} 기준 Chronicle 요약 파일을 찾지 못했습니다. "
            f"입력 폴더를 확인하거나 --source-dir 옵션을 사용해 주세요."
        )
        emit_progress(
            {
                "status": "failed",
                "phase": "collect",
                "step_key": "loading.step.collect",
                "detail_key": "loading.detail.collect",
                "percent": 6,
                "error": message,
            }
        )
        raise FileNotFoundError(
            message
        )
    raise_if_cancelled(should_cancel)

    ten_minute_sources, six_hour_sources = split_sources_by_granularity(sources)
    emit_progress(
        {
            "status": "running",
            "phase": "collect",
            "step_key": "loading.step.collect",
            "detail_key": "loading.detail.collect",
            "current": 0,
            "total": len(sources),
            "percent": 10,
            "stats": {
                "sources_total": len(sources),
                "sources_10min": len(ten_minute_sources),
                "sources_6h": len(six_hour_sources),
            },
        }
    )

    events, stats = choose_events(sources, progress=emit_progress, should_cancel=should_cancel)
    if not events:
        message = (
            f"{target_date_iso} 기준 Chronicle 요약은 있었지만, 읽을 수 있는 본문 이벤트를 추출하지 못했습니다."
        )
        emit_progress(
            {
                "status": "failed",
                "phase": "organize",
                "step_key": "loading.step.organize",
                "detail_key": "loading.detail.organize",
                "percent": 44,
                "error": message,
                "stats": stats,
            }
        )
        raise FileNotFoundError(
            message
        )
    raise_if_cancelled(should_cancel)

    resolved_provider = provider if provider is not None else load_provider_from_codex()
    markdown, used_llm, warnings = generate_markdown(
        target_date=target_date_iso,
        mode=mode,
        day_boundary_hour=day_boundary_hour,
        stats=stats,
        events=events,
        provider=resolved_provider,
        output_language=normalized_output_language,
        progress=emit_progress,
        diary_length=normalized_diary_length,
        should_cancel=should_cancel,
    )
    result = DiaryBuildResult(
        target_date=target_date,
        mode=mode,
        markdown=markdown,
        output_path=resolve_output_path(out_dir, mode, target_date_iso),
        used_llm=used_llm,
        stats={**stats, "diary_length": normalized_diary_length},
        warnings=tuple(warnings),
    )
    emit_progress(
        {
            "status": "completed",
            "phase": "finish",
            "step_key": "loading.step.finish",
            "detail_key": "loading.detail.finish",
            "percent": 100,
            "stats": {**stats, "events_selected": len(events)},
        }
    )
    return result
