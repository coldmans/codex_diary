from __future__ import annotations

from collections import Counter
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
import re
from typing import Iterable, Optional

from .chronicle import discover_sources, get_local_timezone, split_sources_by_granularity
from .llm import LLMError, LLMProvider, load_provider_from_env
from .models import ChronicleSource, DiaryBuildResult, Event
from .parser import extract_events

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
    if not left_norm or not right_norm:
        return False
    if left_norm == right_norm:
        return True
    if left_norm in right_norm or right_norm in left_norm:
        return True
    ratio = SequenceMatcher(None, left_norm, right_norm).ratio()
    if ratio >= 0.9:
        return True
    left_tokens = token_set(left_norm)
    right_tokens = token_set(right_norm)
    if not left_tokens or not right_tokens:
        return False
    intersection = len(left_tokens & right_tokens)
    overlap = intersection / len(left_tokens | right_tokens)
    coverage = intersection / min(len(left_tokens), len(right_tokens))
    return overlap >= 0.75 or coverage >= 0.66


def source_priority(source: ChronicleSource) -> int:
    return 2 if source.granularity == "10min" else 1


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
    for candidate in ordered:
        if any(are_events_similar(candidate, seen) for seen in unique):
            continue
        unique.append(candidate)
    return sorted(unique, key=lambda event: (event.source.recorded_at_local, event.order))


def load_events(sources: Iterable[ChronicleSource]) -> list[Event]:
    events: list[Event] = []
    for source in sources:
        markdown = source.path.read_text(encoding="utf-8")
        events.extend(extract_events(source, markdown))
    return events


def choose_events(sources: list[ChronicleSource]) -> tuple[list[Event], dict[str, int]]:
    ten_minute_sources, six_hour_sources = split_sources_by_granularity(sources)
    ten_minute_events = dedupe_events(load_events(ten_minute_sources))

    stats = {
        "sources_total": len(sources),
        "sources_10min": len(ten_minute_sources),
        "sources_6h": len(six_hour_sources),
        "used_10min": len(ten_minute_sources),
        "used_6h": 0,
    }

    if ten_minute_events and (len(ten_minute_events) >= MIN_PRIMARY_EVENTS or not six_hour_sources):
        return ten_minute_events, stats

    six_hour_events = dedupe_events(load_events(six_hour_sources))
    merged = dedupe_events([*ten_minute_events, *six_hour_events])
    used_six_hour = {event.source.path for event in merged if event.source.granularity == "6h"}
    stats["used_6h"] = len(used_six_hour)
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
    for sentence in sentences:
        normalized = normalize_for_similarity(sentence)
        if not normalized:
            continue
        duplicate = False
        for existing in results:
            existing_norm = normalize_for_similarity(existing)
            if (
                existing_norm == normalized
                or normalized in existing_norm
                or existing_norm in normalized
                or SequenceMatcher(None, existing_norm, normalized).ratio() >= 0.88
            ):
                duplicate = True
                break
        if duplicate:
            continue
        results.append(sentence)
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


def build_minor_timeline(events: list[Event]) -> list[str]:
    timeline = []
    for event in events:
        phrase = to_korean_timeline_phrase(event).strip()
        if not phrase:
            continue
        prefix = event.source.recorded_at_local.strftime("%H:%M")
        timeline.append(f"[{prefix}] {phrase}")
    return unique_sentences(timeline)


