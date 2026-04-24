# 이벤트 선정과 유사도 판단 쉽게 이해하기

이 문서는 `codex-diary`가 Chronicle 요약을 읽어서 어떤 이벤트를 남기고, 어떤 이벤트를 중복으로 보고 버리는지 설명합니다. 코드를 잘 모르는 사람도 따라올 수 있도록 예시 중심으로 정리했습니다.

관련 코드:

- 이벤트 추출: [`codex_diary/parser.py`](../codex_diary/parser.py)
- 이벤트 선정, 중복 제거, 프롬프트 샘플링: [`codex_diary/generator.py`](../codex_diary/generator.py)

## 한 줄 요약

앱은 Chronicle Markdown 전체를 그대로 LLM 프롬프트에 넣지 않습니다. 먼저 작은 `Event` 조각으로 나누고, 비슷한 이벤트를 제거하고, 중요한 이벤트와 하루 전체 흐름을 대표하는 이벤트만 골라서 프롬프트에 넣습니다.

```text
Chronicle Markdown
  -> Event로 쪼개기
  -> 10min 우선, 필요할 때만 6h 추가
  -> 비슷한 이벤트 중복 제거
  -> 중요한 이벤트 먼저 고정
  -> 시간대별로 골고루 샘플링
  -> 글자 수 예산 안에서 프롬프트 생성
```

## 왜 이런 로직이 필요한가

Chronicle 요약이 하루 동안 많이 쌓이면 모든 내용을 LLM에 넣기 어렵습니다. 입력이 너무 길어지면 비용이 커지고, 응답이 느려지고, 중요한 내용이 오히려 묻힐 수 있습니다.

그래서 이 앱은 아래 목표를 가집니다.

- 같은 내용을 여러 번 넣지 않는다.
- 중요한 결정, 막힌 점, 다음 작업은 최대한 살린다.
- 아침 기록만 잔뜩 들어가고 밤 기록은 사라지는 일을 막는다.
- 프롬프트 크기를 일정한 범위 안에 유지한다.

## Event란 무엇인가

`Event`는 "하루 중 의미 있는 작은 기록 한 조각"입니다.

예를 들어 Chronicle 요약에 이런 내용이 있다고 해봅시다.

```markdown
## Recording summary

### Codex Diary README
- The user reviewed the README language links.
- Codex added Korean, Japanese, and Chinese README files.
- A later check found one Japanese line still contained Korean text.

### Follow-up
- The next step was to explain the event selection logic more clearly.
```

앱은 이 내용을 대략 이렇게 나눕니다.

| 순서 | section_title | text | tags 예시 |
| --- | --- | --- | --- |
| 1 | Codex Diary README | The user reviewed the README language links. | research |
| 2 | Codex Diary README | Codex added Korean, Japanese, and Chinese README files. | activity |
| 3 | Codex Diary README | A later check found one Japanese line still contained Korean text. | activity |
| 4 | Follow-up | The next step was to explain the event selection logic more clearly. | next_action |

즉 문서 전체가 아니라, 각각의 bullet이나 문장이 선택 후보가 됩니다.

## 1단계: Markdown에서 Event 추출

이벤트 추출은 [`parser.py`](../codex_diary/parser.py)에서 합니다.

앱은 기본적으로 `## Recording summary` 아래의 `### 섹션`들을 읽습니다. 그리고 그 안의 bullet, 번호 목록, 문단을 작은 문장 단위로 나눕니다.

```markdown
## Recording summary

### Browser
- The user opened GitHub.
- The user checked the README.
```

위 내용은 아래처럼 됩니다.

```text
Event 1: section=Browser, text=The user opened GitHub.
Event 2: section=Browser, text=The user checked the README.
```

이때 민감정보 마스킹도 같이 거칩니다. 예를 들어 토큰, 긴 인증값, 이메일 같은 값은 가능한 한 그대로 프롬프트에 들어가지 않게 처리합니다.

## 2단계: tag 붙이기

각 이벤트에는 `tags`가 붙습니다. 태그는 복잡한 AI 분류가 아니라 키워드 기반입니다.

