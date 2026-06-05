# tran_web — 웹 번역기

텍스트·파일 번역, Gemini AI 요약, 음성 읽기를 지원하는 번역 앱입니다.

## 프로젝트 구조

```
tran_web/
  streamlit_app.py   ← Streamlit Cloud 배포용 (메인)
  core.py            ← 번역·요약·TTS 공통 로직
  server.py          ← 로컬 Flask 서버 (선택)
  index.html         ← 정적 웹 UI (GitHub Pages용, 선택)
  requirements.txt
  .streamlit/
    config.toml
    secrets.toml.example
```

## Streamlit Community Cloud 배포 (권장)

[Streamlit Community Cloud](https://streamlit.io/cloud)에서 GitHub 저장소를 연결해 배포합니다.

### 1. 로컬 테스트

```powershell
cd d:\00_SRC\cursor_exam\tran_web
pip install -r requirements.txt
streamlit run streamlit_app.py
```

### 2. Secrets 설정

Streamlit Cloud → **App settings → Secrets**에 아래 내용 입력:

```toml
GEMINI_API_KEY = "your-api-key"
```

로컬에서는 `.env` 파일에 `GEMINI_API_KEY=...` 설정.

### 3. Cloud 배포

1. GitHub에 `tran_web` 저장소 push
2. [share.streamlit.io](https://share.streamlit.io) → **New app**
3. Repository / Branch 선택
4. **Main file path**: `streamlit_app.py`
5. **Deploy**

## 로컬 Flask 서버 (선택)

```powershell
python server.py
# http://127.0.0.1:5050
```

## 기능

- 텍스트·`.txt` 파일 번역 (14개+ 언어)
- Gemini 2.5 Flash 3단계 요약
- Gemini TTS 음성 읽기 (Streamlit) / 브라우저 TTS (정적 HTML)

## API (Flask)

- `GET /api/languages`
- `POST /api/translate`
- `POST /api/summarize`
- `POST /api/tts`