def extract_lists(events: list[Event]) -> tuple[list[str], list[str], list[str], list[str]]:
    activities = unique_sentences(to_korean_sentence(event) for event in select_representative_events(events, limit=5))
    decisions = unique_sentences(
        to_korean_decision(event)
        for event in select_representative_events(events, limit=4, required_tag="decision")
    )
    blockers = unique_sentences(
        to_korean_blocker(event)
        for event in select_representative_events(events, limit=4, required_tag="blocker")
    )
    next_actions = unique_sentences(
        to_korean_next_action(event)
        for event in select_representative_events(events, limit=4, required_tag="next_action")
    )
    if not next_actions:
        next_actions = unique_sentences(
            to_korean_next_action(event)
            for event in select_representative_events(events, limit=4, required_tag="blocker")
        )

    if not decisions and events:
        decisions = ["새로운 결정보다도 현재 작업 맥락과 우선순위를 다시 맞추는 데 의미가 있었던 날이었다."]
    if not blockers:
        blockers = ["당장 작업이 멈출 정도의 치명적인 장애는 보이지 않았지만, 후속 검증이 남아 있는 항목은 있었다."]
    if not next_actions:
        next_actions = ["오늘 확인한 맥락을 기준으로 가장 가까운 구현 또는 정리 작업 하나를 먼저 확정하기"]
    return activities[:5], decisions[:4], blockers[:4], next_actions[:4]