| 태그 | 이런 단어가 있으면 붙기 쉬움 | 의미 |
| --- | --- | --- |
| `decision` | `planned`, `decided`, `mvp`, `fallback` | 결정, 방향 설정 |
| `research` | `reviewed`, `docs`, `checked`, `scrolled` | 자료 확인, 조사 |
| `blocker` | `error`, `failed`, `missing`, `could not` | 막힌 점, 오류 |
| `next_action` | `next step`, `todo`, `needs follow-up` | 다음 작업 |
| `activity` | 위에 해당하지 않음 | 일반 활동 |

예시:

```text
The user decided to keep README.md as the source document.
-> decision

The app failed because Codex was not logged in.
-> blocker

The next step was to add beginner-friendly examples.
-> next_action
```

## 3단계: 10min 요약을 먼저 쓰고, 6h 요약은 필요할 때만 추가

Chronicle에는 `10min` 요약과 `6h` 요약이 있을 수 있습니다.

- `10min`: 더 촘촘하고 구체적인 기록
- `6h`: 넓은 시간대를 한번에 요약한 기록

앱은 먼저 `10min` 요약만 읽습니다. `10min`만으로 하루 흐름이 충분하면 `6h` 요약은 쓰지 않습니다.

충분하다고 보는 기준은 대략 이렇습니다.

- 이벤트가 최소 5개 이상이어야 함
- 그리고 아래 둘 중 하나를 만족해야 함
- 2시간 단위 시간대가 3개 이상 커버됨
- 전체 기록 span이 6시간 이상임

예시:

| 상황 | 판단 |
| --- | --- |
| 10min 이벤트가 20개 있고 오전, 오후, 밤 기록이 있음 | 10min만 사용 |
| 10min 이벤트가 2개뿐임 | 6h도 추가 |
| 10min 이벤트는 많지만 전부 10:00~10:30에 몰려 있음 | 6h도 추가할 수 있음 |

왜 이렇게 하냐면, `6h`는 도움은 되지만 `10min`과 내용이 겹치는 경우가 많기 때문입니다. 기본은 더 구체적인 `10min`을 신뢰하고, 부족할 때만 `6h`를 보조로 씁니다.

## 4단계: 중복 제거가 필요한 이유

`10min`과 `6h`를 같이 쓰면 같은 일이 여러 번 나타날 수 있습니다.

예시:

```text
10min: The user checked the README language links.
6h: The user reviewed README language links while preparing multilingual docs.
```

두 문장은 완전히 같지는 않지만, 같은 일을 말하고 있습니다. 둘 다 프롬프트에 넣으면 LLM은 이 일을 더 중요하게 착각하거나, 결과 일기에 같은 내용이 반복될 수 있습니다.

그래서 앱은 "시간적으로 가깝고, 내용도 충분히 비슷한 이벤트"를 중복으로 보고 하나만 남깁니다.

## 5단계: 유사도 판단 전체 흐름

유사도 판단은 아래 순서로 진행됩니다.

```text
후보 이벤트 하나를 가져온다
  -> 비교용 문자열로 정규화한다
  -> 의미 있는 토큰만 뽑는다
  -> signature bucket으로 비교할 후보를 줄인다
  -> 시간 차이가 너무 크면 중복으로 보지 않는다
  -> 텍스트가 충분히 비슷하면 중복으로 본다
```

아래부터 하나씩 봅니다.

## 5-1단계: 정규화

정규화는 비교하기 쉽게 문장을 단순화하는 과정입니다.

코드에서는 대략 이런 일을 합니다.

- 대문자를 소문자로 바꿈
- 백틱은 제거하되 안의 내용은 남김
- 비교에 덜 중요한 특수문자는 공백으로 바꿈
- 여러 공백을 하나로 줄임

예시:

```text
원문:
Checked `/api/users` error in Codex!!!

정규화:
checked /api/users error in codex
```

왜 `/api/users`는 남기냐면, API 경로나 파일명 같은 개발 정보는 중요한 힌트일 수 있기 때문입니다.

## 5-2단계: token_set 만들기

정규화된 문장에서 중요한 단어만 뽑습니다.

예시:

```text
정규화 문장:
the user checked docker config documentation

token_set:
{checked, docker, config, docs}
```

