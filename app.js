let SOURCE_LANGUAGES = { auto: "자동 감지", ko: "한국어", en: "English" };
let TARGET_LANGUAGES = { ko: "한국어", en: "English" };

const sourceLang = document.getElementById("sourceLang");
const targetLang = document.getElementById("targetLang");
const inputText = document.getElementById("inputText");
const outputText = document.getElementById("outputText");
const translateBtn = document.getElementById("translateBtn");
const clearBtn = document.getElementById("clearBtn");
const copyBtn = document.getElementById("copyBtn");
const downloadBtn = document.getElementById("downloadBtn");
const swapBtn = document.getElementById("swapBtn");
const statusEl = document.getElementById("status");
const statusText = statusEl?.querySelector(".status-text");
const fileInput = document.getElementById("fileInput");
const fileBtn = document.getElementById("fileBtn");
const charCount = document.getElementById("charCount");
const outputCharCount = document.getElementById("outputCharCount");
const fileBadge = document.getElementById("fileBadge");
const dropZone = document.getElementById("dropZone");
const dropOverlay = document.getElementById("dropOverlay");
const ttsBtn = document.getElementById("ttsBtn");
const ttsLabel = document.getElementById("ttsLabel");
const summarizeBtn = document.getElementById("summarizeBtn");
const summaryLine = document.getElementById("summaryLine");
const summaryShort = document.getElementById("summaryShort");
const summaryDetailed = document.getElementById("summaryDetailed");

let translating = false;
let summarizing = false;
let ttsSpeaking = false;
let selectedFile = null;
let dragCounter = 0;

function apiUrl(path) {
  const meta = document.querySelector('meta[name="api-base"]');
  const base = (meta?.content || "").replace(/\/$/, "");
  return `${base}${path}`;
}

const TTS_LOCALE_MAP = {
  ko: "ko-KR",
  en: "en-US",
  ja: "ja-JP",
  "zh-CN": "zh-CN",
  "zh-TW": "zh-TW",
  es: "es-ES",
  fr: "fr-FR",
  de: "de-DE",
  vi: "vi-VN",
  th: "th-TH",
  ru: "ru-RU",
  pt: "pt-PT",
  id: "id-ID",
  ar: "ar-SA",
  hi: "hi-IN",
};

function populateSelect(select, languages, selected) {
  select.innerHTML = "";
  for (const [code, name] of Object.entries(languages)) {
    const option = document.createElement("option");
    option.value = code;
    option.textContent = name;
    if (code === selected) {
      option.selected = true;
    }
    select.appendChild(option);
  }
}

function setStatus(message, isError = false) {
  if (statusText) {
    statusText.textContent = message;
  } else if (statusEl) {
    statusEl.textContent = message;
  }
  statusEl?.classList.toggle("is-error", isError);
}

async function parseJsonResponse(response, fallbackMessage) {
  const contentType = response.headers.get("content-type") || "";
  if (!contentType.includes("application/json")) {
    if (response.status === 404) {
      const onGithubPages = location.hostname.endsWith("github.io");
      throw new Error(
        onGithubPages
          ? "API 서버에 연결할 수 없습니다. index.html의 api-base에 백엔드 URL을 설정해 주세요."
          : "API를 찾을 수 없습니다. 서버를 재시작해 주세요. (python server.py)"
      );
    }
    throw new Error(fallbackMessage);
  }
  return response.json();
}

function updateCharCounts() {
  const inputLen = inputText.value.length;
  charCount.textContent = inputLen > 0 ? `${inputLen.toLocaleString()}자` : "";
  const outputLen = outputText.value.length;
  outputCharCount.textContent = outputLen > 0 ? `${outputLen.toLocaleString()}자` : "";
}

function setFileBadge(file) {
  if (file) {
    fileBadge.hidden = false;
    fileBadge.textContent = file.name;
  } else {
    fileBadge.hidden = true;
    fileBadge.textContent = "";
  }
}

function setBusy(busy) {
  translating = busy;
  translateBtn.disabled = busy;
  translateBtn.classList.toggle("is-busy", busy);
}

