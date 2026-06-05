import io

import streamlit as st

from core import (
    GEMINI_MODEL,
    LANGUAGES,
    TARGET_LANGUAGES,
    get_gemini_api_key,
    read_text_bytes,
    summarize_with_gemini,
    synthesize_speech,
    translate_text,
    validate_langs,
)

st.set_page_config(
    page_title="번역",
    page_icon="🌐",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
      .block-container { padding-top: 1.5rem; max-width: 1100px; }
      h1 { color: #03C75A; font-weight: 700; }
      .stTextArea textarea { font-size: 1.05rem; line-height: 1.7; }
      div[data-testid="stHorizontalBlock"] div[data-testid="column"] {
        background: #fff;
        border: 1px solid #e5e8eb;
        border-radius: 4px;
        padding: 0.5rem;
      }
      .summary-box {
        background: #fafbfc;
        border: 1px solid #e5e8eb;
        border-radius: 4px;
        padding: 1rem;
        min-height: 80px;
      }
      .summary-box h4 { color: #03C75A; margin: 0 0 0.5rem; font-size: 0.85rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

if "source_lang" not in st.session_state:
    st.session_state.source_lang = "auto"
if "target_lang" not in st.session_state:
    st.session_state.target_lang = "en"
if "output_text" not in st.session_state:
    st.session_state.output_text = ""
if "summary" not in st.session_state:
    st.session_state.summary = None

st.title("🌐 번역")
st.caption("텍스트 · 파일 · Gemini 요약 · 음성 읽기")

lang_col1, lang_swap, lang_col2 = st.columns([5, 1, 5])

with lang_col1:
    source_lang = st.selectbox(
        "원본 언어",
        options=list(LANGUAGES.keys()),
        format_func=lambda k: LANGUAGES[k],
        index=list(LANGUAGES.keys()).index(st.session_state.source_lang),
        key="source_select",
    )
    st.session_state.source_lang = source_lang

with lang_swap:
    st.write("")
    st.write("")
    if st.button("⇄", help="언어 교환", use_container_width=True):
        if source_lang == "auto":
            st.warning("자동 감지 상태에서는 언어를 교환할 수 없습니다.")
        else:
            st.session_state.source_lang, st.session_state.target_lang = (
                st.session_state.target_lang,
                st.session_state.source_lang,
            )
            if st.session_state.output_text:
                st.session_state.input_text = st.session_state.output_text
                st.session_state.output_text = ""
            st.rerun()

with lang_col2:
    target_lang = st.selectbox(
        "번역 언어",
        options=list(TARGET_LANGUAGES.keys()),
        format_func=lambda k: TARGET_LANGUAGES[k],
        index=list(TARGET_LANGUAGES.keys()).index(st.session_state.target_lang),
        key="target_select",
    )
    st.session_state.target_lang = target_lang

left, right = st.columns(2)

with left:
    st.subheader("입력")
    uploaded = st.file_uploader("텍스트 파일 (.txt)", type=["txt"], label_visibility="collapsed")
    if uploaded is not None:
        try:
            file_text = read_text_bytes(upload.getvalue())
            st.session_state.input_text = file_text
            st.success(f"파일 불러옴: {uploaded.name}")
        except ValueError as exc:
            st.error(str(exc))

    input_text = st.text_area(
        "번역할 내용",
        height=280,
        placeholder="번역할 내용을 입력해 주세요.",
        label_visibility="collapsed",
        key="input_text",
    )

with right:
    st.subheader("번역 결과")
    output_text = st.text_area(
        "결과",
        value=st.session_state.output_text,
        height=280,
        disabled=True,
        label_visibility="collapsed",
    )

btn1, btn2, btn3, btn4 = st.columns(4)

with btn1:
    do_translate = st.button("번역", type="primary", use_container_width=True)
with btn2:
    do_clear = st.button("입력 지우기", use_container_width=True)
with btn3:
    do_summarize = st.button("AI 요약", use_container_width=True)
with btn4:
    do_tts = st.button("음성읽기", use_container_width=True)

if do_clear:
    st.session_state.input_text = ""
    st.session_state.output_text = ""
    st.session_state.summary = None
    st.rerun()

if do_translate:
    text = (input_text or "").strip()
    error = validate_langs(st.session_state.source_lang, st.session_state.target_lang)
    if error:
        st.error(error)
    elif not text:
        st.error("번역할 텍스트를 입력해 주세요.")
    else:
        with st.spinner("번역 중..."):
            try:
                st.session_state.output_text = translate_text(
                    text, st.session_state.source_lang, st.session_state.target_lang
                )
                st.session_state.summary = None
                st.rerun()
            except Exception as exc:
                st.error(f"번역 중 문제가 발생했습니다. ({exc})")

if do_summarize:
    text = (st.session_state.output_text or "").strip()
    if not text:
        st.error("요약할 번역 결과가 없습니다.")
    elif not get_gemini_api_key():
        st.error("GEMINI_API_KEY가 설정되지 않았습니다. Streamlit Secrets를 확인해 주세요.")
    else:
        with st.spinner("Gemini로 3단계 요약 생성 중..."):
            try:
                st.session_state.summary = summarize_with_gemini(text, st.session_state.target_lang)
                st.success(f"요약 완료 ({GEMINI_MODEL})")
            except Exception as exc:
                st.error(f"요약 중 문제가 발생했습니다. ({exc})")

if do_tts:
    text = (st.session_state.output_text or "").strip()
    if not text:
        st.error("읽을 번역 결과가 없습니다.")
    elif not get_gemini_api_key():
        st.error("GEMINI_API_KEY가 설정되지 않았습니다.")
    else:
        with st.spinner("음성 생성 중..."):
            try:
                wav_data, truncated = synthesize_speech(text, st.session_state.target_lang)
                st.audio(io.BytesIO(wav_data), format="audio/wav")
                if truncated:
                    st.info("긴 텍스트는 일부만 읽습니다.")
            except Exception as exc:
                st.error(f"음성 생성 중 문제가 발생했습니다. ({exc})")

if st.session_state.summary:
    st.divider()
    st.subheader("AI 3단계 요약")
    s1, s2, s3 = st.columns(3)
    summary = st.session_state.summary
    with s1:
        st.markdown(
            f'<div class="summary-box"><h4>한 줄 요약</h4><p>{summary.get("line", "")}</p></div>',
            unsafe_allow_html=True,
        )
    with s2:
        st.markdown(
            f'<div class="summary-box"><h4>짧은 요약</h4><p>{summary.get("short", "")}</p></div>',
            unsafe_allow_html=True,
        )
    with s3:
        st.markdown(
            f'<div class="summary-box"><h4>상세 요약</h4><p>{summary.get("detailed", "")}</p></div>',
            unsafe_allow_html=True,
        )

if not get_gemini_api_key():
    st.sidebar.warning("GEMINI_API_KEY 미설정 — 요약·음성읽기 사용 불가")