여기서 `the`, `user` 같은 흔한 단어는 버립니다. `documentation`은 `docs`로 통일합니다.

이유는 간단합니다. Chronicle 요약에는 `the user`, `screen`, `summary`, `current` 같은 말이 자주 나오는데, 이런 단어가 겹친다고 같은 이벤트로 보면 안 됩니다.

## 5-3단계: signature bucket으로 비교 후보 줄이기

이벤트가 1,000개라면 모든 이벤트끼리 비교하면 너무 느립니다. 그래서 먼저 "비슷할 가능성이 있는 후보"만 찾습니다.

앱은 각 이벤트에서 이런 signature를 만듭니다.

| signature | 뜻 | 예시 |
| --- | --- | --- |
| `exact` | 정규화 문자열 전체 | `checked readme language links` |
| `prefix` | 앞 28자 | `checked readme language lin` |
| `suffix` | 뒤 28자 | `readme language links` |
| `token` | 가장 긴 토큰 1개 | `language` |
| `pair` | 가장 긴 토큰 2개 조합 | `language|checked` |

새 이벤트가 들어왔을 때 같은 signature를 가진 기존 이벤트만 비교합니다.

예시:

```text
기존 이벤트 A:
checked readme language links
signatures: exact=..., prefix=..., suffix=..., token=language, pair=language|checked

새 이벤트 B:
reviewed readme language links
signatures 중 token=language, suffix=readme language links 등이 겹칠 수 있음

=> 비교 후보가 됨
```

반대로 완전히 다른 이벤트는 signature가 겹치지 않아서 비교 자체를 안 할 수 있습니다.

```text
기존 이벤트:
checked readme language links

새 이벤트:
docker mysql connection failed

=> signature가 거의 겹치지 않음
=> 비교 후보에서 제외될 가능성이 높음
```

## 5-4단계: 시간 window 확인

signature가 겹쳐도 바로 중복으로 보지는 않습니다. 시간적으로 가까워야 합니다.

현재 window는 이렇게 나뉩니다.

| 비교 상황 | 중복으로 볼 수 있는 시간 범위 |
| --- | --- |
| 일반 10min 이벤트끼리 | 90분 이내 |
| 같은 파일 안 이벤트 | 390분 이내 |
| 6h가 섞인 비교 | 390분 이내 |

예시:

```text
10:00 - README links checked
10:40 - README language links reviewed
=> 40분 차이, 비슷하면 중복 가능

10:00 - README links checked
22:00 - README links checked again
=> 12시간 차이, 반복 작업일 수 있으니 중복으로 보지 않음
```

왜 `6h`는 390분으로 더 넓게 보냐면, 6시간 요약은 넓은 시간대를 압축하기 때문입니다. 실제로는 10:00 작업을 말하는데 파일 timestamp는 더 뒤쪽일 수 있습니다.

## 5-5단계: 텍스트가 비슷한지 판단

시간 조건을 통과하면 실제 텍스트 유사도를 봅니다.

판단 순서는 아래와 같습니다.

```text
1. 둘 중 하나가 비어 있으면 중복 아님
2. 정규화 문장이 완전히 같으면 중복
3. 한 문장이 다른 문장 안에 들어 있으면 중복
4. 토큰이 없으면 SequenceMatcher 0.9 이상일 때 중복
5. 공통 토큰이 없으면 중복 아님
6. overlap >= 0.75 이면 중복
7. coverage >= 0.66 이면 중복
8. overlap <= 0.2 이고 coverage <= 0.34 이면 중복 아님
9. 길이 차이가 큰데 coverage < 0.5 이면 중복 아님
10. 마지막으로 SequenceMatcher 0.9 이상이면 중복
```

초보자 입장에서는 `overlap`과 `coverage`만 이해하면 됩니다.

## overlap이란

두 이벤트가 가진 전체 토큰 중 얼마나 많이 겹치는지 보는 값입니다.

```text
A tokens = {docker, mysql, migration}
B tokens = {docker, mysql, config}

교집합 = {docker, mysql} = 2개
합집합 = {docker, mysql, migration, config} = 4개

overlap = 2 / 4 = 0.5
```

