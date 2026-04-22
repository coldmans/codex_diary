(() => {
  "use strict";

  const TIMELINE_PREVIEW = 8;
  const TIMELINE_STEP = 20;
  const MOOD_OPTIONS = [
    { key: "sparkle", emoji: "✨" },
    { key: "happy", emoji: "😊" },
    { key: "soft", emoji: "🙂" },
    { key: "tired", emoji: "😐" },
    { key: "blue", emoji: "🥺" },
  ];
  const MEMO_KEY = "codex-diary:memos:v1";
  const MOOD_KEY = "codex-diary:moods:v1";
  const OUTPUT_LANGUAGE_KEY = "codex-diary:output-language:v1";
  const RUNTIME_STYLE_ID = "codex-diary-runtime-style";
  const OUTPUT_LANGUAGES = [
    { key: "en", label: "English", locale: "en-US" },
    { key: "ko", label: "Korean", locale: "ko-KR" },
    { key: "ja", label: "Japanese", locale: "ja-JP" },
    { key: "zh", label: "Chinese", locale: "zh-CN" },
    { key: "fr", label: "French", locale: "fr-FR" },
    { key: "de", label: "German", locale: "de-DE" },
    { key: "es", label: "Spanish", locale: "es-ES" },
    { key: "vi", label: "Vietnamese", locale: "vi-VN" },
    { key: "th", label: "Thai", locale: "th-TH" },
    { key: "ru", label: "Russian", locale: "ru-RU" },
    { key: "hi", label: "Hindi", locale: "hi-IN" },
  ];
  const UI_COPY = window.CODEX_DIARY_UI_COPY || { en: {} };
  const ENTRY_TONES = [
    { accent: "#cf6f57", surface: "#fff0ea", border: "#f0c6bb" },
    { accent: "#ad8452", surface: "#fbf2e4", border: "#e8d3b1" },
    { accent: "#5f8c73", surface: "#eef7f0", border: "#c6ddcc" },
    { accent: "#6a84b6", surface: "#eef3fd", border: "#cbd7f0" },
    { accent: "#c06a7a", surface: "#fff0f3", border: "#efc3cc" },
    { accent: "#69818d", surface: "#eef4f6", border: "#ccdae0" },
  ];
  const MOOD_TONES = {
    sparkle: ENTRY_TONES[1],
    happy: ENTRY_TONES[0],
    soft: ENTRY_TONES[2],
    tired: ENTRY_TONES[5],
    blue: ENTRY_TONES[3],
  };
  const DEFAULT_OUTPUT_LANGUAGE = OUTPUT_LANGUAGES[0].key;

  const state = {
    config: {
      targetDate: null,
      boundaryHour: 4,
      sourceDir: "",
      outDir: "",
      mode: "finalize",
      autoSave: true,
      outputLanguage: DEFAULT_OUTPUT_LANGUAGE,
    },
    nav: "diary",
    view: "diary",
    calendarCursor: null,
    data: null,
    dates: [],
    weeks: [],
    selectedDateIso: null,
    selectedWeekStart: null,
    busy: false,
    codex: {
      loaded: false,
      available: false,
      connected: false,
      connectable: false,
      message: "",
      detail: "",
    },
    timelineVisibleCount: TIMELINE_PREVIEW,
    settingsOpen: false,
    menuOpen: false,
  };

  function currentUiOption(value = state.config.outputLanguage) {
    return OUTPUT_LANGUAGES.find((option) => option.key === value) || OUTPUT_LANGUAGES[0];
  }

  function currentUiLanguage() {
    return currentUiOption().key;
  }

  function currentUiLocale() {
    return currentUiOption().locale;
  }

  function t(key, params = {}) {
    const language = currentUiLanguage();
    const template = UI_COPY[language]?.[key] ?? UI_COPY.en?.[key] ?? key;
    return String(template).replace(/\{\{(\w+)\}\}/g, (_, token) =>
      params[token] === undefined || params[token] === null ? "" : String(params[token]),
    );
  }

  function moodLabel(moodKey) {
    return t(`mood.${moodKey}`);
  }

  const api = () =>
    window.pywebview && window.pywebview.api ? window.pywebview.api : null;

  const $ = (s) => document.querySelector(s);

  function el(tag, attrs = {}, children = []) {
    const node = document.createElement(tag);
    for (const [key, value] of Object.entries(attrs)) {
      if (value === null || value === undefined || value === false) continue;
      if (key === "class") node.className = value;
      else if (key === "html") node.innerHTML = value;
      else if (key.startsWith("on") && typeof value === "function") {
        node.addEventListener(key.slice(2).toLowerCase(), value);
      } else if (key === "dataset") {
        for (const [k, v] of Object.entries(value)) node.dataset[k] = v;
      } else {
        node.setAttribute(key, value);
      }
    }
    for (const child of [].concat(children)) {
      if (child === null || child === undefined || child === false) continue;
      if (typeof child === "string") node.appendChild(document.createTextNode(child));
      else node.appendChild(child);
    }
    return node;
  }

  /* Mascot placeholders ------------------------------------------------- */
  const CLOUD_PATH =
    "M58 74c-14 0-26-10-28-24-10-1-18-10-18-20 0-11 9-20 20-20 2 0 4 0 6 1 5-9 14-15 24-15 12 0 22 7 26 18 2-1 4-1 6-1 11 0 20 9 20 20s-9 20-20 20c-1 0-2 0-3-0-2 12-13 21-25 21z";

  window.__mascotSvg = function mascotSvg(variant) {
    const svgNS = "http://www.w3.org/2000/svg";
    const sizes = {
      brand: 56,
      header: 44,
      empty: 220,
      diary: 240,
    };
    const size = sizes[variant] || 72;
    const svg = document.createElementNS(svgNS, "svg");
    svg.setAttribute("viewBox", "0 0 120 110");
    svg.setAttribute("width", String(size));
    svg.setAttribute("height", String(Math.round(size * 0.92)));
    svg.setAttribute("class", `mascot-svg mascot-svg--${variant}`);
    svg.setAttribute("aria-hidden", "true");

    const defs = document.createElementNS(svgNS, "defs");
    const gradId = `cloudGrad-${variant}`;
    const grad = document.createElementNS(svgNS, "linearGradient");
    grad.setAttribute("id", gradId);
    grad.setAttribute("x1", "0");
    grad.setAttribute("y1", "0");
    grad.setAttribute("x2", "0");
    grad.setAttribute("y2", "1");
    const stop1 = document.createElementNS(svgNS, "stop");
    stop1.setAttribute("offset", "0%");
    stop1.setAttribute("stop-color", "#fff5f0");
    const stop2 = document.createElementNS(svgNS, "stop");
    stop2.setAttribute("offset", "100%");
    stop2.setAttribute("stop-color", "#fcd9cf");
    grad.appendChild(stop1);
    grad.appendChild(stop2);
    defs.appendChild(grad);
    svg.appendChild(defs);

    const cloud = document.createElementNS(svgNS, "path");
    cloud.setAttribute("d", CLOUD_PATH);
    cloud.setAttribute("fill", `url(#${gradId})`);
    cloud.setAttribute("stroke", "#f0a898");
    cloud.setAttribute("stroke-width", "2");
    cloud.setAttribute("stroke-linejoin", "round");
    svg.appendChild(cloud);

    // blush cheeks
    const blushL = document.createElementNS(svgNS, "ellipse");
    blushL.setAttribute("cx", "38");
    blushL.setAttribute("cy", "58");
    blushL.setAttribute("rx", "6");
    blushL.setAttribute("ry", "4");
    blushL.setAttribute("fill", "#f5a496");
    blushL.setAttribute("opacity", "0.65");
    svg.appendChild(blushL);
    const blushR = document.createElementNS(svgNS, "ellipse");
    blushR.setAttribute("cx", "76");
    blushR.setAttribute("cy", "58");
    blushR.setAttribute("rx", "6");
    blushR.setAttribute("ry", "4");
    blushR.setAttribute("fill", "#f5a496");
    blushR.setAttribute("opacity", "0.65");
    svg.appendChild(blushR);

    // eyes (closed, smiley arcs)
    const eyeL = document.createElementNS(svgNS, "path");
    eyeL.setAttribute("d", "M34 50 q4 4 8 0");
    eyeL.setAttribute("stroke", "#3a2f2a");
    eyeL.setAttribute("stroke-width", "2.2");
    eyeL.setAttribute("stroke-linecap", "round");
    eyeL.setAttribute("fill", "none");
    svg.appendChild(eyeL);
    const eyeR = document.createElementNS(svgNS, "path");
    eyeR.setAttribute("d", "M72 50 q4 4 8 0");
    eyeR.setAttribute("stroke", "#3a2f2a");
    eyeR.setAttribute("stroke-width", "2.2");
    eyeR.setAttribute("stroke-linecap", "round");
    eyeR.setAttribute("fill", "none");
    svg.appendChild(eyeR);

    const mouth = document.createElementNS(svgNS, "path");
    mouth.setAttribute("d", "M52 62 q6 5 12 0");
    mouth.setAttribute("stroke", "#3a2f2a");
    mouth.setAttribute("stroke-width", "2");
    mouth.setAttribute("stroke-linecap", "round");
    mouth.setAttribute("fill", "none");
    svg.appendChild(mouth);

    if (variant === "diary" || variant === "empty") {
      const heart = document.createElementNS(svgNS, "path");
      heart.setAttribute(
        "d",
        "M100 30 q3 -4 6 -1 q3 3 0 7 q-3 4 -6 1 q-3 -4 0 -7z",
      );
      heart.setAttribute("fill", "#f27c91");
      heart.setAttribute("opacity", "0.75");
      svg.appendChild(heart);
    }

    return svg;
  };

  /* Format helpers ------------------------------------------------------ */
  function parseIsoDate(iso) {
    if (!iso) return null;
    const d = new Date(`${iso}T12:00:00`);
    return Number.isNaN(d.getTime()) ? null : d;
  }

  function formatBigDate(iso) {
    if (!iso) return t("date.missing");
    const d = parseIsoDate(iso);
    if (!d) return iso;
    if (currentUiLanguage() === "ko") {
      const y = d.getFullYear();
      const m = String(d.getMonth() + 1).padStart(2, "0");
      const day = String(d.getDate()).padStart(2, "0");
      return `${y}. ${m}. ${day}.`;
    }
    return new Intl.DateTimeFormat(currentUiLocale(), {
      year: "numeric",
      month: "short",
      day: "2-digit",
    }).format(d);
  }

  function formatDisplayDate(iso) {
    if (!iso) return "";
    const d = parseIsoDate(iso);
    if (!d) return iso;
    return new Intl.DateTimeFormat(currentUiLocale(), {
      year: "numeric",
      month: "long",
      day: "numeric",
    }).format(d);
  }

  function formatShortMonthDay(iso) {
    if (!iso) return "";
    const d = parseIsoDate(iso);
    if (!d) return iso;
    return new Intl.DateTimeFormat(currentUiLocale(), {
      month: "numeric",
      day: "numeric",
    }).format(d);
  }

  function formatWeekday(iso) {
    const d = parseIsoDate(iso);
    if (!d) return "";
    return new Intl.DateTimeFormat(currentUiLocale(), { weekday: "long" }).format(d);
  }

  function formatMonthYear(year, month) {
    const d = new Date(year, month, 1, 12, 0, 0);
    return new Intl.DateTimeFormat(currentUiLocale(), {
      year: "numeric",
      month: "long",
    }).format(d);
  }

  function weekdayLabels() {
    const formatter = new Intl.DateTimeFormat(currentUiLocale(), {
      weekday: currentUiLanguage() === "en" ? "short" : "narrow",
    });
    const sunday = new Date(Date.UTC(2024, 0, 7, 12, 0, 0));
    return Array.from({ length: 7 }, (_, index) =>
      formatter.format(new Date(sunday.getTime() + index * 24 * 60 * 60 * 1000)),
    );
  }

  function localTodayIso() {
    const now = new Date();
    return `${now.getFullYear()}-${pad2(now.getMonth() + 1)}-${pad2(now.getDate())}`;
  }

  function formatWeekRange(startIso, endIso) {
    if (!startIso || !endIso) return "";
    return `${formatShortMonthDay(startIso)} ~ ${formatShortMonthDay(endIso)}`;
  }

  function computeGenerateLabel() {
    const modeLabel =
      state.config.mode === "draft-update" ? t("generate.draft") : t("generate.finalize");
    const iso = state.config.targetDate;
    if (!iso) return modeLabel;
    if (iso === localTodayIso()) {
      return state.config.mode === "draft-update"
        ? t("generate.todayDraft")
        : t("generate.todayFinalize");
    }
    return `${formatShortMonthDay(iso)} ${modeLabel}`;
  }

  function refreshGenerateLabel() {
    const label = document.querySelector(".cta__label");
    if (!label || state.busy) return;
    if (state.codex.loaded && !state.codex.connected) {
      label.textContent = t("generate.connect");
      return;
    }
    label.textContent = computeGenerateLabel();
  }

  function syncGenerateButton() {
    const btn = document.querySelector(".cta");
    if (!btn) return;
    const unavailable = state.codex.loaded && !state.codex.connected;
    btn.disabled = state.busy || unavailable;
    btn.title = unavailable ? t("generate.connectTitle") : "";
    refreshGenerateLabel();
  }

  function extractHashtags(structured) {
    const source =
      (structured?.diary || []).join(" ") +
      " " +
      (structured?.report?.reflection || "") +
      " " +
      (structured?.report?.today || "");
    const set = new Set();
    const regex = /#([0-9A-Za-z가-힣_]{2,12})/g;
    let match;
    while ((match = regex.exec(source)) !== null) {
      set.add(match[1]);
      if (set.size >= 6) break;
    }
    if (set.size) return Array.from(set);
    const seeds = [];
    if (structured?.report?.today) seeds.push(currentUiLanguage() === "ko" ? "오늘기록" : "today");
    if (structured?.report?.decisions?.length) seeds.push(currentUiLanguage() === "ko" ? "결정" : "decisions");
    if (structured?.report?.blockers?.length) seeds.push(currentUiLanguage() === "ko" ? "고민" : "blockers");
    if (structured?.report?.tomorrow?.length) seeds.push(currentUiLanguage() === "ko" ? "내일할일" : "tomorrow");
    if (structured?.has_diary) seeds.push(currentUiLanguage() === "ko" ? "일기" : "diary");
    return seeds.slice(0, 4);
  }

  function firstSentence(text) {
    if (!text) return "";
    const trimmed = text.trim();
    const match = trimmed.match(/[^。.!?\n]+[。.!?]?/);
    return (match ? match[0] : trimmed).trim();
  }

  /* Local storage helpers ---------------------------------------------- */
  function readStorage(key) {
    try {
      const raw = localStorage.getItem(key);
      if (!raw) return {};
      return JSON.parse(raw);
    } catch {
      return {};
    }
  }

  function writeStorage(key, value) {
    try {
      localStorage.setItem(key, JSON.stringify(value));
    } catch {
      /* ignore */
    }
  }

  function readTextStorage(key) {
    try {
      return localStorage.getItem(key) || "";
    } catch {
      return "";
    }
  }

  function writeTextStorage(key, value) {
    try {
      if (value) localStorage.setItem(key, value);
      else localStorage.removeItem(key);
    } catch {
      /* ignore */
    }
  }

  function injectRuntimeStyles() {
    if (document.getElementById(RUNTIME_STYLE_ID)) return;
    const style = document.createElement("style");
    style.id = RUNTIME_STYLE_ID;
    style.textContent = `
      .setting__row--stack {
        align-items: stretch;
      }

      .language-select {
        width: 100%;
        min-width: 0;
        border: 1px solid var(--border);
        border-radius: 12px;
        background: #fff;
        color: var(--ink);
        padding: 11px 13px;
        font-size: 13px;
      }

      .cal-grid {
        gap: 4px;
      }

      .cal-cell {
        min-height: 58px;
        aspect-ratio: auto;
        align-items: stretch;
        justify-content: flex-start;
        gap: 6px;
        padding: 7px 8px;
        border-radius: 12px;
      }

      .cal-cell__top {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 6px;
        width: 100%;
      }

      .cal-cell__day {
        font-size: 12px;
        line-height: 1;
      }

      .cal-cell__dot {
        width: 8px;
        height: 8px;
        border-radius: 999px;
        background: var(--entry-accent, var(--accent));
        flex-shrink: 0;
      }

      .cal-cell__mood {
        align-self: flex-end;
        margin-top: auto;
        font-size: 15px;
        line-height: 1;
      }

      .cal-cell.has-entry,
      .cal-cell.has-mood {
        background: var(--entry-surface, #fff);
        border-color: var(--entry-border, var(--border));
        color: var(--entry-accent, var(--accent-strong));
      }

      .cal-cell.is-active {
        background: var(--entry-surface, #fff);
        color: var(--entry-accent, var(--accent-strong));
        border-color: var(--entry-accent, var(--accent));
        box-shadow: 0 0 0 2px var(--entry-accent, var(--accent)) inset,
          0 6px 14px rgba(88, 72, 63, 0.1);
      }

      .cal-cell.is-active .cal-cell__dot {
        background: currentColor;
      }

      .side-date__title-row {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 10px;
      }

      .side-date.has-entry,
      .side-date.has-mood {
        border-left: 3px solid var(--entry-accent, var(--border));
        background: linear-gradient(90deg, var(--entry-surface, #fff) 0px, #fff 42px);
      }

      .side-date.is-active {
        box-shadow: 0 0 0 2px var(--entry-accent, var(--accent)) inset;
      }

      .side-date__mood {
        width: 24px;
        height: 24px;
        border-radius: 999px;
        background: rgba(255, 255, 255, 0.9);
        display: inline-flex;
        align-items: center;
        justify-content: center;
        font-size: 14px;
        line-height: 1;
        flex-shrink: 0;
      }

    `;
    document.head.appendChild(style);
  }

  function ensureLanguageSetting() {
    const panel = $("#settings-panel");
    if (!panel || $("#output-language")) return;
    const autoSaveSetting = $("#auto-save") ? $("#auto-save").closest(".setting") : null;
    const languageSetting = el("label", { class: "setting", dataset: { setting: "output-language" } }, [
      el("span", {}, t("settings.languageLabel")),
      el("div", { class: "setting__row setting__row--stack" }, [
        el(
          "select",
          {
            id: "output-language",
            class: "language-select",
            "aria-label": t("settings.languageLabel"),
          },
          OUTPUT_LANGUAGES.map((option) =>
            el("option", { value: option.key }, option.label),
          ),
        ),
      ]),
      el("span", { class: "setting__hint" }, t("settings.languageHint")),
    ]);
    if (autoSaveSetting) panel.insertBefore(languageSetting, autoSaveSetting);
    else panel.appendChild(languageSetting);
  }

  function installRuntimeUi() {
    injectRuntimeStyles();
    ensureLanguageSetting();
  }

  function applyStaticUiCopy() {
    document.documentElement.lang = currentUiLanguage();
    document.title = t("app.title");

    const setText = (selector, key, params = {}) => {
      const node = document.querySelector(selector);
      if (node) node.textContent = t(key, params);
    };
    const setHtml = (selector, key, params = {}) => {
      const node = document.querySelector(selector);
      if (node) node.innerHTML = t(key, params);
    };
    const setTitle = (selector, key, params = {}) => {
      const node = document.querySelector(selector);
      if (node) node.title = t(key, params);
    };
    const setAria = (selector, key, params = {}) => {
      const node = document.querySelector(selector);
      if (node) node.setAttribute("aria-label", t(key, params));
    };

    setText(".brand__sub", "brand.sub");
    setText('.side-nav__item[data-nav="diary"] span:last-child', "nav.diary");
    setText('.side-nav__item[data-nav="calendar"] span:last-child', "nav.calendar");
    setText('.side-nav__item[data-nav="archive"] span:last-child', "nav.archive");
    setText(".side-section .side-section__head span:first-child", "side.recent");
    setText(".side-section--weeks .side-section__head span:first-child", "side.weekly");
    setHtml(".side-quote__text", "quote.html");
    setText(".side-settings span:last-child", "settings.title");

    setTitle('[data-action="date-prev"]', "action.prevDay");
    setTitle('[data-action="date-next"]', "action.nextDay");
    setTitle('[data-action="open-picker"]', "action.pickDate");
    setAria("#date-input", "action.pickDate");
    setText(".paper__date-label", "date.label");
    setText('[data-action="jump-today"]', "action.today");
    setTitle('[data-action="toggle-menu"]', "action.more");

    setText('input[name="view"][value="diary"] + span', "view.diary");
    setText('input[name="view"][value="report"] + span', "view.report");
    setText('input[name="view"][value="raw"] + span', "view.raw");

    setText('[data-action="view-week"]', "menu.viewWeek");
    setText('[data-action="copy"]', "menu.copy");
    setText('[data-action="open-external"]', "menu.external");

    setAria("#settings-panel", "settings.panelAria");
    setText(".settings__eyebrow", "settings.eyebrow");
    setText(".settings__title", "settings.title");
    setTitle('#settings-panel [data-action="toggle-settings"]', "action.close");
    setAria(".settings__intro", "settings.summaryAria");
    setText(".settings__intro-copy strong", "settings.summaryStrong");
    setText(".settings__intro-copy p", "settings.summaryCopy");
    setText("#settings-output-title", "settings.outputSection");
    setText("#settings-paths-title", "settings.pathsSection");

    const languageSetting = $("#output-language")?.closest(".setting");
    if (languageSetting) {
      const label = languageSetting.querySelector("span");
      const hint = languageSetting.querySelector(".setting__hint");
      if (label) label.textContent = t("settings.languageLabel");
      if (hint) hint.textContent = t("settings.languageHint");
    }

    const boundarySetting = $("#boundary-label")?.closest(".setting");
    if (boundarySetting) {
      const label = boundarySetting.querySelector("span");
      const hint = boundarySetting.querySelector(".setting__hint");
      if (label) label.textContent = t("settings.boundaryLabel");
      if (hint) hint.textContent = t("settings.boundaryHint");
    }

    const modeSetting = document.querySelector('input[name="mode"][value="finalize"]')?.closest(".setting");
    if (modeSetting) {
      const label = modeSetting.querySelector("span");
      if (label) label.textContent = t("settings.modeLabel");
      const finalize = modeSetting.querySelector('input[name="mode"][value="finalize"] + span');
      const draft = modeSetting.querySelector('input[name="mode"][value="draft-update"] + span');
      if (finalize) finalize.textContent = t("settings.modeFinalize");
      if (draft) draft.textContent = t("settings.modeDraft");
    }

    const autoSaveSetting = $("#auto-save")?.closest(".setting");
    if (autoSaveSetting) {
      const title = autoSaveSetting.querySelector(".setting__check-title");
      const hint = autoSaveSetting.querySelector(".setting__hint");
      if (title) title.textContent = t("settings.autoSaveTitle");
      if (hint) hint.textContent = t("settings.autoSaveHint");
    }

    const sourceSetting = $("#source-path")?.closest(".setting");
    if (sourceSetting) {
      const label = sourceSetting.querySelector("span");
      const button = sourceSetting.querySelector("button");
      if (label) label.textContent = t("settings.sourceLabel");
      if (button) button.textContent = t("action.change");
    }

    const outSetting = $("#out-path")?.closest(".setting");
    if (outSetting) {
      const label = outSetting.querySelector("span");
      const button = outSetting.querySelector("button");
      if (label) label.textContent = t("settings.outputLabel");
      if (button) button.textContent = t("action.change");
    }

    const introBadge = document.querySelector(".settings__intro-badge");
    if (introBadge) introBadge.textContent = t("settings.introBadge", { language: getOutputLanguageOption().label });
  }

  function normalizeLanguageKey(value) {
    if (value === null || value === undefined) return null;
    const raw = String(value).trim().toLowerCase();
    if (!raw) return null;

    const aliasMap = {
      english: "en",
      korean: "ko",
      japanese: "ja",
      chinese: "zh",
      french: "fr",
      german: "de",
      spanish: "es",
      vietnamese: "vi",
      thai: "th",
      russian: "ru",
      hindi: "hi",
      "en-us": "en",
      "ko-kr": "ko",
      "ja-jp": "ja",
      "zh-cn": "zh",
      "fr-fr": "fr",
      "de-de": "de",
      "es-es": "es",
      "vi-vn": "vi",
      "th-th": "th",
      "ru-ru": "ru",
      "hi-in": "hi",
    };

    const direct = OUTPUT_LANGUAGES.find(
      (option) =>
        option.key === raw ||
        option.label.toLowerCase() === raw ||
        option.locale.toLowerCase() === raw,
    );
    if (direct) return direct.key;
    return aliasMap[raw] || null;
  }

  function getOutputLanguageOption(value = state.config.outputLanguage) {
    const key = normalizeLanguageKey(value) || DEFAULT_OUTPUT_LANGUAGE;
    return OUTPUT_LANGUAGES.find((option) => option.key === key) || OUTPUT_LANGUAGES[0];
  }

  function setOutputLanguage(value, { persist = true } = {}) {
    const option = getOutputLanguageOption(value);
    state.config.outputLanguage = option.key;
    if (persist) writeTextStorage(OUTPUT_LANGUAGE_KEY, option.key);
    applyStaticUiCopy();
    renderConfig();
    renderSideDates();
    renderStage();
  }

  function hydrateClientPreferences() {
    const storedLanguage = normalizeLanguageKey(readTextStorage(OUTPUT_LANGUAGE_KEY));
    state.config.outputLanguage = storedLanguage || DEFAULT_OUTPUT_LANGUAGE;
  }

  function currentLanguagePayload() {
    const option = getOutputLanguageOption();
    return {
      output_language: option.label,
      output_language_code: option.key,
      target_language: option.label,
      target_language_code: option.key,
      preferred_language: option.label,
      preferred_language_code: option.key,
      language: option.label,
      language_code: option.key,
      locale: option.locale,
    };
  }

  function findMoodOption(moodKey) {
    const option = MOOD_OPTIONS.find((item) => item.key === moodKey);
    return option ? { ...option, label: moodLabel(option.key) } : null;
  }

  function hashIso(iso) {
    return Array.from(String(iso || "")).reduce(
      (acc, ch) => ((acc << 5) - acc + ch.charCodeAt(0)) | 0,
      0,
    );
  }

  function setCalendarCursor(iso) {
    const month = monthOf(iso);
    if (!month) return;
    state.calendarCursor = `${month.year}-${pad2(month.month + 1)}-01`;
  }

  function dateTone(iso, moodKey) {
    if (moodKey && MOOD_TONES[moodKey]) return MOOD_TONES[moodKey];
    return ENTRY_TONES[Math.abs(hashIso(iso)) % ENTRY_TONES.length];
  }

  function toneStyle(iso, moodKey) {
    const tone = dateTone(iso, moodKey);
    return `--entry-accent:${tone.accent}; --entry-surface:${tone.surface}; --entry-border:${tone.border};`;
  }

  function dateVisualMeta(iso, { saved = false } = {}) {
    const mood = findMoodOption(getMood(iso));
    const style = saved || mood ? toneStyle(iso, mood?.key) : "";
    return { mood, style };
  }

  function dateTitleText(iso, { saved = false, mood = null } = {}) {
    const parts = [formatDisplayDate(iso)];
    if (saved) parts.push(t("saved.diary"));
    if (mood) parts.push(`${t("mood.label")} ${mood.emoji} ${mood.label}`);
    return parts.join(" · ");
  }

  function getMood(iso) {
    if (!iso) return null;
    const all = readStorage(MOOD_KEY);
    return all[iso] || null;
  }

  function setMood(iso, moodKey) {
    if (!iso) return;
    const all = readStorage(MOOD_KEY);
    if (moodKey) all[iso] = moodKey;
    else delete all[iso];
    writeStorage(MOOD_KEY, all);
  }

  function getMemo(iso) {
    if (!iso) return "";
    const all = readStorage(MEMO_KEY);
    return all[iso] || "";
  }

  function setMemo(iso, text) {
    if (!iso) return;
    const all = readStorage(MEMO_KEY);
    if (text) all[iso] = text;
    else delete all[iso];
    writeStorage(MEMO_KEY, all);
  }

  /* Stage --------------------------------------------------------------- */
  function renderStage() {
    const stage = $("#stage");
    if (state.menuOpen) toggleMenu(false);
    stage.innerHTML = "";

    if (state.nav === "calendar") {
      stage.appendChild(renderCalendar());
      return;
    }

    if (state.nav === "archive") {
      stage.appendChild(renderArchive());
      return;
    }

    if (state.codex.loaded && !state.codex.connected && !state.data) {
      stage.appendChild(renderConnectionPrompt());
      return;
    }

    if (!state.data) {
      stage.appendChild(renderEmpty());
      return;
    }

    const payload = state.data;
    const structured = payload.structured;
    const viewKey = state.view;

    if (viewKey === "raw") {
      stage.appendChild(renderRaw(payload.views_html?.full || ""));
      return;
    }

    if (viewKey === "report") {
      if (structured?.has_report) {
        stage.appendChild(renderReport(structured.report));
      } else if (payload.views_html?.report) {
        stage.appendChild(renderRaw(payload.views_html.report));
      } else {
        stage.appendChild(renderViewEmpty(t("empty.report")));
      }
      return;
    }

    // diary (default)
    if (structured?.has_diary) {
      stage.appendChild(renderDiary(structured, payload));
    } else if (payload.views_html?.diary) {
      stage.appendChild(renderRaw(payload.views_html.diary));
    } else if (payload.views_html?.full) {
      stage.appendChild(renderRaw(payload.views_html.full));
    } else {
      stage.appendChild(renderViewEmpty(t("empty.diary")));
    }
  }

  function renderEmpty() {
    const mascot = el("div", { class: "empty__mascot" });
    const img = document.createElement("img");
    img.src = "assets/mascot-empty.png";
    img.alt = "";
    img.onerror = () => img.replaceWith(window.__mascotSvg("empty"));
    mascot.appendChild(img);

    const iso = state.selectedDateIso || state.config.targetDate;
    const hasTargetDate = Boolean(iso);
    const title = hasTargetDate
      ? t("empty.titleWithDate", { date: formatDisplayDate(iso) })
      : t("empty.titleToday");
    const copy = hasTargetDate
      ? t("empty.copyWithDate", { language: getOutputLanguageOption().label })
      : t("empty.copyToday");

    return el("section", { class: "empty" }, [
      mascot,
      el("h2", { class: "empty__title" }, [
        document.createTextNode(title),
        el("span", { class: "empty__heart" }, " ♡"),
      ]),
      el("p", { class: "empty__copy" }, copy),
    ]);
  }

  function renderViewEmpty(message) {
    return el("section", { class: "empty" }, [
      el("p", { class: "empty__copy" }, message),
    ]);
  }

  /* Diary view ---------------------------------------------------------- */
  function renderDiary(structured, payload) {
    const iso = payload?.target_date || state.selectedDateIso || state.config.targetDate;

    const headMascot = el("span", { class: "diary__mascot" });
    const headImg = document.createElement("img");
    headImg.src = "assets/app-icon.png";
    headImg.alt = "";
    headImg.onerror = () => headImg.replaceWith(window.__mascotSvg("header"));
    headMascot.appendChild(headImg);

    const head = el("div", { class: "diary__head" }, [
      el("div", { class: "diary__heading" }, [
        headMascot,
        document.createTextNode(t("diary.title")),
        el("span", { class: "diary__heart" }, "♡"),
      ]),
      renderMoodRow(iso),
    ]);

    const paragraphs = (structured.diary || []).map((para) => el("p", {}, para));
    const prose = el("div", { class: "diary__prose" }, paragraphs);

    const sideart = el("div", { class: "diary__sideart" });
    const sideImg = document.createElement("img");
    sideImg.src = "assets/mascot-diary.png";
    sideImg.alt = "";
    sideImg.onerror = () => sideImg.replaceWith(window.__mascotSvg("diary"));
    sideart.appendChild(sideImg);

    const body = el("div", { class: "diary__body" }, [prose, sideart]);

    return el("section", { class: "diary" }, [
      head,
      structured.intro_quote
        ? el("blockquote", { class: "reflection" }, structured.intro_quote)
        : null,
      el("hr", { class: "diary__divider" }),
      body,
      renderHashtagRow(structured),
      renderSummaryCard(structured),
      renderMemoCard(iso),
      renderDiaryFoot(payload),
    ]);
  }

  function renderMoodRow(iso) {
    const current = getMood(iso);
    const options = el("div", { class: "mood__options" });
    MOOD_OPTIONS.forEach((opt) => {
      const localized = findMoodOption(opt.key) || opt;
      const active = current === opt.key;
      const btn = el(
        "button",
        {
          type: "button",
          class: `mood__btn ${active ? "is-selected" : ""}`,
          title: localized.label,
          "aria-label": localized.label,
          onClick: () => {
            const next = current === opt.key ? null : opt.key;
            setMood(iso, next);
            renderSideDates();
            renderStage();
          },
        },
        opt.emoji,
      );
      options.appendChild(btn);
    });
    return el("div", { class: "mood" }, [
      el("span", { class: "mood__label" }, t("mood.label")),
      options,
    ]);
  }

  function renderHashtagRow(structured) {
    const tags = extractHashtags(structured);
    if (!tags.length) return null;
    const row = el("div", { class: "hashtags" });
    tags.forEach((tag) => {
      row.appendChild(el("span", { class: "hashtag" }, `#${tag}`));
    });
    return row;
  }

  function renderSummaryCard(structured) {
    const source =
      structured?.report?.reflection ||
      (structured?.diary || [])[0] ||
      structured?.report?.today ||
      "";
    const sentence = firstSentence(source);
    if (!sentence) return null;
    return el("section", { class: "summary" }, [
      el("span", { class: "summary__label" }, t("summary.label")),
      el("div", { class: "summary__text" }, sentence),
    ]);
  }

  function renderMemoCard(iso) {
    const current = getMemo(iso);
    const input = el("input", {
      class: "memo__input",
      type: "text",
      placeholder: t("memo.placeholder"),
      value: current,
    });

    const saveBtn = el(
      "button",
      {
        type: "button",
        class: "memo__save",
        onClick: () => {
          setMemo(iso, input.value.trim());
          showToast(t("memo.saved"));
        },
      },
      t("memo.save"),
    );

    return el("section", { class: "memo" }, [
      el("span", { class: "memo__icon" }, "✏️"),
      input,
      saveBtn,
    ]);
  }

  function renderDiaryFoot(payload) {
    const saved = payload?.saved_path ? t("foot.saved") : t("foot.preview");
    const mode = payload?.mode === "finalize" ? t("foot.modeFinalize") : t("foot.modeDraft");
    const time = new Date().toLocaleTimeString(currentUiLocale(), {
      hour: "2-digit",
      minute: "2-digit",
    });
    return el("div", { class: "diary__foot" }, `${t("foot.writtenAt")} · ${time} · ${mode} · ${saved}`);
  }

  /* Report view --------------------------------------------------------- */
  function renderReport(report) {
    const container = el("section", { class: "report" });

    if (report.today) {
      container.appendChild(
        reportCard({
          icon: "✺",
          tone: "accent",
          title: t("report.today"),
          body: el("div", { class: "card__body" }, [el("p", {}, report.today)]),
        }),
      );
    }

    if (report.timeline?.length) {
      container.appendChild(renderTimelineCard(report.timeline));
    }

    if (report.decisions?.length) {
      container.appendChild(
        reportCard({
          icon: "◆",
          tone: "accent",
          title: t("report.highlights"),
          subtitle: t("saved.records", { count: report.decisions.length }),
          body: renderBulletList(report.decisions),
        }),
      );
    }

    if (report.blockers?.length) {
      container.appendChild(
        reportCard({
          icon: "!",
          tone: "danger",
          title: t("report.blockers"),
          subtitle: t("saved.records", { count: report.blockers.length }),
          body: renderBulletList(report.blockers, "bullet-list--danger"),
        }),
      );
    }

    if (report.tomorrow?.length) {
      container.appendChild(
        reportCard({
          icon: "→",
          tone: "warm",
          title: t("report.tomorrow"),
          subtitle: t("saved.records", { count: report.tomorrow.length }),
          body: renderTodoList(report.tomorrow),
        }),
      );
    }

    if (report.reflection) {
      container.appendChild(
        el("section", { class: "reflection" }, [
          el("div", { class: "reflection__label" }, t("report.reflection")),
          el("p", { class: "reflection__text" }, report.reflection),
        ]),
      );
    }

    return container;
  }

  function reportCard({ icon, tone = "accent", title, subtitle, body }) {
    const head = el("header", { class: "card__head" }, [
      el("div", { class: `card__badge card__badge--${tone}` }, icon),
      el("div", { class: "card__title" }, title),
      subtitle ? el("div", { class: "card__subtitle" }, subtitle) : null,
    ]);
    return el("section", { class: "card" }, [head, body]);
  }

  function renderBulletList(items, modifier = "") {
    const ul = el("ul", { class: `bullet-list ${modifier}`.trim() });
    items.forEach((item) => ul.appendChild(el("li", {}, item)));
    return ul;
  }

  function renderTodoList(items) {
    const ul = el("ul", { class: "todo-list" });
    items.forEach((item) =>
      ul.appendChild(
        el("li", {}, [el("span", { class: "todo-check" }), el("span", {}, item)]),
      ),
    );
    return ul;
  }

  function renderTimelineCard(items) {
    const total = items.length;
    const visibleCount = Math.max(
      TIMELINE_PREVIEW,
      Math.min(total, Number(state.timelineVisibleCount) || TIMELINE_PREVIEW),
    );
    const remaining = Math.max(0, total - visibleCount);
    const isExpanded = visibleCount > TIMELINE_PREVIEW;
    const isFullyExpanded = visibleCount >= total;
    const visible = items.slice(0, visibleCount);

    const actions = el("div", { class: "timeline__actions" });
    if (!isFullyExpanded) {
      const step = Math.min(TIMELINE_STEP, remaining);
      actions.appendChild(
        el(
          "button",
          {
            type: "button",
            class: "card__action timeline-toggle",
            onClick: () => {
              state.timelineVisibleCount = Math.min(total, visibleCount + TIMELINE_STEP);
              renderStage();
            },
          },
          t("timeline.more", { count: step }),
        ),
      );
      if (remaining > step) {
        actions.appendChild(
          el(
            "button",
            {
              type: "button",
              class: "card__action timeline-toggle",
              onClick: () => {
              state.timelineVisibleCount = total;
              renderStage();
            },
          },
            t("timeline.all", { count: total }),
          ),
        );
      }
    }
    if (isExpanded) {
      actions.appendChild(
        el(
          "button",
          {
            type: "button",
            class: "card__action timeline-toggle timeline-toggle--ghost",
            onClick: () => {
              state.timelineVisibleCount = TIMELINE_PREVIEW;
              renderStage();
            },
          },
          t("timeline.collapse"),
        ),
      );
    }

    const timeline = el(
      "div",
      { class: `timeline ${isExpanded ? "is-open" : "is-preview"}` },
      visible.map((item) =>
        el("div", { class: "timeline__item" }, [
          el("div", { class: "timeline__time" }, item.time || "•"),
          el("div", { class: "timeline__text" }, item.text),
        ]),
      ),
    );

    const head = el("header", { class: "card__head" }, [
      el("div", { class: "card__badge card__badge--accent" }, "⏱"),
      el("div", { class: "card__title" }, t("timeline.title")),
      actions,
    ]);

    const section = el("section", { class: "card timeline-card" }, [head, timeline]);
    if (remaining > 0) {
      section.appendChild(
        el(
          "div",
          { class: "timeline__more" },
          t("timeline.status", { visible: visibleCount, remaining }),
        ),
      );
    }
    return section;
  }

  /* Raw view ------------------------------------------------------------ */
  function renderRaw(html) {
    const section = el("section", { class: "raw" });
    section.innerHTML = html || "";
    return section;
  }

  /* Calendar view ------------------------------------------------------- */
  function pad2(n) {
    return String(n).padStart(2, "0");
  }

  function monthOf(iso) {
    const d = new Date(`${iso}T12:00:00`);
    if (Number.isNaN(d.getTime())) return null;
    return { year: d.getFullYear(), month: d.getMonth() };
  }

  function renderCalendar() {
    const root = el("section", { class: "calendar" });
    const anchorIso =
      state.calendarCursor ||
      state.selectedDateIso ||
      state.config.targetDate ||
      state.dates[0]?.date ||
      localTodayIso();
    const cursor = monthOf(anchorIso) || { year: new Date().getFullYear(), month: new Date().getMonth() };

    const savedSet = new Set(state.dates.map((item) => item.date));

    const prevBtn = el(
      "button",
      {
        type: "button",
        class: "calendar__nav",
        onClick: () => {
          const d = new Date(cursor.year, cursor.month - 1, 1);
          state.calendarCursor = `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-01`;
          renderStage();
        },
      },
      "‹",
    );
    const nextBtn = el(
      "button",
      {
        type: "button",
        class: "calendar__nav",
        onClick: () => {
          const d = new Date(cursor.year, cursor.month + 1, 1);
          state.calendarCursor = `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-01`;
          renderStage();
        },
      },
      "›",
    );

    const head = el("header", { class: "calendar__head" }, [
      prevBtn,
      el(
        "div",
        { class: "calendar__title" },
        formatMonthYear(cursor.year, cursor.month),
      ),
      nextBtn,
      el(
        "div",
        { class: "calendar__count" },
        t("calendar.savedCount", { count: state.dates.length }),
      ),
    ]);
    root.appendChild(head);

    const weekdayRow = el("div", { class: "cal-weekdays" });
    weekdayLabels().forEach((label, idx) => {
      weekdayRow.appendChild(
        el(
          "div",
          { class: `cal-weekdays__cell ${idx === 0 ? "is-sun" : idx === 6 ? "is-sat" : ""}` },
          label,
        ),
      );
    });
    root.appendChild(weekdayRow);

    const grid = el("div", { class: "cal-grid" });
    const firstDay = new Date(cursor.year, cursor.month, 1);
    const leadingBlanks = firstDay.getDay(); // 0=Sun
    const daysInMonth = new Date(cursor.year, cursor.month + 1, 0).getDate();

    for (let i = 0; i < leadingBlanks; i += 1) {
      grid.appendChild(el("div", { class: "cal-cell cal-cell--blank" }));
    }

    for (let day = 1; day <= daysInMonth; day += 1) {
      const iso = `${cursor.year}-${pad2(cursor.month + 1)}-${pad2(day)}`;
      const saved = savedSet.has(iso);
      const meta = dateVisualMeta(iso, { saved });
      const active = iso === (state.selectedDateIso || state.config.targetDate);
      const today = iso === localTodayIso();
      const classes = [
        "cal-cell",
        saved ? "has-entry" : "",
        meta.mood ? "has-mood" : "",
        active ? "is-active" : "",
        today ? "is-today" : "",
      ]
        .filter(Boolean)
        .join(" ");
      grid.appendChild(
        el(
          "button",
          {
            type: "button",
            class: classes,
            style: meta.style || null,
            title: dateTitleText(iso, { saved, mood: meta.mood }),
            onClick: () => {
              if (saved) {
                state.nav = "diary";
                setNavActive();
                openDate(iso);
              } else {
                state.data = null;
                state.selectedDateIso = iso;
                state.selectedWeekStart = null;
                state.view = "diary";
                state.config.targetDate = iso;
                setCalendarCursor(iso);
                renderConfig();
                renderSideDates();
                renderStage();
                setFooter(
                  t("footer.noSavedForDateCalendar", {
                    date: formatDisplayDate(iso),
                    language: getOutputLanguageOption().label,
                  }),
                );
                setWarning("");
              }
            },
          },
          [
            el("span", { class: "cal-cell__top" }, [
              el("span", { class: "cal-cell__day" }, String(day)),
              saved ? el("span", { class: "cal-cell__dot" }, "") : null,
            ]),
            meta.mood ? el("span", { class: "cal-cell__mood" }, meta.mood.emoji) : null,
          ],
        ),
      );
    }

    root.appendChild(grid);

    if (state.weeks.length) {
      root.appendChild(
        el("div", { class: "calendar__sub" }, t("calendar.weekSection")),
      );
      const weeks = el("div", { class: "calendar__weeks" });
      state.weeks.slice(0, 12).forEach((week) => {
        weeks.appendChild(
          el(
            "button",
            {
              type: "button",
              class: `week-card ${week.start === state.selectedWeekStart ? "is-active" : ""}`,
              onClick: () => {
                state.nav = "diary";
                setNavActive();
                openWeek(week.start);
              },
            },
            [
              el(
                "div",
                { class: "week-card__range" },
                `${week.start.slice(5)} ~ ${week.end.slice(5)}`,
              ),
              el("div", { class: "week-card__meta" }, t("calendar.weekRecords", { count: week.count })),
            ],
          ),
        );
      });
      root.appendChild(weeks);
    }

    return root;
  }

  function renderArchive() {
    const root = el("section", { class: "archive" });
    root.appendChild(
      el("header", { class: "archive__head" }, [
        el("div", { class: "archive__eyebrow" }, t("archive.eyebrow")),
        el("h2", { class: "archive__title" }, t("archive.title")),
        el(
          "p",
          { class: "archive__copy" },
          t("archive.copy"),
        ),
      ]),
    );

    const grid = el("div", { class: "archive__grid" });

    const dailySection = el("section", { class: "archive__section" }, [
      el("div", { class: "archive__section-label" }, t("archive.recentSection", { count: state.dates.length })),
    ]);
    const dailyList = el("div", { class: "archive__list" });
    if (!state.dates.length) {
      dailyList.appendChild(
        el("div", { class: "archive__empty" }, t("archive.emptyDaily")),
      );
    } else {
      state.dates.slice(0, 18).forEach((item) => {
        const active = item.date === state.selectedDateIso;
        const meta = dateVisualMeta(item.date, { saved: true });
        dailyList.appendChild(
          el(
            "button",
            {
              type: "button",
              class: `archive-item ${active ? "is-active" : ""}`,
              style: meta.style || null,
              title: dateTitleText(item.date, { saved: true, mood: meta.mood }),
              onClick: () => {
                state.nav = "diary";
                setNavActive();
                openDate(item.date);
              },
            },
            [
              el("div", { class: "archive-item__head" }, [
                el("div", { class: "archive-item__title" }, formatDisplayDate(item.date)),
                meta.mood
                  ? el("span", { class: "archive-item__mood", title: meta.mood.label }, meta.mood.emoji)
                  : null,
              ]),
              el(
                "div",
                { class: "archive-item__caption" },
                `${item.date} · ${formatWeekday(item.date)}`,
              ),
            ],
          ),
        );
      });
    }
    dailySection.appendChild(dailyList);
    grid.appendChild(dailySection);

    const weeklySection = el("section", { class: "archive__section" }, [
      el("div", { class: "archive__section-label" }, t("archive.weeklySection", { count: state.weeks.length })),
    ]);
    const weekList = el("div", { class: "archive__list" });
    if (!state.weeks.length) {
      weekList.appendChild(
        el("div", { class: "archive__empty" }, t("archive.emptyWeekly")),
      );
    } else {
      state.weeks.slice(0, 12).forEach((week) => {
        const active = week.start === state.selectedWeekStart;
        weekList.appendChild(
          el(
            "button",
            {
              type: "button",
              class: `archive-item archive-item--week ${active ? "is-active" : ""}`,
              onClick: () => {
                state.nav = "diary";
                setNavActive();
                openWeek(week.start);
              },
            },
            [
              el("div", { class: "archive-item__head" }, [
                el("div", { class: "archive-item__title" }, formatWeekRange(week.start, week.end)),
              ]),
              el(
                "div",
                { class: "archive-item__caption" },
                `${t("saved.records", { count: week.count })} · ${week.label || `${week.start} ~ ${week.end}`}`,
              ),
            ],
          ),
        );
      });
    }
    weeklySection.appendChild(weekList);
    grid.appendChild(weeklySection);

    root.appendChild(grid);
    return root;
  }

  /* Sidebar ------------------------------------------------------------- */
  function renderSideDates() {
    const dateList = $("#date-list");
    const weekList = $("#week-list");
    const dateCount = $("#date-count");
    const weekCount = $("#week-count");
    dateList.innerHTML = "";
    if (weekList) weekList.innerHTML = "";
    if (dateCount) dateCount.textContent = String(state.dates.length);
    if (weekCount) weekCount.textContent = String(state.weeks.length);

    if (!state.dates.length) {
      dateList.appendChild(
        el("div", { class: "side-empty" }, t("side.emptyDaily")),
      );
    } else {
      state.dates.slice(0, 18).forEach((item) => {
        const active = item.date === state.selectedDateIso;
        const meta = dateVisualMeta(item.date, { saved: true });
        dateList.appendChild(
          el(
            "button",
            {
              type: "button",
              class: `side-date has-entry ${meta.mood ? "has-mood" : ""} ${active ? "is-active" : ""}`.trim(),
              style: meta.style || null,
              title: dateTitleText(item.date, { saved: true, mood: meta.mood }),
              onClick: () => {
                state.nav = "diary";
                setNavActive();
                openDate(item.date);
              },
            },
            [
              el("div", { class: "side-date__body" }, [
                el("div", { class: "side-date__title-row" }, [
                  el(
                    "div",
                    { class: "side-date__title" },
                    formatDisplayDate(item.date),
                  ),
                  meta.mood
                    ? el("span", { class: "side-date__mood", title: meta.mood.label }, meta.mood.emoji)
                    : null,
                ]),
                el(
                  "div",
                  { class: "side-date__caption" },
                  `${item.date} · ${formatWeekday(item.date)}${meta.mood ? ` · ${meta.mood.label}` : ""}`,
                ),
              ]),
            ],
          ),
        );
      });
    }

    if (!weekList) return;
    if (!state.weeks.length) {
      weekList.appendChild(el("div", { class: "side-empty" }, t("side.emptyWeekly")));
      return;
    }

    state.weeks.slice(0, 10).forEach((week) => {
      const active = week.start === state.selectedWeekStart;
      weekList.appendChild(
        el(
          "button",
          {
            type: "button",
            class: `side-date side-date--week ${active ? "is-active" : ""}`,
            onClick: () => {
              state.nav = "diary";
              setNavActive();
              openWeek(week.start);
            },
          },
          [
            el("div", { class: "side-date__body" }, [
              el("div", { class: "side-date__title" }, formatWeekRange(week.start, week.end)),
              el(
                "div",
                { class: "side-date__caption" },
                `${t("saved.records", { count: week.count })} · ${week.label || `${week.start} ~ ${week.end}`}`,
              ),
            ]),
          ],
        ),
      );
    });
  }

  function setNavActive() {
    document.querySelectorAll(".side-nav__item").forEach((btn) => {
      btn.classList.toggle("is-active", btn.dataset.nav === state.nav);
    });
  }

  /* Topbar / config ----------------------------------------------------- */
  function renderConfig() {
    const iso = state.config.targetDate;
    const dateMain = $("#date-main");
    const weekdayEl = $("#date-weekday");
    if (dateMain) dateMain.textContent = formatBigDate(iso);
    if (weekdayEl) weekdayEl.textContent = formatWeekday(iso) || "";

    const input = $("#date-input");
    if (input) input.value = iso || "";

    const boundaryLabel = $("#boundary-label");
    if (boundaryLabel)
      boundaryLabel.textContent = `${String(state.config.boundaryHour).padStart(2, "0")}시`;
    const boundaryChip = $("#boundary-chip");
    if (boundaryChip)
      boundaryChip.textContent = `${String(state.config.boundaryHour).padStart(2, "0")}시 기준`;

    const srcEl = $("#source-path");
    if (srcEl) {
      srcEl.textContent = state.config.sourceDir || "기본 폴더 사용";
      srcEl.title = state.config.sourceDir || "";
    }
    const outEl = $("#out-path");
    if (outEl) {
      outEl.textContent = state.config.outDir || "기본 폴더 사용";
      outEl.title = state.config.outDir || "";
    }

    const modeRadio = document.querySelector(
      `input[name="mode"][value="${state.config.mode}"]`,
    );
    if (modeRadio) modeRadio.checked = true;

    const autoSave = $("#auto-save");
    if (autoSave) autoSave.checked = state.config.autoSave;

    const languageSelect = $("#output-language");
    if (languageSelect) languageSelect.value = getOutputLanguageOption().key;
    const viewSegmented = $("#view-segmented");
    if (viewSegmented) {
      const hiddenOutsideDiary = state.nav !== "diary";
      viewSegmented.hidden = hiddenOutsideDiary;
      viewSegmented.setAttribute("aria-hidden", String(hiddenOutsideDiary));
    }
    const paperTop = document.querySelector(".paper__top");
    if (paperTop) {
      const hiddenOnCalendar = state.nav === "calendar";
      paperTop.hidden = hiddenOnCalendar;
      paperTop.setAttribute("aria-hidden", String(hiddenOnCalendar));
      if (hiddenOnCalendar && state.menuOpen) toggleMenu(false);
    }
    renderCodexStatus();
    syncGenerateButton();
  }

  function syncConfig(config) {
    if (!config) return;
    if (config.target_date) state.config.targetDate = config.target_date;
    if (typeof config.boundary_hour === "number")
      state.config.boundaryHour = config.boundary_hour;
    if (typeof config.source_dir === "string") state.config.sourceDir = config.source_dir;
    if (typeof config.out_dir === "string") state.config.outDir = config.out_dir;
    const language =
      normalizeLanguageKey(config.output_language_code) ||
      normalizeLanguageKey(config.target_language_code) ||
      normalizeLanguageKey(config.language_code) ||
      normalizeLanguageKey(config.output_language) ||
      normalizeLanguageKey(config.target_language) ||
      normalizeLanguageKey(config.preferred_language) ||
      normalizeLanguageKey(config.language) ||
      normalizeLanguageKey(config.locale);
    if (language) state.config.outputLanguage = language;
    renderConfig();
  }

  /* Status -------------------------------------------------------------- */
  function setFooter(text) {
    const foot = $("#foot-main");
    if (!foot) return;
    foot.innerHTML = "";
    foot.appendChild(el("span", { class: "paper__foot-icon" }, "💡"));
    foot.appendChild(el("span", {}, text));
  }

  function setWarning(text) {
    const warn = $("#status-warning");
    if (!warn) return;
    if (text) {
      warn.textContent = text;
      warn.hidden = false;
    } else {
      warn.hidden = true;
    }
  }

  function syncCodexStatus(codex) {
    if (!codex) return;
    state.codex = {
      loaded: true,
      available: Boolean(codex.available),
      connected: Boolean(codex.connected),
      connectable: Boolean(codex.connectable),
      message: codex.message || "",
      detail: codex.detail || "",
    };
    renderCodexStatus();
    syncGenerateButton();
  }

  function renderCodexStatus() {
    const host = $("#codex-status");
    if (!host) return;
    const codex = state.codex || {};
    const loaded = Boolean(codex.loaded);
    const connected = Boolean(codex.connected);
    const connectable = Boolean(codex.connectable);
    const status = connected
      ? "connected"
      : loaded
        ? "disconnected"
        : "loading";

    host.dataset.state = status;
    const dot = host.querySelector(".bridge-status__dot");
    if (dot) {
      dot.className = `bridge-status__dot is-${status}`;
    }

    const detailText = connected
      ? "일기 생성 준비가 끝났어요."
      : loaded
        ? codex.detail || "로그인이 필요해요."
        : "잠시만 기다려 주세요.";
    host.title = detailText;

    const text = host.querySelector(".bridge-status__text");
    if (text) {
      text.textContent = connected
        ? "Codex Ready"
        : loaded
          ? connectable
            ? "Connect Codex"
            : "Codex Check"
          : "Checking Codex";
    }

    const detail = host.querySelector(".bridge-status__detail");
    if (detail) {
      detail.textContent = detailText;
    }

    const action = host.querySelector(".bridge-status__action");
    if (action) {
      if (!loaded || connected) {
        action.hidden = true;
      } else {
        action.hidden = false;
        action.textContent = connectable ? "연결" : "확인";
        action.disabled = state.busy || !connectable;
      }
    }
  }

  function renderConnectionPrompt() {
    const codex = state.codex || {};
    const actionLabel = codex.connectable ? "Codex 연결" : "상태 확인";
    const body = codex.connected
      ? "Codex 연결 상태가 정상이라서, 이제 날짜를 고르면 바로 생성할 수 있어요."
      : codex.detail || "먼저 Codex 로그인 상태를 확인해야 해요.";

    const content = [
      el("div", { class: "empty__badge" }, "Codex"),
      el("h2", { class: "empty__title" }, [
        document.createTextNode("먼저 codex를 연결해주세요"),
      ]),
      el("p", { class: "empty__copy" }, body),
    ];

    if (codex.connectable) {
      content.push(
        el(
          "button",
          {
            type: "button",
            class: "empty__action",
            "data-action": "codex-connect",
          },
          actionLabel,
        ),
      );
    }

    return el("section", { class: "empty empty--connection" }, content);
  }

  function showToast(text) {
    let toast = document.querySelector(".toast");
    if (!toast) {
      toast = document.createElement("div");
      toast.className = "toast";
      document.body.appendChild(toast);
    }
    toast.textContent = text;
    toast.classList.add("is-visible");
    clearTimeout(showToast._t);
    showToast._t = setTimeout(() => toast.classList.remove("is-visible"), 1600);
  }

  function setBusy(busy) {
    state.busy = busy;
    const btn = document.querySelector(".cta");
    if (btn) {
      btn.disabled = busy || (state.codex.loaded && !state.codex.connected);
      const spinner = btn.querySelector(".spinner");
      const label = btn.querySelector(".cta__label");
      if (spinner) spinner.hidden = !busy;
      if (label) {
        label.textContent = busy
          ? "생성 중..."
          : state.codex.loaded && !state.codex.connected
            ? "Codex 연결 후 생성"
            : computeGenerateLabel();
      }
    }
    renderCodexStatus();
  }

  /* Actions ------------------------------------------------------------- */
  function withTimeout(promise, ms) {
    let timeoutId;
    const timer = new Promise((_, reject) => {
      timeoutId = setTimeout(
        () => reject(new Error(`응답이 ${Math.round(ms / 1000)}초 안에 오지 않아요. Chronicle 폴더가 올바른지 확인해 주세요.`)),
        ms,
      );
    });
    return Promise.race([promise, timer]).finally(() => clearTimeout(timeoutId));
  }

  async function generate() {
    const bridge = api();
    if (!bridge) {
      setWarning("WebView 브리지가 준비되지 않았어요.");
      return;
    }
    if (state.codex.loaded && !state.codex.connected) {
      state.data = null;
      renderStage();
      setFooter("먼저 Codex를 연결해 주세요.");
      setWarning("먼저 codex를 연결해주세요.");
      return;
    }
    if (state.busy) return;
    setBusy(true);
    toggleMenu(false);
    const language = getOutputLanguageOption();
    setFooter(`Chronicle 요약을 읽고 선택한 날짜의 기록을 ${language.label}로 만드는 중이에요...`);
    setWarning("");
    try {
      const payload = await withTimeout(
        bridge.generate({
          target_date: state.config.targetDate,
          boundary_hour: state.config.boundaryHour,
          mode: state.config.mode,
          source_dir: state.config.sourceDir,
          out_dir: state.config.outDir,
          auto_save: state.config.autoSave,
          ...currentLanguagePayload(),
        }),
        90000,
      );
      if (payload?.error) {
        setFooter("생성에 실패했어요.");
        setWarning(payload.error);
        return;
      }
      state.data = payload;
      state.config.targetDate = payload.target_date;
      state.selectedDateIso = payload.target_date;
      state.selectedWeekStart = null;
      state.view = "diary";
      state.nav = "diary";
      state.timelineVisibleCount = TIMELINE_PREVIEW;
      setCalendarCursor(payload.target_date);
      renderConfig();
      setNavActive();
      syncSegmented();
      renderStage();
      setFooter(
        `${formatKoreanDate(payload.target_date)} 일기를 ${language.label}로 바로 열었어요. ${payload.saved_path ? "자동 저장도 완료했어요." : ""}`,
      );
      if (payload.warnings?.length) setWarning(payload.warnings.join(" · "));
      refreshLists();
    } catch (err) {
      setFooter("생성에 실패했어요.");
      setWarning(String(err && err.message ? err.message : err));
    } finally {
      setBusy(false);
    }
  }

  async function connectCodex() {
    const bridge = api();
    if (!bridge) {
      setWarning("WebView 브리지가 준비되지 않았어요.");
      return;
    }
    if (!state.codex.loaded || !state.codex.connected) {
      setFooter("Codex 연결 상태를 확인하는 중이에요.");
    }
    setBusy(true);
    try {
      const payload = await bridge.connect_codex();
      if (payload?.error) {
        setWarning(payload.error);
        setFooter(payload.error);
        return;
      }
      if (payload?.codex) {
        syncCodexStatus(payload.codex);
      }
      if (payload?.connected && payload?.codex?.connected) {
        setFooter("날짜를 고르고 기록을 생성하면 앱 안에서 바로 일기와 보고서를 볼 수 있어요.");
        showToast("Codex 준비 완료");
      } else if (payload?.message) {
        setFooter(payload.message);
        showToast(payload.message);
      } else {
        setFooter("Codex 연결 상태를 다시 확인했어요.");
      }
      if (!state.data) renderStage();
    } catch (err) {
      setWarning(String(err && err.message ? err.message : err));
      setFooter("Codex 연결에 실패했어요.");
    } finally {
      setBusy(false);
    }
  }

  function showEmptyDateState(iso, reasonText = "") {
    state.data = null;
    state.selectedDateIso = iso || null;
    state.selectedWeekStart = null;
    state.nav = "diary";
    state.view = "diary";
    state.timelineVisibleCount = TIMELINE_PREVIEW;
    setCalendarCursor(iso);
    setNavActive();
    renderConfig();
    renderSideDates();
    syncSegmented();
    renderStage();
    if (iso) {
      const connectionMessage =
        state.codex.loaded && !state.codex.connected
          ? "먼저 Codex를 연결해 주세요."
          : "";
      setFooter(
        reasonText ||
          connectionMessage ||
          `${formatKoreanDate(iso)} 저장된 일기가 아직 없어요. 새로 생성하면 이 날짜 기록으로 덮어써집니다.`,
      );
    }
    setWarning("");
  }

  async function openDate(iso, options = {}) {
    const { clearOnMissing = false } = options;
    const bridge = api();
    if (!bridge) return;
    try {
      const payload = await bridge.load_date(iso, state.config.outDir);
      if (payload?.error) {
        state.config.targetDate = iso;
        if (clearOnMissing) {
          showEmptyDateState(iso);
          return;
        }
        setFooter(`${iso} 일기를 열 수 없어요.`);
        setWarning(payload.error);
        return;
      }
      state.data = payload;
      state.selectedDateIso = iso;
      state.selectedWeekStart = null;
      state.config.targetDate = iso;
      setCalendarCursor(iso);
      state.nav = "diary";
      state.view = "diary";
      state.timelineVisibleCount = TIMELINE_PREVIEW;
      setNavActive();
      renderConfig();
      renderSideDates();
      syncSegmented();
      renderStage();
      setFooter(`${formatKoreanDate(iso)} 일기를 열었어요.`);
      setWarning("");
    } catch (err) {
      setWarning(String(err));
    }
  }

  function syncTargetDateView() {
    if (!state.config.targetDate) return;
    setCalendarCursor(state.config.targetDate);
    openDate(state.config.targetDate, { clearOnMissing: true });
  }

  async function openWeek(iso) {
    const bridge = api();
    if (!bridge) return;
    try {
      const payload = await bridge.load_week(iso, state.config.outDir);
      if (payload?.error) {
        setFooter("주간 보기를 열 수 없어요.");
        setWarning(payload.error);
        return;
      }
      state.data = payload;
      state.config.targetDate = iso;
      state.selectedWeekStart = iso;
      state.selectedDateIso = null;
      state.nav = "diary";
      state.view = "raw";
      state.timelineVisibleCount = TIMELINE_PREVIEW;
      setCalendarCursor(iso);
      setNavActive();
      renderConfig();
      renderSideDates();
      syncSegmented();
      renderStage();
      setFooter(`${payload.label} 주간 보기를 열었어요.`);
      setWarning("");
    } catch (err) {
      setWarning(String(err));
    }
  }

  async function refreshLists() {
    const bridge = api();
    if (!bridge) return;
    try {
      const entries = await bridge.list_entries(state.config.outDir);
      state.dates = entries.dates || [];
      state.weeks = entries.weeks || [];
      renderSideDates();
      if (state.nav === "calendar" || state.nav === "archive") renderStage();
    } catch (err) {
      console.error(err);
    }
  }

  async function pickFolder(kind) {
    const bridge = api();
    if (!bridge) return;
    toggleMenu(false);
    const current = kind === "source" ? state.config.sourceDir : state.config.outDir;
    const picked = await bridge.pick_folder(kind, current);
    if (!picked) return;
    if (kind === "source") state.config.sourceDir = picked;
    else state.config.outDir = picked;
    renderConfig();
    refreshLists();
    showToast(kind === "source" ? "입력 폴더를 바꿨어요" : "출력 폴더를 바꿨어요");
  }

  async function copyCurrentView() {
    if (!state.data) {
      showToast("복사할 내용이 없어요");
      return;
    }
    const views = state.data.views || {};
    const key = state.view === "raw" ? "full" : state.view;
    const text = views[key] || views.full || state.data.markdown || "";
    if (!text.trim()) {
      showToast("복사할 내용이 없어요");
      return;
    }
    try {
      await navigator.clipboard.writeText(text);
      showToast("복사했어요");
    } catch {
      const bridge = api();
      if (bridge) {
        await bridge.copy_to_clipboard(text);
        showToast("복사했어요");
      } else {
        showToast("복사에 실패했어요");
      }
    }
  }

  async function openExternal() {
    const bridge = api();
    if (!bridge || !state.data?.saved_path) {
      showToast("저장된 파일이 없어요");
      return;
    }
    await bridge.open_external(state.data.saved_path);
  }

  /* Segmented / view ---------------------------------------------------- */
  function syncSegmented() {
    const radios = document.querySelectorAll('input[name="view"]');
    radios.forEach((r) => {
      r.checked = r.value === state.view;
    });
  }

  /* Date helpers -------------------------------------------------------- */
  function shiftDate(days) {
    if (!state.config.targetDate) return;
    const d = new Date(`${state.config.targetDate}T12:00:00`);
    d.setDate(d.getDate() + days);
    state.config.targetDate = d.toISOString().slice(0, 10);
    setCalendarCursor(state.config.targetDate);
    renderConfig();
    syncTargetDateView();
  }

  async function jumpToday() {
    const bridge = api();
    if (!bridge) return;
    try {
      const iso = await bridge.today(state.config.boundaryHour);
      if (!iso) return;
      state.config.targetDate = iso;
      setCalendarCursor(iso);
      renderConfig();
      syncTargetDateView();
      showToast("오늘 기준 날짜로 맞췄어요");
    } catch (err) {
      setWarning(String(err && err.message ? err.message : err));
    }
  }

  function shiftBoundary(delta) {
    const next = Math.max(0, Math.min(23, state.config.boundaryHour + delta));
    state.config.boundaryHour = next;
    renderConfig();
    const bridge = api();
    if (bridge && state.config.targetDate) {
      bridge
        .recompute_target(state.config.targetDate, next)
        .then((iso) => {
          if (iso) {
            state.config.targetDate = iso;
            setCalendarCursor(iso);
            renderConfig();
            syncTargetDateView();
          }
        })
        .catch(() => {});
    }
  }

  function openDatePicker() {
    if (state.config.targetDate) {
      setCalendarCursor(state.config.targetDate);
      state.selectedDateIso = state.selectedDateIso || state.config.targetDate;
    }
    state.nav = "calendar";
    setNavActive();
    renderConfig();
    renderStage();
    setFooter("캘린더 탭에서 날짜를 골라 기록을 이어서 볼 수 있어요.");
    setWarning("");
  }

  function toggleSettings(force) {
    state.settingsOpen = typeof force === "boolean" ? force : !state.settingsOpen;
    const panel = $("#settings-panel");
    if (panel) panel.hidden = !state.settingsOpen;
    if (state.settingsOpen && state.menuOpen) toggleMenu(false);
  }

  function toggleMenu(force) {
    state.menuOpen = typeof force === "boolean" ? force : !state.menuOpen;
    const menu = $("#overflow-menu");
    if (menu) menu.hidden = !state.menuOpen;
    const btn = document.querySelector('[data-action="toggle-menu"]');
    if (btn) btn.setAttribute("aria-expanded", String(state.menuOpen));
  }

  function bindWheelScroll(node) {
    if (!node) return;
    node.addEventListener(
      "wheel",
      (event) => {
        const canScrollY = node.scrollHeight > node.clientHeight + 1;
        const canScrollX = node.scrollWidth > node.clientWidth + 1;
        if (!canScrollY && !canScrollX) return;

        const prevTop = node.scrollTop;
        const prevLeft = node.scrollLeft;

        if (canScrollY && event.deltaY) node.scrollTop += event.deltaY;
        if (canScrollX && event.deltaX) node.scrollLeft += event.deltaX;

        if (node.scrollTop !== prevTop || node.scrollLeft !== prevLeft) {
          event.preventDefault();
        }
      },
      { passive: false },
    );
  }

  /* Events -------------------------------------------------------------- */
  function bindEvents() {
    const dateInput = $("#date-input");
    if (dateInput) {
      dateInput.addEventListener("change", (e) => {
        state.config.targetDate = e.target.value;
        renderConfig();
        syncTargetDateView();
      });
    }

    document.querySelectorAll('input[name="mode"]').forEach((r) =>
      r.addEventListener("change", (e) => {
        state.config.mode = e.target.value;
      }),
    );

    document.querySelectorAll('input[name="view"]').forEach((r) =>
      r.addEventListener("change", (e) => {
        state.view = e.target.value;
        renderStage();
      }),
    );

    const autoSave = $("#auto-save");
    if (autoSave) {
      autoSave.addEventListener("change", (e) => {
        state.config.autoSave = e.target.checked;
      });
    }

    const outputLanguage = $("#output-language");
    if (outputLanguage) {
      outputLanguage.addEventListener("change", (e) => {
        setOutputLanguage(e.target.value);
        showToast(`출력 언어를 ${getOutputLanguageOption().label}로 바꿨어요`);
      });
    }

    document.querySelectorAll(".side-nav__item").forEach((btn) => {
      btn.addEventListener("click", () => {
        state.nav = btn.dataset.nav || "diary";
        if (state.nav === "diary") {
          state.view = "diary";
          syncSegmented();
        } else if (state.nav === "calendar" && state.config.targetDate) {
          setCalendarCursor(state.config.targetDate);
        }
        setNavActive();
        renderConfig();
        renderStage();
      });
    });

    const menuToggleBtn = document.querySelector('[data-action="toggle-menu"]');
    if (menuToggleBtn) {
      menuToggleBtn.addEventListener("pointerdown", (event) => {
        event.stopPropagation();
      });
      menuToggleBtn.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
        toggleMenu();
      });
    }

    const overflowMenu = $("#overflow-menu");
    if (overflowMenu) {
      overflowMenu.addEventListener("pointerdown", (event) => {
        event.stopPropagation();
      });
    }

    document.addEventListener("pointerdown", (event) => {
      if (state.menuOpen && !event.target.closest(".menu-wrap")) {
        toggleMenu(false);
      }
    });

    document.addEventListener("click", (event) => {
      const target = event.target.closest("[data-action]");
      if (!target) {
        if (state.menuOpen && !event.target.closest(".menu-wrap")) toggleMenu(false);
        return;
      }
      // Close menu on ANY action click that isn't the toggle itself.
      if (state.menuOpen && target.dataset.action !== "toggle-menu") {
        const inMenu = target.closest("#overflow-menu");
        if (!inMenu) toggleMenu(false);
      }
      const action = target.dataset.action;
      switch (action) {
        case "date-prev":
          shiftDate(-1);
          break;
        case "date-next":
          shiftDate(1);
          break;
        case "open-picker":
          openDatePicker();
          break;
        case "jump-today":
          jumpToday();
          break;
        case "boundary-plus":
          shiftBoundary(1);
          break;
        case "boundary-minus":
          shiftBoundary(-1);
          break;
        case "pick-source":
          pickFolder("source");
          break;
        case "pick-out":
          pickFolder("out");
          break;
        case "generate":
          generate();
          break;
        case "codex-connect":
          connectCodex();
          break;
        case "view-week":
          toggleMenu(false);
          if (state.config.targetDate) openWeek(state.config.targetDate);
          break;
        case "copy":
          toggleMenu(false);
          copyCurrentView();
          break;
        case "open-external":
          toggleMenu(false);
          openExternal();
          break;
        case "toggle-settings":
          toggleSettings();
          break;
        case "toggle-menu":
          break;
        default:
          break;
      }
    });

    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") {
        if (state.menuOpen) toggleMenu(false);
        else if (state.settingsOpen) toggleSettings(false);
      }
      if ((e.metaKey || e.ctrlKey) && e.key === "Enter") generate();
    });

    window.addEventListener("blur", () => {
      if (state.menuOpen) toggleMenu(false);
    });
    window.addEventListener("resize", () => {
      if (state.menuOpen) toggleMenu(false);
    });
    document.addEventListener(
      "scroll",
      () => {
        if (state.menuOpen) toggleMenu(false);
      },
      true,
    );

    bindWheelScroll($(".paper__body"));
    bindWheelScroll($(".sidebar"));
    bindWheelScroll($("#settings-panel"));
  }

  /* Boot ---------------------------------------------------------------- */
  async function boot() {
    hydrateClientPreferences();
    installRuntimeUi();
    bindEvents();
    setNavActive();
    syncSegmented();
    renderStage();
    renderConfig();
    setFooter("날짜를 고르고 기록을 생성하면 앱 안에서 바로 일기와 보고서를 볼 수 있어요.");

    await new Promise((resolve) => {
      if (api()) return resolve();
      window.addEventListener("pywebviewready", resolve, { once: true });
    });

    const bridge = api();
    try {
      const initial = await bridge.get_state();
      syncConfig(initial.config);
      syncCodexStatus(initial.codex || {
        available: Boolean(initial.generation_available),
        connected: Boolean(initial.generation_available),
        connectable: false,
        message: initial.status || "",
        detail: initial.status || "",
      });
      state.dates = initial.entries?.dates || [];
      state.weeks = initial.entries?.weeks || [];
      renderSideDates();
      syncTargetDateView();
    } catch (err) {
      console.error(err);
    }
  }

  document.addEventListener("DOMContentLoaded", boot);
})();
