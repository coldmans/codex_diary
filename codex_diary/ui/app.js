(() => {
  "use strict";

  const TIMELINE_PREVIEW = 8;
  const TIMELINE_STEP = 20;
  const LOADING_PHASE_INDEX = {
    collect: 0,
    organize: 0,
    write: 1,
    finish: 2,
  };
  const LOADING_PHASES = [
    {
      titleKeys: ["loading.step.collect", "loading.step.organize"],
      detailKey: "loading.detail.collect",
      minSeconds: 0,
    },
    { titleKey: "loading.step.write", detailKey: "loading.detail.write", minSeconds: 8 },
    { titleKey: "loading.step.finish", detailKey: "loading.detail.finish", minSeconds: 18 },
  ];
  const MOOD_OPTIONS = [
    { key: "sparkle", emoji: "✨" },
    { key: "happy", emoji: "😊" },
    { key: "soft", emoji: "🙂" },
    { key: "tired", emoji: "😐" },
    { key: "blue", emoji: "🥺" },
  ];
  const MEMO_KEY = "codex-diary:memos:v1";
  const MOOD_KEY = "codex-diary:moods:v1";
  const CARRYOVER_TODO_KEY = "codex-diary:carryover-todos:v1";
  const OUTPUT_LANGUAGE_KEY = "codex-diary:output-language:v1";
  const DIARY_LENGTH_KEY = "codex-diary:diary-length:v1";
  const CODEX_MODEL_KEY = "codex-diary:codex-model:v1";
  const BOUNDARY_HOUR_KEY = "codex-diary:boundary-hour:v1";
  const AUTO_SAVE_KEY = "codex-diary:auto-save:v1";
  const SOURCE_DIR_KEY = "codex-diary:source-dir:v1";
  const OUT_DIR_KEY = "codex-diary:out-dir:v1";
  const RUNTIME_STYLE_ID = "codex-diary-runtime-style";
  const OUTPUT_LANGUAGES = [
    { key: "en", label: "English", nativeLabel: "English", locale: "en-US" },
    { key: "ko", label: "Korean", nativeLabel: "한국어", locale: "ko-KR" },
    { key: "ja", label: "Japanese", nativeLabel: "日本語", locale: "ja-JP" },
    { key: "zh", label: "Chinese", nativeLabel: "中文", locale: "zh-CN" },
    { key: "fr", label: "French", nativeLabel: "Français", locale: "fr-FR" },
    { key: "de", label: "German", nativeLabel: "Deutsch", locale: "de-DE" },
    { key: "es", label: "Spanish", nativeLabel: "Español", locale: "es-ES" },
    { key: "vi", label: "Vietnamese", nativeLabel: "Tiếng Việt", locale: "vi-VN" },
    { key: "th", label: "Thai", nativeLabel: "ไทย", locale: "th-TH" },
    { key: "ru", label: "Russian", nativeLabel: "Русский", locale: "ru-RU" },
    { key: "hi", label: "Hindi", nativeLabel: "हिन्दी", locale: "hi-IN" },
  ];
  const UI_COPY = window.CODEX_DIARY_UI_COPY || { en: {} };
  const DIARY_LENGTH_OPTIONS = [
    { key: "short" },
    { key: "medium" },
    { key: "long" },
    { key: "very-long" },
  ];
  const DEFAULT_CODEX_MODEL = "gpt-5.4";
  const CODEX_MODEL_OPTIONS = [
    { key: "gpt-5.5", label: "GPT-5.5" },
    { key: "gpt-5.4", label: "GPT-5.4" },
    { key: "gpt-5.4-mini", label: "GPT-5.4 Mini" },
    { key: "gpt-5.3-codex", label: "GPT-5.3 Codex" },
    { key: "gpt-5.3-codex-spark", label: "GPT-5.3 Codex Spark" },
    { key: "gpt-5.2", label: "GPT-5.2" },
  ];
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
      diaryLength: "short",
      codexModel: DEFAULT_CODEX_MODEL,
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
    busyKind: null,
    loadingTimerId: null,
    loadingTick: 0,
    generationMeta: null,
    generationProgress: null,
    codex: {
      loaded: false,
      available: false,
      connected: false,
      connectable: false,
      message: "",
      detail: "",
    },
    readiness: {
      loaded: false,
      sourceDir: "",
      sourceExists: false,
      sourceMarkdownCount: null,
      outDir: "",
      outExists: false,
    },
    timelineVisibleCount: TIMELINE_PREVIEW,
    settingsOpen: false,
    settingsLastFocus: null,
    settingsHideTimer: null,
    menuOpen: false,
    languagePinned: false,
    diaryLengthPinned: false,
    codexModelPinned: false,
    boundaryPinned: false,
    autoSavePinned: false,
    sourceDirPinned: false,
    outDirPinned: false,
    stageRenderId: 0,
    viewRequestId: 0,
    boundaryRequestId: 0,
    suppressNextClick: false,
    effectiveTodayIso: null,
  };

  function currentUiOption(value = state.config.outputLanguage) {
    return OUTPUT_LANGUAGES.find((option) => option.key === value) || OUTPUT_LANGUAGES[0];
  }

  function clamp(value, min, max) {
    return Math.min(max, Math.max(min, value));
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

  function displayLanguageLabel(value = state.config.outputLanguage) {
    const option = getOutputLanguageOption(value);
    return option.nativeLabel || option.label;
  }

  function toNullableNumber(value) {
    return typeof value === "number" && Number.isFinite(value) ? value : null;
  }

  function normalizeProgress(progress) {
    if (!progress || typeof progress !== "object") return null;
    return {
      ...progress,
      percent: toNullableNumber(progress.percent),
      current: toNullableNumber(progress.current),
      total: toNullableNumber(progress.total),
      stats:
        progress.stats && typeof progress.stats === "object" ? progress.stats : {},
      indeterminate: Boolean(progress.indeterminate),
      error: progress.error ? String(progress.error) : "",
      phase: progress.phase ? String(progress.phase) : null,
      status: progress.status ? String(progress.status) : "running",
    };
  }

  function syncGenerationProgress(progress) {
    state.generationProgress = normalizeProgress(progress);
    if (state.busy && state.busyKind === "generate") {
      updateLoadingView();
      syncGenerateButton();
    }
  }

  function currentLoadingFallback(elapsedSeconds) {
    const phaseIndex = LOADING_PHASES.reduce(
      (current, phase, index) => (elapsedSeconds >= phase.minSeconds ? index : current),
      0,
    );
    const progressFloor = phaseIndex === 0 ? 18 : phaseIndex === 1 ? 42 : 84;
    const progressCeil = phaseIndex === 0 ? 34 : phaseIndex === 1 ? 78 : 96;
    const phaseStart = LOADING_PHASES[phaseIndex].minSeconds || 0;
    const phaseElapsed = Math.max(0, elapsedSeconds - phaseStart);
    return {
      phaseIndex,
      phase: LOADING_PHASES[phaseIndex],
      percent: clamp(progressFloor + Math.min(phaseElapsed, 12) * 3, progressFloor, progressCeil),
      indeterminate: true,
      progress: null,
    };
  }

  function loadingMetaText(snapshot) {
    const stats = snapshot?.progress?.stats || {};
    const diaryLengthKey =
      normalizeDiaryLengthKey(state.generationMeta?.diaryLengthKey || state.config.diaryLength) ||
      "short";
    const sourcesTotal = Number(stats.sources_total || 0);
    const eventsSelected = Number(stats.events_selected || 0);
    if (diaryLengthKey === "very-long" || sourcesTotal >= 120 || eventsSelected >= 2500) {
      return t("loading.meta.slow");
    }
    return t("loading.meta");
  }

  function generationRequestTimeoutMs(lengthKey = state.config.diaryLength) {
    const key = normalizeDiaryLengthKey(lengthKey) || "short";
    if (key === "very-long") return 405000;
    if (key === "long") return 345000;
    return 285000;
  }

  function loadingStepTitle(step) {
    const keys = Array.isArray(step.titleKeys) ? step.titleKeys : [step.titleKey];
    return keys.filter(Boolean).map((key) => t(key)).join(" · ");
  }

  function loadingStepDetail(step, index, snapshot) {
    const progress = snapshot.progress;
    if (index < snapshot.phaseIndex) {
      return "";
    }
    const baseKey =
      progress && index === snapshot.phaseIndex && progress.detail_key
        ? progress.detail_key
        : step.detailKey;
    const baseText = t(baseKey);
    if (!progress || index !== snapshot.phaseIndex) return baseText;

    const suffixes = [];
    if (progress.current !== null && progress.total !== null && progress.total > 0) {
      suffixes.push(`${progress.current}/${progress.total}`);
    } else if (!progress.indeterminate && typeof progress.percent === "number" && progress.percent > 0) {
      suffixes.push(`${progress.percent}%`);
    }
    return suffixes.length ? `${baseText} · ${suffixes.join(" · ")}` : baseText;
  }

  function currentLoadingSnapshot() {
    const startedAt = state.generationMeta?.startedAt || Date.now();
    const elapsedSeconds = Math.max(0, Math.floor((Date.now() - startedAt) / 1000));
    const progress = state.generationProgress;
    const fallback = currentLoadingFallback(elapsedSeconds);
    if (!progress || !progress.phase || progress.status === "idle") {
      return { elapsedSeconds, ...fallback };
    }
    const phaseIndex =
      LOADING_PHASE_INDEX[progress.phase] ?? fallback.phaseIndex;
    const phase = LOADING_PHASES[phaseIndex] || fallback.phase;
    return {
      elapsedSeconds,
      phaseIndex,
      phase,
      percent:
        progress.percent !== null
          ? clamp(progress.percent, 0, 100)
          : fallback.percent,
      indeterminate: Boolean(progress.indeterminate),
      progress,
    };
  }

  function updateLoadingView() {
    if (!(state.busy && state.busyKind === "generate")) return;
    const root = document.querySelector("[data-loading-card]");
    if (!root) {
      renderStage({ preserveScroll: true });
      return;
    }

    const snapshot = currentLoadingSnapshot();
    const { elapsedSeconds, phase } = snapshot;
    const phaseText = root.querySelector("[data-loading-phase]");
    const elapsedText = root.querySelector("[data-loading-elapsed]");
    const metaText = root.querySelector("[data-loading-meta]");
    if (phaseText) phaseText.textContent = t((snapshot.progress && snapshot.progress.detail_key) || phase.detailKey);
    if (elapsedText) elapsedText.textContent = t("loading.elapsed", { seconds: elapsedSeconds });
    if (metaText) {
      const meta = loadingMetaText(snapshot);
      metaText.textContent = meta;
      metaText.hidden = !meta;
    }

    const meter = root.querySelector("[data-loading-progressbar]");
    const meterBar = root.querySelector("[data-loading-meter-bar]");
    if (meter) {
      meter.setAttribute("aria-valuemin", "0");
      meter.setAttribute("aria-valuemax", "100");
      meter.setAttribute("aria-valuetext", t((snapshot.progress && snapshot.progress.detail_key) || phase.detailKey));
      if (snapshot.indeterminate) {
        meter.removeAttribute("aria-valuenow");
      } else {
        meter.setAttribute("aria-valuenow", String(snapshot.percent));
      }
    }
    if (meterBar) {
      meterBar.style.width = `${snapshot.indeterminate ? 44 : clamp(snapshot.percent, 6, 100)}%`;
      meterBar.classList.toggle("is-determinate", !snapshot.indeterminate);
      meterBar.classList.toggle("is-indeterminate", snapshot.indeterminate);
    }

  }

  function startLoadingPulse() {
    if (state.loadingTimerId) clearInterval(state.loadingTimerId);
    state.loadingTick = 0;
    state.loadingTimerId = setInterval(() => {
      if (!(state.busy && state.busyKind === "generate")) return;
      state.loadingTick += 1;
      updateLoadingView();
    }, 1000);
  }

  function stopLoadingPulse() {
    if (state.loadingTimerId) {
      clearInterval(state.loadingTimerId);
      state.loadingTimerId = null;
    }
    state.loadingTick = 0;
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
      loading: 260,
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
    const weekStart = weekStartDay();
    const sunday = new Date(Date.UTC(2024, 0, 7, 12, 0, 0));
    return Array.from({ length: 7 }, (_, index) =>
      formatter.format(new Date(sunday.getTime() + (weekStart + index) * 24 * 60 * 60 * 1000)),
    );
  }

  function weekStartDay() {
    return ["fr", "de", "es", "vi", "ru", "zh"].includes(currentUiLanguage()) ? 1 : 0;
  }

  function localTodayIso() {
    const now = new Date();
    return `${now.getFullYear()}-${pad2(now.getMonth() + 1)}-${pad2(now.getDate())}`;
  }

  function addDaysIso(iso, days) {
    const d = parseIsoDate(iso);
    if (!d) return "";
    d.setDate(d.getDate() + days);
    return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`;
  }

  function formatWeekRange(startIso, endIso) {
    if (!startIso || !endIso) return "";
    return `${formatShortMonthDay(startIso)} ~ ${formatShortMonthDay(endIso)}`;
  }

  function computeGenerateLabel() {
    const modeLabel = t("generate.finalize");
    const iso = state.config.targetDate;
    if (!iso) return modeLabel;
    if (iso === (state.effectiveTodayIso || localTodayIso())) {
      return t("generate.todayFinalize");
    }
    return `${formatShortMonthDay(iso)} ${modeLabel}`;
  }

  function isCancellingGeneration() {
    return state.busyKind === "generate" && state.generationProgress?.status === "cancelling";
  }

  function isGenerationLocked() {
    return state.busy && state.busyKind === "generate";
  }

  function isCodexChecking() {
    return !state.codex.loaded;
  }

  function needsCodexConnection() {
    return state.codex.loaded && !state.codex.connected;
  }

  function canConnectCodex() {
    return needsCodexConnection() && state.codex.connectable;
  }

  function generateBlockedByCodex() {
    return isCodexChecking() || (needsCodexConnection() && !state.codex.connectable);
  }

  function idleGenerateLabel() {
    if (isCodexChecking()) return t("status.text.loading");
    if (needsCodexConnection()) return t("generate.connect");
    return computeGenerateLabel();
  }

  function refreshGenerateLabel() {
    const label = document.querySelector(".cta__label");
    if (!label) return;
    if (state.busyKind === "generate") {
      label.textContent = isCancellingGeneration() ? t("generate.cancelling") : t("generate.cancel");
      return;
    }
    if (state.busy) {
      label.textContent = state.busyKind === "connect" ? t("status.text.loading") : t("generate.busy");
      return;
    }
    label.textContent = idleGenerateLabel();
  }

  function syncGenerateButton() {
    const btn = document.querySelector(".cta");
    if (!btn) return;
    const generating = state.busyKind === "generate";
    const blocked = generateBlockedByCodex();
    btn.disabled = generating ? isCancellingGeneration() : state.busy || blocked;
    btn.classList.toggle("is-cancel", generating);
    const spinner = btn.querySelector(".spinner");
    if (spinner) spinner.hidden = !(state.busy && state.busyKind === "generate");
    btn.title = generating
      ? t("generate.cancelTitle")
      : isCodexChecking()
        ? t("status.detail.wait")
      : needsCodexConnection()
        ? t("generate.connectTitle")
        : "";
    refreshGenerateLabel();
  }

  function syncMutableControls() {
    const locked = isGenerationLocked();
    document
      .querySelectorAll(
        [
          "#date-input",
          "#output-language",
          "#diary-length",
          "#codex-model",
          "#auto-save",
          ".side-nav__item",
          '[data-action="date-prev"]',
          '[data-action="date-next"]',
          '[data-action="open-picker"]',
          '[data-action="jump-today"]',
          '[data-action="boundary-minus"]',
          '[data-action="boundary-plus"]',
          '[data-action="pick-source"]',
          '[data-action="pick-out"]',
          '[data-action="toggle-menu"]',
        ].join(", "),
      )
      .forEach((control) => {
        if (control instanceof HTMLButtonElement || control instanceof HTMLInputElement || control instanceof HTMLSelectElement) {
          control.disabled = locked;
        }
      });
  }

  function syncOverflowActions() {
    const copyButton = document.querySelector('[data-action="copy"]');
    const externalButton = document.querySelector('[data-action="open-external"]');
    if (copyButton instanceof HTMLButtonElement) {
      copyButton.disabled = !state.data;
      copyButton.title = state.data ? "" : t("toast.nothingToCopy");
    }
    if (externalButton instanceof HTMLButtonElement) {
      externalButton.disabled = !state.data?.saved_path;
      externalButton.title = state.data?.saved_path ? "" : t("toast.noSavedFile");
    }
  }

  function extractHashtags(structured) {
    if (Array.isArray(structured?.tags) && structured.tags.length) {
      return structured.tags.slice(0, 6);
    }
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
    if (structured?.report?.today) seeds.push(t("tag.today"));
    if (structured?.report?.decisions?.length) seeds.push(t("tag.decisions"));
    if (structured?.report?.blockers?.length) seeds.push(t("tag.blockers"));
    if (structured?.report?.tomorrow?.length) seeds.push(t("tag.tomorrow"));
    if (structured?.has_diary) seeds.push(t("tag.diary"));
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
    const languageSetting = el("label", { class: "setting setting--card", dataset: { setting: "output-language" } }, [
      el("span", {}, t("settings.languageLabel")),
      el("div", { class: "setting__field setting__field--select" }, [
        el(
          "select",
          {
            id: "output-language",
            class: "select",
            "aria-label": t("settings.languageLabel"),
          },
          OUTPUT_LANGUAGES.map((option) =>
            el("option", { value: option.key }, option.nativeLabel || option.label),
          ),
        ),
      ]),
      el("span", { class: "setting__hint" }, t("settings.languageHint")),
    ]);
    if (autoSaveSetting && autoSaveSetting.parentElement) {
      autoSaveSetting.parentElement.insertBefore(languageSetting, autoSaveSetting);
    }
    else panel.appendChild(languageSetting);
  }

  function ensureDiaryLengthSetting() {
    const panel = $("#settings-panel");
    if (!panel || $("#diary-length")) return;
    const autoSaveSetting = $("#auto-save") ? $("#auto-save").closest(".setting") : null;
    const lengthSetting = el("label", { class: "setting setting--card", dataset: { setting: "diary-length" } }, [
      el("span", {}, t("settings.lengthLabel")),
      el("div", { class: "setting__field setting__field--select" }, [
        el(
          "select",
          {
            id: "diary-length",
            class: "select",
            "aria-label": t("settings.lengthLabel"),
          },
          DIARY_LENGTH_OPTIONS.map((option) =>
            el("option", { value: option.key }, t(`length.${option.key}`)),
          ),
        ),
      ]),
      el("span", { class: "setting__hint" }, t("settings.lengthHint")),
    ]);
    if (autoSaveSetting && autoSaveSetting.parentElement) {
      autoSaveSetting.parentElement.insertBefore(lengthSetting, autoSaveSetting);
    }
    else panel.appendChild(lengthSetting);
  }

  function installRuntimeUi() {
    injectRuntimeStyles();
    ensureLanguageSetting();
    ensureDiaryLengthSetting();
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
    setAria('[data-action="date-prev"]', "action.prevDay");
    setTitle('[data-action="date-next"]', "action.nextDay");
    setAria('[data-action="date-next"]', "action.nextDay");
    setTitle('[data-action="open-picker"]', "action.pickDate");
    setAria('[data-action="open-picker"]', "action.pickDate");
    setAria("#date-input", "action.pickDate");
    setText(".paper__date-label", "date.label");
    setText('[data-action="jump-today"]', "action.today");
    setTitle('[data-action="toggle-menu"]', "action.more");
    setAria('[data-action="toggle-menu"]', "action.more");

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
    setAria('#settings-panel [data-action="toggle-settings"]', "action.close");
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
      const select = languageSetting.querySelector("select");
      if (select) select.setAttribute("aria-label", t("settings.languageLabel"));
    }

    const boundarySetting = $("#boundary-label")?.closest(".setting");
    if (boundarySetting) {
      const label = boundarySetting.querySelector("span");
      const hint = boundarySetting.querySelector(".setting__hint");
      if (label) label.textContent = t("settings.boundaryLabel");
      if (hint) hint.textContent = t("settings.boundaryHint");
    }

    const lengthSetting = $("#diary-length")?.closest(".setting");
    if (lengthSetting) {
      const label = lengthSetting.querySelector("span");
      const hint = lengthSetting.querySelector(".setting__hint");
      if (label) label.textContent = t("settings.lengthLabel");
      if (hint) hint.textContent = t("settings.lengthHint");
      const select = lengthSetting.querySelector("select");
      if (select) {
        select.setAttribute("aria-label", t("settings.lengthLabel"));
        Array.from(select.options).forEach((optionEl) => {
          optionEl.textContent = t(`length.${optionEl.value}`);
        });
      }
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
    if (introBadge) introBadge.textContent = t("settings.introBadge", { language: displayLanguageLabel() });
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

  function normalizeDiaryLengthKey(value) {
    if (value === null || value === undefined) return null;
    const raw = String(value).trim().toLowerCase();
    if (!raw) return null;
    const aliasMap = {
      brief: "short",
      compact: "short",
      normal: "medium",
      "very long": "very-long",
      very_long: "very-long",
      verylong: "very-long",
      "짧게": "short",
      "중간": "medium",
      "길게": "long",
      "매우 길게": "very-long",
    };
    const normalized = aliasMap[raw] || raw;
    return DIARY_LENGTH_OPTIONS.find((option) => option.key === normalized)?.key || null;
  }

  function getOutputLanguageOption(value = state.config.outputLanguage) {
    const key = normalizeLanguageKey(value) || DEFAULT_OUTPUT_LANGUAGE;
    return OUTPUT_LANGUAGES.find((option) => option.key === key) || OUTPUT_LANGUAGES[0];
  }

  function getDiaryLengthOption(value = state.config.diaryLength) {
    const key = normalizeDiaryLengthKey(value) || DIARY_LENGTH_OPTIONS[0].key;
    return DIARY_LENGTH_OPTIONS.find((option) => option.key === key) || DIARY_LENGTH_OPTIONS[0];
  }

  function normalizeCodexModelKey(value) {
    if (value === null || value === undefined) return null;
    const raw = String(value).trim();
    if (!raw || !/^[A-Za-z0-9][A-Za-z0-9._:-]{0,80}$/.test(raw)) return null;
    return raw;
  }

  function codexModelOptions() {
    const current = normalizeCodexModelKey(state.config.codexModel);
    const known = new Set(CODEX_MODEL_OPTIONS.map((option) => option.key));
    if (current && !known.has(current)) {
      return [{ key: current, label: current }, ...CODEX_MODEL_OPTIONS];
    }
    return CODEX_MODEL_OPTIONS;
  }

  function getCodexModelOption(value = state.config.codexModel) {
    const key = normalizeCodexModelKey(value) || DEFAULT_CODEX_MODEL;
    return codexModelOptions().find((option) => option.key === key) || { key, label: key };
  }

  function setOutputLanguage(value, { persist = true, rerender = true } = {}) {
    const option = getOutputLanguageOption(value);
    state.config.outputLanguage = option.key;
    if (persist) {
      writeTextStorage(OUTPUT_LANGUAGE_KEY, option.key);
      state.languagePinned = true;
    }
    applyStaticUiCopy();
    renderConfig();
    renderSideDates();
    if (rerender) renderStage({ preserveScroll: true });
  }

  function setDiaryLength(value, { persist = true } = {}) {
    const option = getDiaryLengthOption(value);
    state.config.diaryLength = option.key;
    if (persist) {
      writeTextStorage(DIARY_LENGTH_KEY, option.key);
      state.diaryLengthPinned = true;
    }
    renderConfig();
  }

  function setCodexModel(value, { persist = true } = {}) {
    const option = getCodexModelOption(value);
    state.config.codexModel = option.key;
    if (persist) {
      writeTextStorage(CODEX_MODEL_KEY, option.key);
      state.codexModelPinned = true;
    }
    renderConfig();
    syncCodexStatus(state.codex);
  }

  function hydrateClientPreferences() {
    const storedLanguage = normalizeLanguageKey(readTextStorage(OUTPUT_LANGUAGE_KEY));
    const storedLength = normalizeDiaryLengthKey(readTextStorage(DIARY_LENGTH_KEY));
    const storedCodexModel = normalizeCodexModelKey(readTextStorage(CODEX_MODEL_KEY));
    const storedBoundary = Number(readTextStorage(BOUNDARY_HOUR_KEY));
    const storedAutoSave = readTextStorage(AUTO_SAVE_KEY);
    const storedSourceDir = readTextStorage(SOURCE_DIR_KEY).trim();
    const storedOutDir = readTextStorage(OUT_DIR_KEY).trim();
    state.languagePinned = Boolean(storedLanguage);
    state.diaryLengthPinned = Boolean(storedLength);
    state.codexModelPinned = Boolean(storedCodexModel);
    state.boundaryPinned = Number.isInteger(storedBoundary) && storedBoundary >= 0 && storedBoundary <= 23;
    state.autoSavePinned = storedAutoSave === "true" || storedAutoSave === "false";
    state.sourceDirPinned = Boolean(storedSourceDir);
    state.outDirPinned = Boolean(storedOutDir);
    state.config.outputLanguage = storedLanguage || DEFAULT_OUTPUT_LANGUAGE;
    state.config.diaryLength = storedLength || DIARY_LENGTH_OPTIONS[0].key;
    state.config.codexModel = storedCodexModel || DEFAULT_CODEX_MODEL;
    if (state.boundaryPinned) state.config.boundaryHour = storedBoundary;
    if (state.autoSavePinned) state.config.autoSave = storedAutoSave === "true";
    if (state.sourceDirPinned) state.config.sourceDir = storedSourceDir;
    if (state.outDirPinned) state.config.outDir = storedOutDir;
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

  function normalizeTodoText(text) {
    return String(text || "").replace(/\s+/g, " ").trim();
  }

  function stableTodoId(fromIso, text) {
    const raw = `${fromIso || "unknown"}:${normalizeTodoText(text).toLowerCase()}`;
    return `todo-${Math.abs(hashIso(raw)).toString(36)}`;
  }

  function normalizeCarryoverTodo(todo, fallbackFromIso = "") {
    const text = normalizeTodoText(typeof todo === "string" ? todo : todo?.text);
    if (!text) return null;
    const fromIso = typeof todo === "object" && todo?.fromIso ? todo.fromIso : fallbackFromIso;
    return {
      id: typeof todo === "object" && todo?.id ? String(todo.id) : stableTodoId(fromIso, text),
      text,
      fromIso,
      done: Boolean(typeof todo === "object" && todo?.done),
      createdAt: typeof todo === "object" && todo?.createdAt ? String(todo.createdAt) : "",
    };
  }

  function getCarryoverTodos(iso) {
    if (!iso) return [];
    const all = readStorage(CARRYOVER_TODO_KEY);
    const raw = Array.isArray(all[iso]) ? all[iso] : [];
    return raw.map((item) => normalizeCarryoverTodo(item)).filter(Boolean);
  }

  function setCarryoverTodos(iso, todos) {
    if (!iso) return;
    const all = readStorage(CARRYOVER_TODO_KEY);
    const cleaned = (todos || []).map((item) => normalizeCarryoverTodo(item)).filter(Boolean);
    if (cleaned.length) all[iso] = cleaned;
    else delete all[iso];
    writeStorage(CARRYOVER_TODO_KEY, all);
  }

  function hasCarryoverTodo(iso, text) {
    const normalized = normalizeTodoText(text).toLowerCase();
    if (!normalized) return false;
    return getCarryoverTodos(iso).some((todo) => todo.text.toLowerCase() === normalized);
  }

  function addCarryoverTodo(fromIso, text) {
    const normalized = normalizeTodoText(text);
    const targetIso = addDaysIso(fromIso, 1);
    if (!targetIso || !normalized) return { added: false, targetIso };
    const todos = getCarryoverTodos(targetIso);
    if (todos.some((todo) => todo.text.toLowerCase() === normalized.toLowerCase())) {
      return { added: false, targetIso };
    }
    todos.push({
      id: stableTodoId(fromIso, normalized),
      text: normalized,
      fromIso,
      done: false,
      createdAt: new Date().toISOString(),
    });
    setCarryoverTodos(targetIso, todos);
    return { added: true, targetIso };
  }

  function toggleCarryoverTodo(iso, todoId) {
    const todos = getCarryoverTodos(iso);
    const next = todos.map((todo) =>
      todo.id === todoId ? { ...todo, done: !todo.done } : todo,
    );
    setCarryoverTodos(iso, next);
  }

  /* Stage --------------------------------------------------------------- */
  function renderStage(options = {}) {
    const stage = $("#stage");
    if (!stage) return;
    const renderId = (state.stageRenderId += 1);
    const preserveScroll = Boolean(options.preserveScroll);
    const previousScrollTop = preserveScroll ? stage.scrollTop : 0;
    const finish = (node) => {
      if (node) stage.appendChild(node);
      if (preserveScroll) {
        requestAnimationFrame(() => {
          if (renderId !== state.stageRenderId) return;
          const maxScroll = Math.max(0, stage.scrollHeight - stage.clientHeight);
          stage.scrollTop = Math.min(previousScrollTop, maxScroll);
        });
      } else {
        stage.scrollTop = 0;
        requestAnimationFrame(() => {
          if (renderId !== state.stageRenderId) return;
          stage.scrollTop = 0;
        });
      }
    };
    if (state.menuOpen) toggleMenu(false);
    stage.innerHTML = "";

    if (state.busy && state.busyKind === "generate") {
      return finish(renderLoadingStage());
    }

    if (state.nav === "calendar") {
      return finish(renderCalendar());
    }

    if (state.nav === "archive") {
      return finish(renderArchive());
    }

    if (state.codex.loaded && !state.codex.connected && !state.data) {
      return finish(renderConnectionPrompt());
    }

    if (!state.data) {
      return finish(renderEmpty());
    }

    const payload = state.data;
    const structured = payload.structured;
    const viewKey = state.view;

    if (viewKey === "raw") {
      return finish(renderRaw(payload.views_html?.full || ""));
    }

    if (viewKey === "report") {
      if (structured?.has_report) {
        finish(renderReport(structured.report, payload?.target_date));
      } else if (payload.views_html?.report) {
        finish(renderRaw(payload.views_html.report));
      } else {
        finish(renderViewEmpty(t("empty.report")));
      }
      return;
    }

    // diary (default)
    if (structured?.has_diary) {
      finish(renderDiary(structured, payload));
    } else if (payload.views_html?.diary) {
      finish(renderRaw(payload.views_html.diary));
    } else if (payload.views_html?.full) {
      finish(renderRaw(payload.views_html.full));
    } else {
      finish(renderViewEmpty(t("empty.diary")));
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
      ? t("empty.copyWithDate", { language: displayLanguageLabel() })
      : t("empty.copyToday");

    const empty = el("section", { class: "empty" }, [
      mascot,
      el("h2", { class: "empty__title" }, [
        document.createTextNode(title),
        el("span", { class: "empty__heart" }, " ♡"),
      ]),
      el("p", { class: "empty__copy" }, copy),
    ]);
    const carryover = renderCarryoverTodoCard(iso, { compact: true });
    const readiness = renderReadinessCard();
    const blocks = [empty, readiness, carryover].filter(Boolean);
    return blocks.length > 1 ? el("div", { class: "empty-stack" }, blocks) : empty;
  }

  function compactPath(path) {
    if (!path) return t("path.default");
    return String(path).replace(/^\/Users\/[^/]+/, "~");
  }

  function readinessRow({ state: rowState, label, value }) {
    return el("div", { class: `readiness__row is-${rowState}` }, [
      el("span", { class: "readiness__dot" }),
      el("span", { class: "readiness__label" }, label),
      el("span", { class: "readiness__value" }, value),
    ]);
  }

  function renderReadinessCard() {
    const readiness = state.readiness || {};
    const readinessLoaded = Boolean(readiness.loaded);
    const sourceDir = readiness.sourceDir || state.config.sourceDir;
    const outDir = readiness.outDir || state.config.outDir;
    const sourceCount =
      Number.isFinite(readiness.sourceMarkdownCount) ? readiness.sourceMarkdownCount : null;
    const sourceOk = readinessLoaded && Boolean(readiness.sourceExists) && (sourceCount === null || sourceCount > 0);
    const outputOk = readinessLoaded && Boolean(readiness.outExists);
    const sourceValue = !readinessLoaded
      ? t("status.text.loading")
      : !readiness.sourceExists
        ? t("readiness.sourceMissing")
      : sourceCount === 0
        ? `${compactPath(sourceDir)} · ${t("readiness.sourceEmpty")}`
      : `${compactPath(sourceDir)}${
        sourceCount === null ? "" : ` · ${t("readiness.sourceCount", { count: sourceCount })}`
      }`;
    const codexState = state.codex.connected ? "ok" : isCodexChecking() ? "pending" : "warn";
    const codexValue = state.codex.connected
      ? (state.codex.detail || t("status.detail.connected"))
      : isCodexChecking()
        ? t("status.text.loading")
        : (state.codex.detail || t("status.detail.login"));

    return el("section", { class: "readiness", "aria-label": t("readiness.title") }, [
      el("div", { class: "readiness__title" }, t("readiness.title")),
      el("div", { class: "readiness__notice" }, [
        el("strong", {}, t("readiness.prereqTitle")),
        el("span", {}, t("readiness.prereqBody")),
      ]),
      readinessRow({
        state: codexState,
        label: "Codex",
        value: codexValue,
      }),
      readinessRow({
        state: !readinessLoaded ? "pending" : sourceOk ? "ok" : "warn",
        label: t("settings.sourceLabel"),
        value: sourceValue,
      }),
      readinessRow({
        state: !readinessLoaded ? "pending" : outputOk ? "ok" : "pending",
        label: t("settings.outputLabel"),
        value: !readinessLoaded ? t("status.text.loading") : `${compactPath(outDir)} · ${
          outputOk ? t("readiness.outputReady") : t("readiness.outputMissing")
        }`,
      }),
    ]);
  }

  function renderLoadingStage() {
    const meta = state.generationMeta || {};
    const iso = meta.targetDate || state.selectedDateIso || state.config.targetDate;
    const language = displayLanguageLabel(meta.languageKey || state.config.outputLanguage);
    const title = iso
      ? t("loading.titleWithDate", { date: formatDisplayDate(iso) })
      : t("loading.titleToday");
    const snapshot = currentLoadingSnapshot();
    const { elapsedSeconds, phase } = snapshot;

    const mascot = el("div", { class: "loading-card__art", "aria-hidden": "true" });
    const glow = el("div", { class: "loading-card__glow" });
    const img = document.createElement("img");
    img.src = "assets/mascot-diary.png";
    img.alt = "";
    img.onerror = () => img.replaceWith(window.__mascotSvg("loading"));
    mascot.append(glow, img);
    ["1", "2", "3", "4"].forEach((index) =>
      mascot.appendChild(el("span", { class: `loading-card__spark loading-card__spark--${index}` })),
    );

    const meterAttrs = {
      class: "loading-card__meter",
      "data-loading-progressbar": "true",
      role: "progressbar",
      "aria-valuemin": "0",
      "aria-valuemax": "100",
      "aria-valuetext": t((snapshot.progress && snapshot.progress.detail_key) || phase.detailKey),
    };
    if (!snapshot.indeterminate) {
      meterAttrs["aria-valuenow"] = String(snapshot.percent);
    }

    return el("section", { class: "loading-card", "data-loading-card": "true" }, [
      el("div", { class: "loading-card__copy-block" }, [
        el("div", { class: "loading-card__badge" }, t("loading.badge", { language })),
        el("h2", { class: "loading-card__title" }, title),
        el("p", { class: "loading-card__copy" }, t("loading.copy", { language })),
        el("div", meterAttrs, [el("span", { class: `loading-card__meter-bar ${snapshot.indeterminate ? "is-indeterminate" : "is-determinate"}`.trim(), "data-loading-meter-bar": "true", style: `width: ${snapshot.indeterminate ? 44 : clamp(snapshot.percent, 6, 100)}%` })]),
        el("p", { class: "loading-card__phase", "data-loading-phase": "true", role: "status", "aria-live": "polite", "aria-atomic": "true" }, t((snapshot.progress && snapshot.progress.detail_key) || phase.detailKey)),
        el("div", { class: "loading-card__meta-row" }, [
          el("span", { class: "loading-card__elapsed", "data-loading-elapsed": "true" }, t("loading.elapsed", { seconds: elapsedSeconds })),
          el("span", { class: "loading-card__meta", "data-loading-meta": "true", hidden: !loadingMetaText(snapshot) }, loadingMetaText(snapshot)),
        ]),
      ]),
      mascot,
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
      renderCarryoverTodoCard(iso),
      renderMemoCard(iso),
      renderDiaryFoot(payload),
    ]);
  }

  function renderMoodRow(iso) {
    const current = getMood(iso);
    const options = el("div", { class: "mood__options", role: "group", "aria-label": t("mood.label") });
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
          "aria-pressed": active ? "true" : "false",
          onClick: () => {
            const next = current === opt.key ? null : opt.key;
            setMood(iso, next);
            renderSideDates();
            renderStage({ preserveScroll: true });
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
    const timestamp = payload?.saved_mtime ? new Date(payload.saved_mtime) : new Date();
    const time = timestamp.toLocaleTimeString(currentUiLocale(), {
      hour: "2-digit",
      minute: "2-digit",
    });
    return el("div", { class: "diary__foot" }, `${t("foot.writtenAt")} · ${time} · ${saved}`);
  }

  /* Report view --------------------------------------------------------- */
  function renderReport(report, reportIso = null) {
    const container = el("section", { class: "report" });
    const iso = reportIso || state.selectedDateIso || state.config.targetDate;

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
          icon: assetImg("assets/todo-carry.png", "card__badge-img"),
          tone: "warm",
          title: t("report.tomorrow"),
          subtitle: t("saved.records", { count: report.tomorrow.length }),
          body: renderTodoList(report.tomorrow, { carryForward: true, sourceIso: iso }),
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

  function assetImg(src, className, alt = "") {
    const img = document.createElement("img");
    img.src = src;
    img.alt = alt;
    img.className = className;
    return img;
  }

  function renderCarryoverTodoCard(iso, { compact = false } = {}) {
    const todos = getCarryoverTodos(iso);
    if (!todos.length) return null;
    const list = el("ul", { class: "carryover__list" });
    todos.forEach((todo) => {
      const btn = el(
        "button",
        {
          type: "button",
          class: `carryover__check ${todo.done ? "is-done" : ""}`,
          "aria-pressed": todo.done ? "true" : "false",
          title: todo.done ? t("todo.markOpen") : t("todo.markDone"),
          "aria-label": todo.done ? t("todo.markOpen") : t("todo.markDone"),
          onClick: () => {
            toggleCarryoverTodo(iso, todo.id);
            renderStage({ preserveScroll: true });
            showToast(t("toast.todoUpdated"));
          },
        },
        todo.done ? "✓" : "",
      );
      list.appendChild(
        el("li", { class: `carryover__item ${todo.done ? "is-done" : ""}`.trim() }, [
          btn,
          el("div", { class: "carryover__text" }, [
            el("span", {}, todo.text),
            todo.fromIso
              ? el("small", {}, t("carryover.from", { date: formatDisplayDate(todo.fromIso) }))
              : null,
          ]),
        ]),
      );
    });

    return el("section", { class: `carryover ${compact ? "carryover--compact" : ""}`.trim() }, [
      el("header", { class: "carryover__head" }, [
        assetImg("assets/todo-carry.png", "carryover__icon"),
        el("div", {}, [
          el("div", { class: "carryover__title" }, t("carryover.title")),
          el("div", { class: "carryover__subtitle" }, t("carryover.subtitle", { count: todos.length })),
        ]),
      ]),
      list,
    ]);
  }

  function renderTodoList(items, { carryForward = false, sourceIso = null } = {}) {
    const ul = el("ul", { class: "todo-list" });
    const targetIso = sourceIso ? addDaysIso(sourceIso, 1) : "";
    items.forEach((rawItem) => {
      const item = normalizeTodoText(rawItem);
      if (!item) return;
      const carried = carryForward && targetIso && hasCarryoverTodo(targetIso, item);
      const check = carryForward
        ? el(
            "button",
            {
              type: "button",
              class: `todo-check todo-check--action ${carried ? "is-carried" : ""}`.trim(),
              "aria-pressed": carried ? "true" : "false",
              title: carried ? t("todo.carriedForward") : t("todo.carryForward"),
              "aria-label": carried ? t("todo.carriedForward") : t("todo.carryForward"),
              onClick: () => {
                const result = addCarryoverTodo(sourceIso, item);
                renderStage({ preserveScroll: true });
                showToast(
                  result.added
                    ? t("toast.todoCarried", { date: formatDisplayDate(result.targetIso) })
                    : t("toast.todoAlreadyCarried", { date: formatDisplayDate(result.targetIso) }),
                );
              },
            },
            carried ? "✓" : "",
          )
        : el("span", { class: "todo-check" });
      ul.appendChild(
        el("li", { class: carried ? "is-carried" : "" }, [check, el("span", { class: "todo-text" }, item)]),
      );
    });
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
              renderStage({ preserveScroll: true });
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
                renderStage({ preserveScroll: true });
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
              renderStage({ preserveScroll: true });
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
      const weekday = (weekStartDay() + idx) % 7;
      weekdayRow.appendChild(
        el(
          "div",
          { class: `cal-weekdays__cell ${weekday === 0 ? "is-sun" : weekday === 6 ? "is-sat" : ""}` },
          label,
        ),
      );
    });
    root.appendChild(weekdayRow);

    const grid = el("div", { class: "cal-grid" });
    const firstDay = new Date(cursor.year, cursor.month, 1);
    const leadingBlanks = (firstDay.getDay() - weekStartDay() + 7) % 7;
    const daysInMonth = new Date(cursor.year, cursor.month + 1, 0).getDate();

    for (let i = 0; i < leadingBlanks; i += 1) {
      grid.appendChild(el("div", { class: "cal-cell cal-cell--blank" }));
    }

    for (let day = 1; day <= daysInMonth; day += 1) {
      const iso = `${cursor.year}-${pad2(cursor.month + 1)}-${pad2(day)}`;
      const saved = savedSet.has(iso);
      const meta = dateVisualMeta(iso, { saved });
      const active = iso === (state.selectedDateIso || state.config.targetDate);
      const today = iso === (state.effectiveTodayIso || localTodayIso());
      const title = dateTitleText(iso, { saved, mood: meta.mood });
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
            title,
            "aria-label": title,
            "aria-current": active ? "date" : null,
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
                state.nav = "diary";
                state.config.targetDate = iso;
                setCalendarCursor(iso);
                setNavActive();
                renderConfig();
                renderSideDates();
                renderStage();
                setFooter(
                  t("footer.noSavedForDateCalendar", {
                    date: formatDisplayDate(iso),
                    language: displayLanguageLabel(),
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
    const renderedCells = leadingBlanks + daysInMonth;
    for (let i = renderedCells; i < 42; i += 1) {
      grid.appendChild(el("div", { class: "cal-cell cal-cell--blank" }));
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
                formatWeekRange(week.start, week.end),
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
      state.dates.forEach((item) => {
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
      state.weeks.forEach((week) => {
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
      const active = btn.dataset.nav === state.nav;
      btn.classList.toggle("is-active", active);
      if (active) btn.setAttribute("aria-current", "page");
      else btn.removeAttribute("aria-current");
    });
  }

  /* Topbar / config ----------------------------------------------------- */
  function renderConfig() {
    applyStaticUiCopy();
    const iso = state.config.targetDate;
    const dateMain = $("#date-main");
    const weekdayEl = $("#date-weekday");
    if (dateMain) dateMain.textContent = formatBigDate(iso);
    if (weekdayEl) weekdayEl.textContent = formatWeekday(iso) || "";

    const input = $("#date-input");
    if (input) input.value = iso || "";

    const boundaryLabel = $("#boundary-label");
    if (boundaryLabel)
      boundaryLabel.textContent = t("boundary.label", {
        hour: String(state.config.boundaryHour).padStart(2, "0"),
      });
    const boundaryChip = $("#boundary-chip");
    if (boundaryChip)
      boundaryChip.textContent = t("boundary.chip", {
        hour: String(state.config.boundaryHour).padStart(2, "0"),
      });

    const srcEl = $("#source-path");
    if (srcEl) {
      srcEl.textContent = state.config.sourceDir || t("path.default");
      srcEl.title = state.config.sourceDir || "";
    }
    const outEl = $("#out-path");
    if (outEl) {
      outEl.textContent = state.config.outDir || t("path.default");
      outEl.title = state.config.outDir || "";
    }

    const autoSave = $("#auto-save");
    if (autoSave) autoSave.checked = state.config.autoSave;

    const languageSelect = $("#output-language");
    if (languageSelect) {
      Array.from(languageSelect.options).forEach((optionEl) => {
        const option = getOutputLanguageOption(optionEl.value);
        optionEl.textContent = option.nativeLabel || option.label;
      });
      languageSelect.value = getOutputLanguageOption().key;
    }
    const lengthSelect = $("#diary-length");
    if (lengthSelect) {
      Array.from(lengthSelect.options).forEach((optionEl) => {
        optionEl.textContent = t(`length.${optionEl.value}`);
      });
      lengthSelect.value = getDiaryLengthOption().key;
    }
    const modelSelect = $("#codex-model");
    if (modelSelect) {
      const options = codexModelOptions();
      modelSelect.replaceChildren(
        ...options.map((option) => el("option", { value: option.key }, option.label || option.key)),
      );
      modelSelect.value = getCodexModelOption().key;
      modelSelect.setAttribute("aria-label", t("status.modelLabel"));
    }
    const viewSegmented = $("#view-segmented");
    if (viewSegmented) {
      const hiddenOutsideDiary = state.nav !== "diary";
      viewSegmented.hidden = hiddenOutsideDiary;
      viewSegmented.setAttribute("aria-hidden", String(hiddenOutsideDiary));
    }
    const paperTop = document.querySelector(".paper__top");
    if (paperTop) {
      const hiddenOutsideDiary = state.nav !== "diary";
      paperTop.hidden = hiddenOutsideDiary;
      paperTop.setAttribute("aria-hidden", String(hiddenOutsideDiary));
      if (hiddenOutsideDiary && state.menuOpen) toggleMenu(false);
    }
    syncOverflowActions();
    renderCodexStatus();
    syncGenerateButton();
    syncMutableControls();
  }

  function syncConfig(config) {
    if (!config) return;
    if (config.target_date) {
      state.config.targetDate = config.target_date;
      if (!state.effectiveTodayIso) state.effectiveTodayIso = config.target_date;
    }
    if (typeof config.boundary_hour === "number" && !state.boundaryPinned)
      state.config.boundaryHour = config.boundary_hour;
    if (typeof config.source_dir === "string" && !state.sourceDirPinned) state.config.sourceDir = config.source_dir;
    if (typeof config.out_dir === "string" && !state.outDirPinned) state.config.outDir = config.out_dir;
    const language =
      normalizeLanguageKey(config.output_language_code) ||
      normalizeLanguageKey(config.target_language_code) ||
      normalizeLanguageKey(config.language_code) ||
      normalizeLanguageKey(config.output_language) ||
      normalizeLanguageKey(config.target_language) ||
      normalizeLanguageKey(config.preferred_language) ||
      normalizeLanguageKey(config.language) ||
      normalizeLanguageKey(config.locale);
    if (language && !state.languagePinned) state.config.outputLanguage = language;
    const diaryLength =
      normalizeDiaryLengthKey(config.diary_length_code) ||
      normalizeDiaryLengthKey(config.diary_length) ||
      normalizeDiaryLengthKey(config.length);
    if (diaryLength && !state.diaryLengthPinned) state.config.diaryLength = diaryLength;
    const codexModel =
      normalizeCodexModelKey(config.codex_model) ||
      normalizeCodexModelKey(config.selected_model) ||
      normalizeCodexModelKey(config.configured_model);
    if (codexModel && !state.codexModelPinned) state.config.codexModel = codexModel;
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

  function syncReadiness(readiness) {
    if (!readiness || typeof readiness !== "object") return;
    state.readiness = {
      loaded: true,
      sourceDir: readiness.source_dir || state.config.sourceDir || "",
      sourceExists: Boolean(readiness.source_exists),
      sourceMarkdownCount: Number.isFinite(readiness.source_markdown_count)
        ? readiness.source_markdown_count
        : null,
      outDir: readiness.out_dir || state.config.outDir || "",
      outExists: Boolean(readiness.out_exists),
    };
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
      configuredModel: normalizeCodexModelKey(codex.configured_model) || "",
      selectedModel: normalizeCodexModelKey(codex.selected_model) || state.config.codexModel,
    };
    if (!state.codexModelPinned && state.codex.selectedModel) {
      state.config.codexModel = state.codex.selectedModel;
    }
    renderConfig();
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
      ? (codex.detail || t("status.detail.connected"))
      : loaded
        ? (codex.detail || t("status.detail.login"))
        : t("status.detail.wait");
    host.title = detailText;

    const text = host.querySelector(".bridge-status__text");
    if (text) {
      text.textContent = connected
        ? t("status.text.connected")
        : loaded
          ? connectable
            ? t("status.text.connect")
            : t("status.text.check")
          : t("status.text.loading");
    }

    const modelSelect = host.querySelector("#codex-model");
    if (modelSelect) {
      modelSelect.disabled = state.busy || !loaded;
      modelSelect.title = detailText;
      modelSelect.setAttribute("aria-label", t("status.modelLabel"));
      modelSelect.value = getCodexModelOption().key;
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
        action.textContent = connectable ? t("status.action.connect") : t("status.action.check");
        action.disabled = state.busy;
      }
    }
  }

  function renderConnectionPrompt() {
    const codex = state.codex || {};
    const actionLabel = codex.connectable ? t("status.text.connect") : t("status.text.check");
    const body = codex.connected ? t("connect.body.connected") : t("connect.body.default");

    const content = [
      el("div", { class: "empty__badge" }, t("connect.badge")),
      el("h2", { class: "empty__title" }, [
        document.createTextNode(t("connect.title")),
      ]),
      el("p", { class: "empty__copy" }, body),
    ];

    if (codex.loaded) {
      content.push(
        el(
          "button",
          {
            type: "button",
            class: "empty__action",
            "data-action": "codex-connect",
            disabled: state.busy,
          },
          actionLabel,
        ),
      );
    }

    return el("div", { class: "empty-stack" }, [
      el("section", { class: "empty empty--connection" }, content),
      renderReadinessCard(),
    ]);
  }

  function showToast(text) {
    let toast = document.querySelector(".toast");
    if (!toast) {
      toast = document.createElement("div");
      toast.className = "toast";
      toast.setAttribute("role", "status");
      toast.setAttribute("aria-live", "polite");
      document.body.appendChild(toast);
    }
    toast.textContent = text;
    toast.classList.add("is-visible");
    clearTimeout(showToast._t);
    const duration = clamp(1800 + String(text || "").length * 45, 2200, 5200);
    showToast._t = setTimeout(() => toast.classList.remove("is-visible"), duration);
  }

  function setBusy(busy, kind = null) {
    const previousKind = state.busyKind;
    state.busy = busy;
    state.busyKind = busy ? kind || state.busyKind : null;
    if (state.busyKind === "generate") {
      toggleSettings(false);
      toggleMenu(false);
    }
    syncGenerateButton();
    syncMutableControls();
    if (state.busy && state.busyKind === "generate") {
      renderStage();
      startLoadingPulse();
      updateLoadingView();
    } else if (!state.busy && previousKind === "generate") {
      stopLoadingPulse();
      state.generationMeta = null;
      state.generationProgress = null;
      renderStage();
    } else if (!state.busy) {
      stopLoadingPulse();
    }
    renderCodexStatus();
  }

  /* Actions ------------------------------------------------------------- */
  function withTimeout(promise, ms, onTimeout) {
    let timeoutId;
    const timer = new Promise((_, reject) => {
      timeoutId = setTimeout(
        async () => {
          if (onTimeout) {
            try {
              await onTimeout();
            } catch {
              // The original timeout message is more useful to the user here.
            }
          }
          reject(
            new Error(
              t("warning.timeout", {
                seconds: Math.round(ms / 1000),
              }),
            ),
          );
        },
        ms,
      );
    });
    return Promise.race([promise, timer]).finally(() => clearTimeout(timeoutId));
  }

  async function cancelGeneration() {
    const bridge = api();
    if (!bridge || state.busyKind !== "generate" || isCancellingGeneration()) return;
    try {
      const payload = await bridge.cancel_generation();
      if (payload?.progress) syncGenerationProgress(payload.progress);
      setFooter(t("footer.cancelling"));
      setWarning("");
    } catch (err) {
      setWarning(String(err && err.message ? err.message : err));
    }
  }

  async function generate() {
    const bridge = api();
    if (!bridge) {
      setWarning(t("warning.webview"));
      return;
    }
    if (state.busyKind === "generate") {
      await cancelGeneration();
      return;
    }
    if (isCodexChecking()) {
      setFooter(t("status.text.loading"));
      setWarning("");
      return;
    }
    if (needsCodexConnection()) {
      state.data = null;
      renderStage();
      if (canConnectCodex()) {
        await connectCodex();
        return;
      }
      setFooter(t("footer.connectFirst"));
      setWarning(t("connect.title"));
      return;
    }
    if (state.busy) return;
    const language = getOutputLanguageOption();
    const requestOutDir = state.config.outDir;
    state.generationMeta = {
      targetDate: state.config.targetDate,
      languageKey: language.key,
      diaryLengthKey: state.config.diaryLength,
      startedAt: Date.now(),
    };
    syncGenerationProgress(null);
    setBusy(true, "generate");
    toggleMenu(false);
    setFooter(t("footer.generating", { language: displayLanguageLabel(language.key) }));
    setWarning("");
    try {
      const payload = await bridge.generate({
          target_date: state.config.targetDate,
          boundary_hour: state.config.boundaryHour,
          mode: state.config.mode,
          source_dir: state.config.sourceDir,
          out_dir: requestOutDir,
          auto_save: state.config.autoSave,
          diary_length_code: state.config.diaryLength,
          codex_model: state.config.codexModel,
          ...currentLanguagePayload(),
        });
      if (payload?.cancelled) {
        syncGenerationProgress(payload.progress);
        setFooter(t("footer.cancelled"));
        setWarning("");
        showToast(t("toast.cancelled"));
        return;
      }
      if (payload?.error) {
        syncGenerationProgress(payload.progress);
        setFooter(t("footer.generateFailed"));
        setWarning(payload.error);
        return;
      }
      syncGenerationProgress(payload.progress);
      state.data = payload;
      state.config.targetDate = payload.target_date;
      state.selectedDateIso = payload.target_date;
      state.selectedWeekStart = null;
      state.view = "diary";
      state.nav = "diary";
      state.timelineVisibleCount = TIMELINE_PREVIEW;
      setCalendarCursor(payload.target_date);
      if (payload.diary_length_code) state.config.diaryLength = payload.diary_length_code;
      if (payload.codex_model) state.config.codexModel = payload.codex_model;
      renderConfig();
      setNavActive();
      syncSegmented();
      renderStage();
      setFooter(
        t("footer.generated", {
          date: formatDisplayDate(payload.target_date),
          language: displayLanguageLabel(language.key),
          saved: payload.saved_path ? ` ${t("foot.saved")}.` : "",
        }),
      );
      if (payload.warnings?.length) setWarning(payload.warnings.join(" · "));
      refreshLists(requestOutDir);
      refreshReadiness();
    } catch (err) {
      setFooter(t("footer.generateFailed"));
      setWarning(String(err && err.message ? err.message : err));
    } finally {
      setBusy(false);
    }
  }

  async function connectCodex() {
    const bridge = api();
    if (!bridge) {
      setWarning(t("warning.webview"));
      return;
    }
    if (state.busy) return;
    if (!state.codex.loaded || !state.codex.connected) {
      setFooter(t("status.text.loading"));
    }
    setBusy(true, "connect");
    try {
      const payload = await bridge.connect_codex();
      if (payload?.codex) {
        syncCodexStatus(payload.codex);
      }
      if (payload?.error) {
        setWarning(payload.error);
        setFooter(t("footer.connectFailed"));
        return;
      }
      if (payload?.connected && payload?.codex?.connected) {
        setFooter(t("footer.connected"));
        showToast(t("toast.codexReady"));
      } else if (payload?.message) {
        setFooter(t("footer.rechecked"));
        setWarning("");
      } else {
        setFooter(t("footer.rechecked"));
      }
      if (!state.data) renderStage();
    } catch (err) {
      setWarning(String(err && err.message ? err.message : err));
      setFooter(t("footer.connectFailed"));
    } finally {
      setBusy(false);
    }
  }

  function showEmptyDateState(iso, reasonText = "") {
    state.viewRequestId += 1;
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
          ? t("footer.connectFirst")
          : "";
      setFooter(
        reasonText ||
          connectionMessage ||
          t("footer.noSavedForDate", {
            date: formatDisplayDate(iso),
          }),
      );
    }
    setWarning("");
  }

  async function openDate(iso, options = {}) {
    const { clearOnMissing = false } = options;
    const bridge = api();
    if (!bridge) return;
    const requestId = (state.viewRequestId += 1);
    try {
      const payload = await bridge.load_date(iso, state.config.outDir);
      if (requestId !== state.viewRequestId) return;
      if (payload?.error) {
        state.config.targetDate = iso;
        if (clearOnMissing) {
          showEmptyDateState(iso);
          return;
        }
        setFooter(
          t("footer.openDiaryFailed", {
            date: formatDisplayDate(iso),
          }),
        );
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
      setFooter(
        t("footer.openedDiary", {
          date: formatDisplayDate(iso),
        }),
      );
      setWarning("");
    } catch (err) {
      if (requestId !== state.viewRequestId) return;
      setWarning(String(err));
    }
  }

  function syncTargetDateView() {
    if (!state.config.targetDate) return;
    setCalendarCursor(state.config.targetDate);
    if (!api()) {
      showEmptyDateState(state.config.targetDate);
      return;
    }
    openDate(state.config.targetDate, { clearOnMissing: true });
  }

  async function openWeek(iso) {
    const bridge = api();
    if (!bridge) return;
    const requestId = (state.viewRequestId += 1);
    try {
      const payload = await bridge.load_week(iso, state.config.outDir, currentUiLanguage());
      if (requestId !== state.viewRequestId) return;
      if (payload?.error) {
        setFooter(t("footer.openWeekFailed"));
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
      setFooter(
        t("footer.openedWeek", {
          label: payload.label,
        }),
      );
      setWarning("");
    } catch (err) {
      if (requestId !== state.viewRequestId) return;
      setWarning(String(err));
    }
  }

  async function refreshLists(outDir = state.config.outDir) {
    const bridge = api();
    if (!bridge) return;
    try {
      const entries = await bridge.list_entries(outDir);
      state.dates = entries.dates || [];
      state.weeks = entries.weeks || [];
      renderSideDates();
      if (state.nav === "calendar" || state.nav === "archive") renderStage();
    } catch (err) {
      console.error(err);
    }
  }

  async function refreshReadiness({ rerender = false } = {}) {
    const bridge = api();
    if (!bridge || !bridge.readiness) return;
    try {
      syncReadiness(await bridge.readiness(state.config.sourceDir, state.config.outDir));
      if (rerender && !state.data) renderStage({ preserveScroll: true });
    } catch (err) {
      console.error(err);
    }
  }

  async function pickFolder(kind) {
    if (isGenerationLocked()) return;
    const bridge = api();
    if (!bridge) return;
    toggleMenu(false);
    const current = kind === "source" ? state.config.sourceDir : state.config.outDir;
    const picked = await bridge.pick_folder(kind, current);
    if (!picked) return;
    if (kind === "source") state.config.sourceDir = picked;
    else state.config.outDir = picked;
    writeTextStorage(kind === "source" ? SOURCE_DIR_KEY : OUT_DIR_KEY, picked);
    if (kind === "source") state.sourceDirPinned = true;
    else state.outDirPinned = true;
    renderConfig();
    await refreshReadiness({ rerender: true });
    await refreshLists();
    if (kind === "out" && state.config.targetDate) {
      syncTargetDateView();
    }
    showToast(kind === "source" ? t("toast.sourceChanged") : t("toast.outputChanged"));
  }

  async function copyCurrentView() {
    if (!state.data) {
      showToast(t("toast.nothingToCopy"));
      return;
    }
    const views = state.data.views || {};
    const key = state.view === "raw" ? "full" : state.view;
    const text = views[key] || views.full || state.data.markdown || "";
    if (!text.trim()) {
      showToast(t("toast.nothingToCopy"));
      return;
    }
    try {
      await navigator.clipboard.writeText(text);
      showToast(t("toast.copied"));
    } catch {
      const bridge = api();
      if (bridge) {
        const copied = await bridge.copy_to_clipboard(text);
        showToast(copied ? t("toast.copied") : t("toast.copyFailed"));
      } else {
        showToast(t("toast.copyFailed"));
      }
    }
  }

  async function openExternal() {
    const bridge = api();
    if (!bridge || !state.data?.saved_path) {
      showToast(t("toast.noSavedFile"));
      return;
    }
    const opened = await bridge.open_external(state.data.saved_path);
    if (!opened) {
      showToast(t("toast.openExternalFailed"));
    }
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
    if (isGenerationLocked()) return;
    if (!state.config.targetDate) return;
    const d = new Date(`${state.config.targetDate}T12:00:00`);
    d.setDate(d.getDate() + days);
    state.config.targetDate = d.toISOString().slice(0, 10);
    setCalendarCursor(state.config.targetDate);
    renderConfig();
    syncTargetDateView();
  }

  async function jumpToday() {
    if (isGenerationLocked()) return;
    const bridge = api();
    if (!bridge) return;
    try {
      const iso = await bridge.today(state.config.boundaryHour);
      if (!iso) return;
      state.config.targetDate = iso;
      state.effectiveTodayIso = iso;
      setCalendarCursor(iso);
      renderConfig();
      syncTargetDateView();
      showToast(t("toast.todayAdjusted"));
    } catch (err) {
      setWarning(String(err && err.message ? err.message : err));
    }
  }

  function shiftBoundary(delta) {
    if (isGenerationLocked()) return;
    const next = Math.max(0, Math.min(23, state.config.boundaryHour + delta));
    const requestId = (state.boundaryRequestId += 1);
    const requestDate = state.config.targetDate;
    state.config.boundaryHour = next;
    writeTextStorage(BOUNDARY_HOUR_KEY, String(next));
    state.boundaryPinned = true;
    renderConfig();
    const bridge = api();
    if (bridge && state.config.targetDate) {
      bridge
        .recompute_target(requestDate, next)
        .then((iso) => {
          if (requestId !== state.boundaryRequestId || state.config.boundaryHour !== next) return;
          if (iso) {
            state.config.targetDate = iso;
            state.effectiveTodayIso = iso;
            setCalendarCursor(iso);
            renderConfig();
            syncTargetDateView();
          }
        })
        .catch(() => {});
    }
  }

  function openDatePicker() {
    if (isGenerationLocked()) return;
    if (state.config.targetDate) {
      setCalendarCursor(state.config.targetDate);
      state.selectedDateIso = state.selectedDateIso || state.config.targetDate;
    }
    state.nav = "calendar";
    setNavActive();
    renderConfig();
    renderStage();
    setFooter(t("footer.calendarHint"));
    setWarning("");
  }

  function toggleSettings(force) {
    const nextOpen = typeof force === "boolean" ? force : !state.settingsOpen;
    if (nextOpen === state.settingsOpen) return;
    if (state.settingsHideTimer) {
      clearTimeout(state.settingsHideTimer);
      state.settingsHideTimer = null;
    }
    if (nextOpen) {
      state.settingsLastFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    }
    state.settingsOpen = nextOpen;
    document.body.classList.toggle("is-settings-open", state.settingsOpen);
    const panel = $("#settings-panel");
    if (panel) {
      if (state.settingsOpen) {
        panel.hidden = false;
        panel.setAttribute("aria-hidden", "false");
        panel.getBoundingClientRect();
        requestAnimationFrame(() => {
          if (!state.settingsOpen) return;
          panel.classList.add("is-open");
          panel.querySelector('[data-action="toggle-settings"]')?.focus({ preventScroll: true });
        });
      } else {
        panel.classList.remove("is-open");
        panel.setAttribute("aria-hidden", "true");
        state.settingsHideTimer = setTimeout(() => {
          if (!state.settingsOpen) panel.hidden = true;
          state.settingsHideTimer = null;
        }, 240);
      }
    }
    if (state.settingsOpen && state.menuOpen) toggleMenu(false);
    syncSettingsModalState();
    const launcher = document.querySelector(".side-settings");
    if (launcher) launcher.setAttribute("aria-expanded", String(state.settingsOpen));
    if (!state.settingsOpen && panel?.contains(document.activeElement) && state.settingsLastFocus?.isConnected) {
      state.settingsLastFocus.focus({ preventScroll: true });
    }
  }

  function syncSettingsModalState() {
    document.querySelectorAll(".sidebar, .main").forEach((node) => {
      if (!(node instanceof HTMLElement)) return;
      if (state.settingsOpen) {
        node.setAttribute("aria-hidden", "true");
        if ("inert" in node) node.inert = true;
      } else {
        node.removeAttribute("aria-hidden");
        if ("inert" in node) node.inert = false;
      }
    });
  }

  function trapSettingsFocus(event) {
    if (!state.settingsOpen || event.key !== "Tab") return;
    const panel = $("#settings-panel");
    if (!panel) return;
    const focusable = Array.from(
      panel.querySelectorAll(
        'button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), a[href], [tabindex]:not([tabindex="-1"])',
      ),
    ).filter((node) => node instanceof HTMLElement && node.offsetParent !== null);
    if (!focusable.length) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }

  function toggleMenu(force) {
    state.menuOpen = typeof force === "boolean" ? force : !state.menuOpen;
    const menu = $("#overflow-menu");
    if (menu) menu.hidden = !state.menuOpen;
    const btn = document.querySelector('[data-action="toggle-menu"]');
    if (btn) btn.setAttribute("aria-expanded", String(state.menuOpen));
    if (state.menuOpen) {
      requestAnimationFrame(() => {
        menu?.querySelector("button:not(:disabled)")?.focus({ preventScroll: true });
      });
    }
  }

  function bindWheelScroll(node) {
    if (!node) return;
    node.addEventListener(
      "wheel",
      (event) => {
        const canScrollY = node.scrollHeight > node.clientHeight + 1;
        if (!canScrollY) return;

        const prevTop = node.scrollTop;

        if (canScrollY && event.deltaY) node.scrollTop += event.deltaY;

        if (node.scrollTop !== prevTop) {
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
        if (isGenerationLocked()) {
          e.target.value = state.config.targetDate || "";
          return;
        }
        state.config.targetDate = e.target.value;
        renderConfig();
        syncTargetDateView();
      });
    }

    document.querySelectorAll('input[name="view"]').forEach((r) =>
      r.addEventListener("change", (e) => {
        if (isGenerationLocked()) return;
        state.view = e.target.value;
        renderStage();
      }),
    );

    const autoSave = $("#auto-save");
    if (autoSave) {
      autoSave.addEventListener("change", (e) => {
        if (isGenerationLocked()) {
          e.target.checked = state.config.autoSave;
          return;
        }
        state.config.autoSave = e.target.checked;
        writeTextStorage(AUTO_SAVE_KEY, String(state.config.autoSave));
        state.autoSavePinned = true;
      });
    }

    const outputLanguage = $("#output-language");
    if (outputLanguage) {
      outputLanguage.addEventListener("change", (e) => {
        if (isGenerationLocked()) {
          e.target.value = getOutputLanguageOption().key;
          return;
        }
        setOutputLanguage(e.target.value);
        showToast(
          t("toast.languageChanged", {
            language: displayLanguageLabel(),
          }),
        );
      });
    }

    const diaryLength = $("#diary-length");
    if (diaryLength) {
      diaryLength.addEventListener("change", (e) => {
        if (isGenerationLocked()) {
          e.target.value = getDiaryLengthOption().key;
          return;
        }
        setDiaryLength(e.target.value);
        showToast(
          t("toast.lengthChanged", {
            length: t(`length.${getDiaryLengthOption().key}`),
          }),
        );
      });
    }

    const codexModel = $("#codex-model");
    if (codexModel) {
      codexModel.addEventListener("change", (e) => {
        if (isGenerationLocked()) {
          e.target.value = getCodexModelOption().key;
          return;
        }
        setCodexModel(e.target.value);
        showToast(t("toast.modelChanged", { model: getCodexModelOption().label }));
      });
    }

    document.querySelectorAll(".side-nav__item").forEach((btn) => {
      btn.addEventListener("click", () => {
        if (isGenerationLocked()) return;
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
      if (
        state.settingsOpen &&
        !event.target.closest("#settings-panel") &&
        !event.target.closest('[data-action="toggle-settings"]')
      ) {
        state.suppressNextClick = true;
        toggleSettings(false);
      }
    });

    document.addEventListener("click", (event) => {
      if (state.suppressNextClick) {
        state.suppressNextClick = false;
        event.preventDefault();
        event.stopPropagation();
        return;
      }
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
      if (isGenerationLocked() && action !== "generate") return;
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
      trapSettingsFocus(e);
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
    applyStaticUiCopy();
    bindEvents();
    setNavActive();
    syncSegmented();
    renderStage();
    renderConfig();
    setFooter(t("footer.ready"));

    await new Promise((resolve) => {
      if (api()) return resolve();
      window.addEventListener("pywebviewready", resolve, { once: true });
    });

    const bridge = api();
    try {
      const initial = await bridge.get_state();
      syncConfig(initial.config);
      syncReadiness(initial.readiness);
      syncCodexStatus(initial.codex || {
        available: Boolean(initial.generation_available),
        connected: Boolean(initial.generation_available),
        connectable: false,
        message: initial.status || "",
        detail: initial.status || "",
      });
      syncGenerationProgress(initial.progress);
      state.dates = initial.entries?.dates || [];
      state.weeks = initial.entries?.weeks || [];
      renderSideDates();
      await refreshReadiness({ rerender: true });
      if (state.outDirPinned) await refreshLists();
      syncTargetDateView();
    } catch (err) {
      console.error(err);
    }
  }

  window.__codexDiaryOnProgress = function onCodexDiaryProgress(payload) {
    syncGenerationProgress(payload);
  };

  document.addEventListener("DOMContentLoaded", boot);
})();