현재 로직에서는 `overlap >= 0.75`이면 꽤 비슷하다고 봅니다.

예시:

```text
A = docker mysql migration checked
B = docker mysql migration reviewed

A tokens = {docker, mysql, migration, checked}
B tokens = {docker, mysql, migration, reviewed}
교집합 = 3
합집합 = 5
overlap = 3 / 5 = 0.6

=> overlap만 보면 0.75보다 낮아서 아직 확정 중복은 아님
```

## coverage란

짧은 문장의 핵심 단어가 긴 문장에 얼마나 포함됐는지 보는 값입니다.

```text
A tokens = {docker, mysql, migration}
B tokens = {docker, mysql, migration, backend, config, followup}

교집합 = {docker, mysql, migration} = 3개
짧은 쪽 토큰 수 = 3개

coverage = 3 / 3 = 1.0
```

이 경우 B가 더 길지만 A의 핵심을 전부 포함합니다. 그래서 같은 이벤트일 가능성이 높습니다.

현재 로직에서는 `coverage >= 0.66`이면 중복으로 봅니다.

## overlap과 coverage를 둘 다 쓰는 이유

`overlap`만 쓰면 긴 요약과 짧은 요약의 중복을 잘 못 잡습니다.

예시:

```text
A:
docker mysql migration checked

B:
docker mysql migration checked while backend config still needed follow-up before packaging
```

토큰을 단순화하면:

```text
A = {docker, mysql, migration, checked}
B = {docker, mysql, migration, checked, backend, config, still, needed, follow-up, packaging}
```

계산:

```text
교집합 = 4
합집합 = 10
overlap = 4 / 10 = 0.4
coverage = 4 / 4 = 1.0
```

`overlap`은 낮지만 `coverage`는 높습니다. 즉 짧은 A가 긴 B 안에 거의 들어 있습니다. 이런 경우는 중복으로 보는 것이 맞습니다.

## 예시 1: 완전히 같은 이벤트

```text
A: The user checked README language links.
B: The user checked README language links.
```

정규화 후:

```text
A: the user checked readme language links
B: the user checked readme language links
```

결과:

```text
완전히 같음 -> 중복
```

## 예시 2: 한 문장이 다른 문장에 포함됨

```text
A: checked readme language links
B: checked readme language links before updating korean docs
```

결과:

```text
A가 B 안에 포함됨 -> 중복
```

## 예시 3: 10min과 6h가 같은 일을 말함

```text
10min:
The user checked README language links.

6h:
The user reviewed README language links while preparing multilingual documentation.
```

공통 핵심:

```text
readme, language, links
```

시간 window도 통과하고 coverage가 충분히 높으면 중복으로 봅니다.

이때 어떤 이벤트가 남을까요?

```text
10min이 우선순위가 더 높음 -> 10min 이벤트가 남고 6h 이벤트가 버려질 가능성이 높음
```

## 예시 4: 단어 일부는 같지만 다른 이벤트

```text
A: The user checked README language links.
B: The user fixed Docker MySQL connection errors.
```

토큰:

```text
A = {checked, readme, language, links}
B = {fixed, docker, mysql, connection, errors}
```

공통 토큰이 거의 없습니다.

결과:

```text
중복 아님
```

## 예시 5: 같은 말처럼 보이지만 시간이 너무 멀다

```text
10:00 - The user checked README language links.
22:00 - The user checked README language links.
```

문장은 매우 비슷합니다. 하지만 12시간 차이가 납니다.

결과:

```text
중복 아님
```

이유는 같은 행동을 하루에 두 번 했을 수 있기 때문입니다. 일기에서는 오전에 한 번, 밤에 다시 확인한 흐름이 의미 있을 수 있습니다.

## 예시 6: 너무 짧거나 저신호인 이벤트

```text
Codex
```

이런 이벤트는 정보량이 거의 없습니다. 그래서 noise로 볼 가능성이 높습니다.

또 이런 패턴도 저신호로 봅니다.

```text
the left sidebar showed ...
the preview panel showed ...
the visible prompt asked ...
```

이런 문장은 화면 설명일 뿐 실제 작업의 핵심이 아닐 수 있어서 점수가 낮아집니다.