function setSummaryPlaceholder() {
  summaryLine.textContent = "번역 결과를 기반으로 요약이 표시됩니다.";
  summaryLine.classList.add("is-placeholder");
  summaryShort.textContent = "—";
  summaryShort.classList.add("is-placeholder");
  summaryDetailed.textContent = "—";
  summaryDetailed.classList.add("is-placeholder");
}

function renderSummary(summary) {
  summaryLine.textContent = summary.line || "—";
  summaryShort.textContent = summary.short || "—";
  summaryDetailed.textContent = summary.detailed || "—";
  [summaryLine, summaryShort, summaryDetailed].forEach((el) => {
    el.classList.remove("is-placeholder", "is-loading");
  });
}

function setSummaryLoading() {
  [summaryLine, summaryShort, summaryDetailed].forEach((el) => {
    el.textContent = "요약 생성 중...";
    el.classList.add("is-loading");
    el.classList.remove("is-placeholder");
  });
}

function setTtsPlaying(playing) {
  ttsSpeaking = playing;
  ttsBtn.classList.toggle("is-playing", playing);
  const caption = playing ? "일시중지" : "음성읽기";
  if (ttsLabel) ttsLabel.textContent = caption;
  ttsBtn.title = caption;
  ttsBtn.setAttribute("aria-label", caption);
}

function pickVoice(locale) {
  const voices = window.speechSynthesis?.getVoices() || [];
  const langPrefix = locale.split("-")[0];
  return (
    voices.find((v) => v.lang === locale) ||
    voices.find((v) => v.lang.startsWith(langPrefix)) ||
    null
  );
}

function stopTts() {
  if (window.speechSynthesis) {
    window.speechSynthesis.cancel();
  }
  setTtsPlaying(false);
}

async function loadLanguages() {
  try {
    const response = await fetch(apiUrl("/api/languages"));
    const data = await response.json();
    SOURCE_LANGUAGES = data.source;
    TARGET_LANGUAGES = data.target;
    populateSelect(sourceLang, SOURCE_LANGUAGES, "auto");
    populateSelect(targetLang, TARGET_LANGUAGES, "en");
  } catch {
    populateSelect(sourceLang, SOURCE_LANGUAGES, "auto");
    populateSelect(targetLang, TARGET_LANGUAGES, "en");
    setStatus("언어 목록을 불러오지 못했습니다. 기본 목록을 사용합니다.", true);
  }
}

async function translate(useFile = false) {
  if (translating) return;

  const source = sourceLang.value;
  const target = targetLang.value;

  if (source === target) {
    setStatus("원본 언어와 번역 언어가 같습니다.", true);
    return;
  }

  if (useFile && selectedFile) {
    await translateViaServer(source, target);
    return;
  }

  const text = inputText.value.trim();
  if (!text) {
    setStatus("번역할 텍스트를 입력하거나 파일을 불러와 주세요.", true);
    inputText.focus();
    return;
  }

  setBusy(true);
  setStatus("번역 중...");

  try {
    const response = await fetch(apiUrl("/api/translate"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, source, target }),
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || "번역에 실패했습니다.");
    }

    outputText.value = data.result;
    updateCharCounts();
    setSummaryPlaceholder();
    setStatus(`${SOURCE_LANGUAGES[source]} → ${TARGET_LANGUAGES[target]}`);
  } catch (error) {
    setStatus(error.message, true);
  } finally {
    setBusy(false);
  }
}

async function translateViaServer(source, target) {
  if (!selectedFile) return;

  const formData = new FormData();
  formData.append("file", selectedFile);
  formData.append("source", source);
  formData.append("target", target);

  setBusy(true);
  setStatus(`파일 번역 중... (${selectedFile.name})`);

  try {
    const response = await fetch(apiUrl("/api/translate/file"), {
      method: "POST",
      body: formData,
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || "파일 번역에 실패했습니다.");
    }

    outputText.value = data.result;
    updateCharCounts();
    setSummaryPlaceholder();
    setStatus(`${data.filename} · ${SOURCE_LANGUAGES[source]} → ${TARGET_LANGUAGES[target]}`);
  } catch (error) {
    setStatus(error.message, true);
  } finally {
    setBusy(false);
  }
}