def format_today_section(activities: list[str]) -> str:
    if not activities:
        return "기록이 많지 않아 세부 흐름은 제한적이었지만, 화면에 남은 Chronicle 요약을 바탕으로 오늘의 작업 맥락을 다시 정리했다."
    connectors = ["초반에는", "이어서", "중간에는", "마지막으로", "끝무렵에는"]
    sentences = []
    for index, activity in enumerate(activities):
        prefix = connectors[index] if index < len(connectors) else "또"
        trimmed = activity[:-1] if activity.endswith(".") else activity
        sentences.append(f"{prefix} {trimmed}.")
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
) -> str:
    return "\n".join(
        [
            "## 금일 작업 보고서",
            "",
            "### 오늘 한 일",
            format_today_section(activities),
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


def format_diary_section(
    *,
    activities: list[str],
    timeline: list[str],
    decisions: list[str],
    blockers: list[str],
    next_actions: list[str],
    reflection: str,
) -> str:
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


def build_reflection(events: list[Event], activities: list[str], blockers: list[str]) -> str:
    projects = Counter(subject for event in events if (subject := choose_subject(event)))
    multi_project = len(projects) >= 2
    research_heavy = sum(1 for event in events if "research" in event.tags) >= max(2, len(events) // 3)
    blocker_heavy = blockers and "치명적인 장애" not in blockers[0]

    parts = []
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


def build_llm_prompt(
    *,
    mode: str,
    target_date: str,
    day_boundary_hour: int,
    stats: dict[str, int],
    events: list[Event],
) -> str:
    lines = [
        f"대상 날짜: {target_date}",
        f"모드: {mode}",
        f"하루 경계 시각: 오전 {day_boundary_hour}시",
        f"사용한 10분 요약 개수: {stats.get('used_10min', 0)}",
        f"사용한 6시간 요약 개수: {stats.get('used_6h', 0)}",
        "",
        "작성 규칙:",
        "- 보이지 않은 사실이나 감정을 지어내지 말 것",
        "- 감정은 명시적으로 드러난 경우만 반영하고, 아니면 집중, 비교 검토, 맥락 복구 정도로 절제할 것",
        "- 원문을 길게 인용하지 말고 요약 위주로 쓸 것",
        "- 민감정보는 절대 복원하거나 재인용하지 말 것",
        "- 중요도가 낮아 보여도 화면에 실제로 나온 앱 전환, 짧은 문서 열람, 확인용 클릭, 대기나 인증 흐름은 빠뜨리지 말 것",
        "- 결과는 같은 문서 안에 '금일 작업 보고서'와 '오늘의 일기 버전' 두 섹션을 모두 포함할 것",
        "- 일기 버전은 보고서를 그대로 복붙하지 말고, 흐름을 조금 더 부드럽고 살짝 귀엽게 풀어 쓸 것",
        "- 다만 귀여운 톤 때문에 사실이 바뀌거나 감정이 과장되면 안 됨",
        "- 아래 Markdown 구조를 유지할 것:",
        "  # 제목",
        "  > 짧은 메타 설명 1줄",
        "  ## 금일 작업 보고서",
        "  ### 오늘 한 일",
        "  ### 사소한 흐름까지 포함한 시간순 메모",
        "  ### 중요하게 확인하거나 결정한 것",
        "  ### 막혔던 점 또는 미해결 이슈",
        "  ### 내일 할 일",
        "  ### 짧은 회고",
        "  ## 오늘의 일기 버전",
        "  (2-4개 짧은 문단)",
        "",
        "이벤트 목록:",
    ]
    for event in events[:18]:
        lines.append(
            f"- [{event.source.recorded_at_local.strftime('%H:%M')}] "
            f"{event.source.granularity} | {event.section_title} | tags={','.join(event.tags)} | {event.text}"
        )
    return "\n".join(lines)


def fallback_markdown(
    *,
    target_date: str,
    mode: str,
    stats: dict[str, int],
    events: list[Event],
) -> str:
    activities, decisions, blockers, next_actions = extract_lists(events)
    timeline = build_minor_timeline(events)
    title_suffix = "작업 일기 초안" if mode == "draft-update" else "작업 일기"
    reflection = build_reflection(events, activities, blockers)
    source_note = (
        f"> Chronicle 10분 요약 {stats.get('used_10min', 0)}개"
        f"{'와 6시간 요약 ' + str(stats.get('used_6h', 0)) + '개' if stats.get('used_6h', 0) else ''}"
        "를 바탕으로 정리했다."
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
            ),
            format_diary_section(
                activities=activities,
                timeline=timeline,
                decisions=decisions,
                blockers=blockers,
                next_actions=next_actions,
                reflection=reflection,
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
) -> tuple[str, bool, list[str]]:
    warnings: list[str] = []
    if provider:
        try:
            markdown = provider.generate_markdown(
                build_llm_prompt(
                    mode=mode,
                    target_date=target_date,
                    day_boundary_hour=day_boundary_hour,
                    stats=stats,
                    events=events,
                )
            )
            return markdown.strip() + "\n", True, warnings
        except LLMError as exc:
            warnings.append(f"LLM 호출이 실패해 규칙 기반 요약으로 대체했습니다: {exc}")
    return fallback_markdown(
        target_date=target_date,
        mode=mode,
        stats=stats,
        events=events,
    ), False, warnings


def resolve_output_path(out_dir: Path, mode: str, target_date: str) -> Path:
    if mode == "draft-update":
        return out_dir / "drafts" / f"{target_date}.md"
    return out_dir / f"{target_date}.md"


def build_diary(
    *,
    target_date,
    mode: str,
    source_dir: Path,
    out_dir: Path,
    day_boundary_hour: int,
    provider: Optional[LLMProvider] = None,
) -> DiaryBuildResult:
    local_tz = get_local_timezone()
    sources = discover_sources(
        source_dir,
        target_date=target_date,
        day_boundary_hour=day_boundary_hour,
        local_tz=local_tz,
    )
    if not sources:
        raise FileNotFoundError(
            f"{target_date.isoformat()} 기준 Chronicle 요약 파일을 찾지 못했습니다. "
            f"입력 폴더를 확인하거나 --source-dir 옵션을 사용해 주세요."
        )

    events, stats = choose_events(sources)
    if not events:
        raise FileNotFoundError(
            f"{target_date.isoformat()} 기준 Chronicle 요약은 있었지만, 읽을 수 있는 본문 이벤트를 추출하지 못했습니다."
        )

    resolved_provider = provider if provider is not None else load_provider_from_env()
    markdown, used_llm, warnings = generate_markdown(
        target_date=target_date.isoformat(),
        mode=mode,
        day_boundary_hour=day_boundary_hour,
        stats=stats,
        events=events,
        provider=resolved_provider,
    )
    return DiaryBuildResult(
        target_date=target_date,
        mode=mode,
        markdown=markdown,
        output_path=resolve_output_path(out_dir, mode, target_date.isoformat()),
        used_llm=used_llm,
        stats=stats,
        warnings=tuple(warnings),
    )