## 6단계: 중복이면 무엇을 버리나

중복 판단이 true가 되면 "나중에 들어온 후보 이벤트"를 버립니다.

그래서 정렬 순서가 중요합니다. 현재 정렬은 대략 이렇습니다.

```text
1. 10min 이벤트 먼저
2. 더 이른 시간 먼저
3. 파일 안에서 더 앞에 나온 이벤트 먼저
4. 같은 조건이면 더 긴 텍스트 먼저
```

결과적으로 `10min`과 `6h`가 같은 내용을 말하면 더 구체적인 `10min`이 살아남기 쉽습니다.

예시:

```text
6h:
The user reviewed README language links while preparing docs.

10min:
The user checked README language links.
```

입력 순서가 6h가 먼저였더라도, dedupe 내부 정렬에서 10min이 먼저 처리됩니다.

결과:

```text
10min 이벤트 유지
6h 이벤트 제거
```

## 7단계: 프롬프트에 넣을 이벤트 고르기

중복 제거가 끝났다고 모든 이벤트를 프롬프트에 넣지는 않습니다. 이벤트가 너무 많으면 다시 샘플링합니다.

현재 길이별 예산은 대략 이렇습니다.

| length | 최대 이벤트 수 | 이벤트 목록 문자 예산 |
| --- | ---: | ---: |
| `short` | 120 | 18,000 |
| `medium` | 150 | 22,000 |
| `long` | 190 | 28,000 |
| `very-long` | 240 | 36,000 |

프롬프트 샘플링은 이렇게 합니다.

```text
1. 전체 이벤트를 시간순으로 정렬
2. 이벤트 수가 예산 이하면 전부 사용
3. 너무 많으면 첫 이벤트와 마지막 이벤트를 먼저 고정
4. decision, blocker, next_action 이벤트를 태그별 최대 2개씩 고정
5. 남은 자리는 source window별로 골고루 채움
```

## source window별로 골고루 뽑는다는 뜻

예를 들어 이벤트가 이렇게 있다고 합시다.

```text
아침 source: 이벤트 100개
오후 source: 이벤트 5개
밤 source: 이벤트 5개
```

앞에서부터 50개만 자르면 아침 이벤트만 들어갑니다. 그러면 오후와 밤의 흐름이 사라집니다.

그래서 앱은 source를 그룹으로 보고, 가능한 여러 source에서 골고루 뽑습니다.

```text
나쁜 방식:
아침 50개, 오후 0개, 밤 0개

현재 방식:
아침 일부, 오후 일부, 밤 일부
```

## 8단계: 이벤트 한 줄도 잘라낸다

프롬프트에 들어가는 이벤트는 이런 형식입니다.

```text
- [14:20] 10min | README Work | tags=research | The user checked README language links...
```

각 부분도 제한이 있습니다.

| 항목 | 제한 |
| --- | ---: |
| section title | 72자 |
| event text | 240자 |
| 전체 이벤트 목록 | length별 char budget |

그래서 이벤트 하나가 너무 길어도 프롬프트 전체를 망치지 않습니다.

## 전체 예시

입력 이벤트가 이렇게 많다고 해봅시다.

```text
09:00 README language links checked
09:10 README Korean translation added
09:20 README Japanese translation added
09:30 README Chinese translation added
10:00 README language links checked again
14:00 Docker MySQL connection failed
15:00 Next step was to document event selection
21:00 User asked for beginner-friendly examples
```

중복 제거 후:

```text
09:00 README language links checked
09:10 README Korean translation added
09:20 README Japanese translation added
09:30 README Chinese translation added
14:00 Docker MySQL connection failed
15:00 Next step was to document event selection
21:00 User asked for beginner-friendly examples
```

`10:00 README language links checked again`은 09:00과 가까우며 내용이 너무 비슷하면 제거될 수 있습니다.

프롬프트 선정 시:

```text
첫 이벤트 유지:
09:00 README language links checked

blocker 유지:
14:00 Docker MySQL connection failed

next_action 유지:
15:00 Next step was to document event selection

마지막 이벤트 유지:
21:00 User asked for beginner-friendly examples

남은 자리는 시간대와 source를 고려해 채움
```