function isTextFile(file) {
  if (!file) return false;
  const name = file.name.toLowerCase();
  return file.type === "text/plain" || name.endsWith(".txt") || file.type === "";
}

function readLocalFile(file, autoTranslate = false) {
  if (!isTextFile(file)) {
    setStatus(".txt 텍스트 파일만 지원합니다.", true);
    return;
  }

  selectedFile = file;
  setFileBadge(file);
  fileInput.value = "";

  const reader = new FileReader();
  reader.onload = () => {
    inputText.value = reader.result;
    updateCharCounts();
    setStatus(`파일을 불러왔습니다: ${file.name}`);
    if (autoTranslate) {
      translate(true);
    }
  };
  reader.onerror = () => {
    setStatus("파일을 읽지 못했습니다.", true);
  };
  reader.readAsText(file, "UTF-8");
}

function handleFiles(files, autoTranslate = false) {
  const file = files?.[0];
  if (!file) return;
  readLocalFile(file, autoTranslate);
}

function swapLanguages() {
  const prevSource = sourceLang.value;
  const prevTarget = targetLang.value;
  const inputContent = inputText.value;
  const outputContent = outputText.value;

  if (prevSource === "auto") {
    setStatus("자동 감지 상태에서는 언어를 교환할 수 없습니다.", true);
    return;
  }

  if (!(prevTarget in SOURCE_LANGUAGES) || !(prevSource in TARGET_LANGUAGES)) {
    setStatus("선택한 언어 조합은 교환할 수 없습니다.", true);
    return;
  }

  sourceLang.value = prevTarget;
  targetLang.value = prevSource;

  if (outputContent) {
    inputText.value = outputContent;
    outputText.value = inputContent;
    updateCharCounts();
  }
}

function clearInput() {
  stopTts();
  inputText.value = "";
  outputText.value = "";
  selectedFile = null;
  fileInput.value = "";
  setFileBadge(null);
  updateCharCounts();
  setSummaryPlaceholder();
  setStatus("입력을 지웠습니다.");
  inputText.focus();
}

async function summarizeOutput() {
  if (summarizing) return;

  const text = outputText.value.trim();
  if (!text) {
    setStatus("요약할 번역 결과가 없습니다.", true);
    return;
  }

  summarizing = true;
  summarizeBtn.disabled = true;
  summarizeBtn.classList.add("is-busy");
  setSummaryLoading();
  setStatus("Gemini로 3단계 요약 생성 중...");

  try {
    const response = await fetch(apiUrl("/api/summarize"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, lang: targetLang.value }),
    });

    const data = await parseJsonResponse(response, "요약 API 응답이 올바르지 않습니다. 서버를 재시작해 주세요.");
    if (!response.ok) {
      throw new Error(data.error || "요약에 실패했습니다.");
    }

    renderSummary(data.summary);
    setStatus(`3단계 요약 완료 (${data.model})`);
  } catch (error) {
    setSummaryPlaceholder();
    setStatus(error.message, true);
  } finally {
    summarizing = false;
    summarizeBtn.disabled = false;
    summarizeBtn.classList.remove("is-busy");
  }
}

function startSpeech(text, langCode) {
  const locale = TTS_LOCALE_MAP[langCode] || langCode;
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = locale;
  utterance.rate = 1;

  const voice = pickVoice(locale);
  if (voice) utterance.voice = voice;

  utterance.onend = () => {
    setTtsPlaying(false);
    setStatus("읽기가 완료되었습니다.");
  };

  utterance.onerror = () => {
    if (ttsSpeaking) {
      setTtsPlaying(false);
      setStatus("음성 읽기에 실패했습니다.", true);
    }
  };

  setTtsPlaying(true);
  window.speechSynthesis.speak(utterance);
  setStatus("번역 결과를 읽는 중...");
}

