import io
import json
import os
import wave
from pathlib import Path

from deep_translator import GoogleTranslator
from dotenv import load_dotenv
from google import genai
from google.genai import types

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

CHUNK_SIZE = 4500
TTS_CHUNK_SIZE = 1500
GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_TTS_MODEL = "gemini-2.5-flash-preview-tts"

LANGUAGES: dict[str, str] = {
    "auto": "자동 감지",
    "ko": "한국어",
    "en": "English",
    "ja": "日本語",
    "zh-CN": "中文(简体)",
    "zh-TW": "中文(繁體)",
    "es": "Español",
    "fr": "Français",
    "de": "Deutsch",
    "vi": "Tiếng Việt",
    "th": "ไทย",
    "ru": "Русский",
    "pt": "Português",
    "id": "Bahasa Indonesia",
    "ar": "العربية",
    "hi": "हिन्दी",
}

TARGET_LANGUAGES = {k: v for k, v in LANGUAGES.items() if k != "auto"}

TTS_VOICES: dict[str, str] = {
    "ko": "Kore",
    "en": "Kore",
    "ja": "Aoede",
    "zh-CN": "Aoede",
    "zh-TW": "Aoede",
    "es": "Puck",
    "fr": "Aoede",
    "de": "Charon",
    "vi": "Kore",
    "th": "Kore",
    "ru": "Charon",
    "pt": "Puck",
    "id": "Kore",
    "ar": "Kore",
    "hi": "Kore",
}

_gemini_client: genai.Client | None = None


def get_gemini_api_key() -> str:
    key = os.getenv("GEMINI_API_KEY", "")
    if key:
        return key
    try:
        import streamlit as st

        return st.secrets.get("GEMINI_API_KEY", "")
    except Exception:
        return ""


def get_gemini_client() -> genai.Client:
    global _gemini_client
    api_key = get_gemini_api_key()
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY가 없습니다. .env 또는 Streamlit Secrets에 설정해 주세요."
        )
    if _gemini_client is None:
        _gemini_client = genai.Client(api_key=api_key)
    return _gemini_client


def read_text_bytes(data: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "cp949", "euc-kr"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("텍스트 파일 인코딩을 읽을 수 없습니다. UTF-8 또는 CP949 파일을 사용해 주세요.")


def chunk_text(text: str, max_size: int = CHUNK_SIZE) -> list[str]:
    if len(text) <= max_size:
        return [text]

    chunks: list[str] = []
    paragraphs = text.split("\n")
    current = ""

    for paragraph in paragraphs:
        segment = f"{paragraph}\n"
        if len(segment) > max_size:
            if current:
                chunks.append(current)
                current = ""
            for i in range(0, len(paragraph), max_size):
                chunks.append(paragraph[i : i + max_size])
            continue

        if len(current) + len(segment) > max_size:
            chunks.append(current)
            current = segment
        else:
            current += segment

    if current:
        chunks.append(current)

    return chunks


def translate_text(text: str, source: str, target: str) -> str:
    translator = GoogleTranslator(source=source, target=target)
    return "".join(translator.translate(chunk) for chunk in chunk_text(text))


def validate_langs(source: str, target: str) -> str | None:
    if source not in LANGUAGES or target not in TARGET_LANGUAGES:
        return "지원하지 않는 언어입니다."
    if source == target:
        return "원본 언어와 번역 언어가 같습니다."
    return None


def summarize_with_gemini(text: str, lang_code: str) -> dict[str, str]:
    lang_name = TARGET_LANGUAGES.get(lang_code, "한국어")
    prompt = f"""다음 텍스트를 {lang_name}로 3단계 요약해 주세요.

텍스트:
{text[:12000]}

반드시 아래 JSON 형식만 출력하세요. 다른 설명은 넣지 마세요.
{{
  "line": "핵심을 담은 한 줄 요약",
  "short": "3~5문장의 짧은 요약",
  "detailed": "주요 내용과 핵심 포인트를 담은 상세 요약"
}}"""

    client = get_gemini_client()
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.3,
        ),
    )

    raw = (response.text or "").strip()
    data = json.loads(raw)
    return {
        "line": str(data.get("line", "")).strip(),
        "short": str(data.get("short", "")).strip(),
        "detailed": str(data.get("detailed", "")).strip(),
    }


def pcm_to_wav(pcm: bytes, channels: int = 1, rate: int = 24000, sample_width: int = 2) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(rate)
        wf.writeframes(pcm)
    return buf.getvalue()


def extract_pcm(response: object) -> bytes:
    import base64

    candidates = getattr(response, "candidates", None) or []
    for candidate in candidates:
        content = getattr(candidate, "content", None)
        if not content:
            continue
        for part in content.parts or []:
            inline = getattr(part, "inline_data", None)
            if inline and inline.data:
                data = inline.data
                if isinstance(data, str):
                    return base64.b64decode(data)
                return bytes(data)
    raise ValueError("TTS 응답에서 오디오를 찾을 수 없습니다.")


def synthesize_chunk(text: str, voice_name: str) -> bytes:
    client = get_gemini_client()
    response = client.models.generate_content(
        model=GEMINI_TTS_MODEL,
        contents=text,
        config=types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice_name)
                )
            ),
        ),
    )
    return extract_pcm(response)


def synthesize_speech(text: str, lang_code: str) -> tuple[bytes, bool]:
    voice = TTS_VOICES.get(lang_code, "Kore")
    chunks = chunk_text(text.strip(), TTS_CHUNK_SIZE)
    truncated = len(text) > TTS_CHUNK_SIZE * 3
    if truncated:
        chunks = chunks[:3]

    pcm_parts = [synthesize_chunk(chunk, voice) for chunk in chunks]
    return pcm_to_wav(b"".join(pcm_parts)), truncated