## 이 로직의 장점

- 프롬프트가 너무 길어지는 것을 막습니다.
- 같은 내용을 반복해서 넣는 일을 줄입니다.
- `10min`의 구체적인 기록을 우선합니다.
- 결정, 오류, 다음 작업 같은 중요한 이벤트를 놓칠 가능성을 줄입니다.
- 하루의 시작과 끝, 여러 시간대의 흐름을 최대한 살립니다.

## 이 로직의 한계

이 로직은 embedding이나 LLM 판단이 아니라 규칙 기반입니다. 그래서 장단점이 있습니다.

장점:

- 빠릅니다.
- 결과가 비교적 예측 가능합니다.
- 외부 API 호출 없이 동작합니다.
- 테스트하기 쉽습니다.

한계:

- 표현은 완전히 다르지만 의미가 같은 이벤트를 놓칠 수 있습니다.
- 키워드가 우연히 많이 겹치면 다른 이벤트를 비슷하다고 볼 수 있습니다.
- 정말 중요한 이벤트인데 `decision`, `blocker`, `next_action` 키워드가 없으면 점수가 낮을 수 있습니다.
- 입력 파일이 너무 많으면 프롬프트는 줄어도 파일 읽기와 이벤트 추출 비용은 여전히 커질 수 있습니다.

## 용어 사전

처음 보면 헷갈릴 수 있는 단어들을 아주 쉽게 풀면 아래와 같습니다.

| 용어 | 쉬운 뜻 |
| --- | --- |
| `Event` | 일기 후보가 되는 작은 사건 카드 |
| `source` | 이벤트가 나온 Chronicle Markdown 파일 |
| `10min` | 10분 단위로 더 촘촘하게 기록된 요약 |
| `6h` | 6시간 단위로 넓게 묶인 요약 |
| `tag` | 이벤트의 성격표. 예: 결정, 오류, 다음 작업 |
| `dedupe` | 비슷한 이벤트를 하나만 남기는 과정 |
| `signature` | 비교 후보를 빨리 찾기 위한 특징값 |
| `bucket` | 같은 signature를 가진 이벤트들을 모아둔 상자 |
| `window` | 중복으로 볼 수 있는 시간 범위 |
| `overlap` | 두 이벤트의 전체 단어 중 겹치는 비율 |
| `coverage` | 짧은 이벤트의 핵심 단어가 긴 이벤트 안에 얼마나 들어 있는지 |
| `SequenceMatcher` | 문자열 모양이 얼마나 비슷한지 보는 Python 기본 도구 |
| `char budget` | 프롬프트에 넣을 수 있는 최대 글자 수 예산 |

비유하자면, 이 로직은 책상 위에 쌓인 메모지를 정리하는 일과 비슷합니다.

```text
1. 메모지를 한 장씩 읽는다.
2. 같은 내용을 말하는 메모지는 하나만 남긴다.
3. 결정, 문제, 다음 할 일 메모는 따로 챙긴다.
4. 오전 메모만 남지 않도록 오후와 밤 메모도 골고루 챙긴다.
5. 최종적으로 작은 묶음만 일기 작성자에게 건넨다.
```

## 다음 개선 아이디어

입력이 더 커질 경우에는 아래 구조가 더 안정적입니다.

```text
많은 Chronicle 파일
  -> source/window별 1차 요약
  -> 1차 요약 캐시 저장
  -> 최종 일기 생성 시 캐시 요약만 다시 합침
```

이런 방식을 흔히 map-reduce 스타일이라고 볼 수 있습니다. 지금은 이벤트 단위 샘플링으로 프롬프트를 줄이고 있고, 다음 단계에서는 source별 요약 캐시를 만들면 전처리 비용까지 줄일 수 있습니다.

## 아주 짧게 다시 정리

초보자용으로 딱 한 문장으로 말하면 이렇습니다.

```text
앱은 하루 기록을 작은 사건들로 쪼갠 뒤, 비슷한 사건은 하나만 남기고, 중요한 사건과 하루 전체 흐름을 대표하는 사건만 골라서 일기 작성용 프롬프트에 넣는다.
```