function playTts() {
  if (ttsSpeaking) {
    stopTts();
    setStatus("읽기를 중지했습니다.");
    return;
  }

  const text = outputText.value.trim();
  if (!text) {
    setStatus("읽을 번역 결과가 없습니다.", true);
    return;
  }

  if (!window.speechSynthesis) {
    setStatus("이 브라우저는 음성 읽기를 지원하지 않습니다.", true);
    return;
  }

  stopTts();

  const langCode = targetLang.value;
  const voices = window.speechSynthesis.getVoices();
  if (voices.length === 0) {
    window.speechSynthesis.onvoiceschanged = () => {
      window.speechSynthesis.onvoiceschanged = null;
      startSpeech(text, langCode);
    };
    return;
  }

  startSpeech(text, langCode);
}

async function copyOutput() {
  const text = outputText.value.trim();
  if (!text) {
    setStatus("복사할 번역 결과가 없습니다.", true);
    return;
  }

  try {
    await navigator.clipboard.writeText(text);
    setStatus("클립보드에 복사했습니다.");
  } catch {
    outputText.select();
    document.execCommand("copy");
    setStatus("클립보드에 복사했습니다.");
  }
}

function downloadOutput() {
  const text = outputText.value;
  if (!text.trim()) {
    setStatus("저장할 번역 결과가 없습니다.", true);
    return;
  }

  const baseName = selectedFile
    ? selectedFile.name.replace(/\.txt$/i, "")
    : "translated";
  const targetCode = targetLang.value;
  const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `${baseName}_${targetCode}.txt`;
  link.click();
  URL.revokeObjectURL(url);
  setStatus(`저장했습니다: ${link.download}`);
}

function setDragOver(active) {
  dropZone.classList.toggle("is-dragover", active);
  dropOverlay.setAttribute("aria-hidden", active ? "false" : "true");
}

dropZone.addEventListener("dragenter", (event) => {
  event.preventDefault();
  dragCounter += 1;
  setDragOver(true);
});

dropZone.addEventListener("dragover", (event) => {
  event.preventDefault();
  event.dataTransfer.dropEffect = "copy";
});

dropZone.addEventListener("dragleave", (event) => {
  event.preventDefault();
  dragCounter -= 1;
  if (dragCounter <= 0) {
    dragCounter = 0;
    setDragOver(false);
  }
});

dropZone.addEventListener("drop", (event) => {
  event.preventDefault();
  dragCounter = 0;
  setDragOver(false);
  handleFiles(event.dataTransfer.files, true);
});

fileBtn.addEventListener("click", () => fileInput.click());
fileInput.addEventListener("change", () => {
  handleFiles(fileInput.files, false);
});

translateBtn.addEventListener("click", () => translate(!!selectedFile));
clearBtn.addEventListener("click", clearInput);
copyBtn.addEventListener("click", copyOutput);
downloadBtn.addEventListener("click", downloadOutput);
ttsBtn.addEventListener("click", playTts);
summarizeBtn.addEventListener("click", summarizeOutput);
swapBtn.addEventListener("click", swapLanguages);

inputText.addEventListener("input", () => {
  if (selectedFile && inputText.value !== "") {
    selectedFile = null;
    setFileBadge(null);
  }
  updateCharCounts();
});

inputText.addEventListener("keydown", (event) => {
  if (event.ctrlKey && event.key === "Enter") {
    event.preventDefault();
    translate(!!selectedFile);
  }
});

sourceLang.addEventListener("change", () => {
  if (inputText.value.trim() || selectedFile) {
    translate(!!selectedFile);
  }
});

targetLang.addEventListener("change", () => {
  if (inputText.value.trim() || selectedFile) {
    translate(!!selectedFile);
  }
});

if (window.speechSynthesis) {
  window.speechSynthesis.getVoices();
  window.speechSynthesis.addEventListener("voiceschanged", () => {
    window.speechSynthesis.getVoices();
  });
}

loadLanguages();
updateCharCounts();
setSummaryPlaceholder();
