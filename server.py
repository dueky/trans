"""로컬 Flask 서버 (선택). Streamlit 배포는 streamlit_app.py 사용."""

from pathlib import Path

from flask import Flask, Response, jsonify, request, send_from_directory

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

ROOT = Path(__file__).resolve().parent
app = Flask(__name__)


@app.get("/")
def index() -> object:
    return send_from_directory(ROOT, "index.html")


@app.get("/styles.css")
def styles_css() -> object:
    return send_from_directory(ROOT, "styles.css")


@app.get("/app.js")
def app_js() -> object:
    return send_from_directory(ROOT, "app.js")


@app.get("/api/health")
def health() -> object:
    return jsonify({
        "ok": True,
        "gemini": bool(get_gemini_api_key()),
        "model": GEMINI_MODEL,
        "routes": ["translate", "summarize", "tts"],
    })


@app.get("/api/languages")
def languages() -> object:
    return jsonify({"source": LANGUAGES, "target": TARGET_LANGUAGES})


@app.post("/api/translate")
def translate() -> object:
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()
    source = data.get("source", "auto")
    target = data.get("target", "en")

    if not text:
        return jsonify({"error": "번역할 텍스트를 입력해 주세요."}), 400

    error = validate_langs(source, target)
    if error:
        return jsonify({"error": error}), 400

    try:
        result = translate_text(text, source, target)
        return jsonify({"result": result, "chars": len(result)})
    except Exception as exc:
        return jsonify({"error": f"번역 중 문제가 발생했습니다. ({exc})"}), 500


@app.post("/api/translate/file")
def translate_file() -> object:
    upload = request.files.get("file")
    source = request.form.get("source", "auto")
    target = request.form.get("target", "en")

    if upload is None or not upload.filename:
        return jsonify({"error": "텍스트 파일을 선택해 주세요."}), 400

    error = validate_langs(source, target)
    if error:
        return jsonify({"error": error}), 400

    try:
        text = read_text_bytes(upload.read()).strip()
        if not text:
            return jsonify({"error": "파일 내용이 비어 있습니다."}), 400

        result = translate_text(text, source, target)
        return jsonify({
            "result": result,
            "filename": upload.filename,
            "sourceChars": len(text),
            "chars": len(result),
        })
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": f"번역 중 문제가 발생했습니다. ({exc})"}), 500


@app.post("/api/summarize")
def summarize() -> object:
    import json

    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()
    lang = data.get("lang", "ko")

    if not text:
        return jsonify({"error": "요약할 텍스트가 없습니다."}), 400

    if lang not in TARGET_LANGUAGES:
        return jsonify({"error": "지원하지 않는 언어입니다."}), 400

    try:
        summary = summarize_with_gemini(text, lang)
        if not any(summary.values()):
            return jsonify({"error": "요약 결과를 생성하지 못했습니다."}), 500
        return jsonify({"summary": summary, "model": GEMINI_MODEL})
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 500
    except json.JSONDecodeError:
        return jsonify({"error": "요약 결과를 파싱하지 못했습니다."}), 500
    except Exception as exc:
        return jsonify({"error": f"요약 중 문제가 발생했습니다. ({exc})"}), 500


@app.post("/api/tts")
def tts() -> object:
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()
    lang = data.get("lang", "ko")

    if not text:
        return jsonify({"error": "읽을 텍스트가 없습니다."}), 400

    if lang not in TARGET_LANGUAGES:
        return jsonify({"error": "지원하지 않는 언어입니다."}), 400

    try:
        wav_data, truncated = synthesize_speech(text, lang)
        response = Response(wav_data, mimetype="audio/wav")
        response.headers["X-TTS-Truncated"] = "true" if truncated else "false"
        return response
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 500
    except Exception as exc:
        return jsonify({"error": f"TTS 생성 중 문제가 발생했습니다. ({exc})"}), 500


if __name__ == "__main__":
    print(f"GEMINI_API_KEY: {'설정됨' if get_gemini_api_key() else '없음'}")
    print(f"모델: {GEMINI_MODEL} | Streamlit: streamlit run streamlit_app.py")
    app.run(host="127.0.0.1", port=5050, debug=False)
