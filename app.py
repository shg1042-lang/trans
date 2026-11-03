import os

import openai
import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "").strip() or "gpt-6-astra"
MAX_CHARS = 5000

# 버튼 라벨 -> (모델에 전달할 언어명, 결과 제목에 표시할 이름)
LANGUAGES = {
    "영어": ("English", "English"),
    "일본어": ("Japanese", "日本語"),
    "베트남어": ("Vietnamese", "Tiếng Việt"),
}

SYSTEM_PROMPT = (
    "You are a professional translator. Translate the user's text into "
    "{target_language}. Preserve the original meaning, tone, formatting, and "
    "line breaks. Output only the translated text without any explanations."
)


@st.cache_resource
def get_client(api_key: str) -> OpenAI:
    return OpenAI(api_key=api_key)


def translate(text: str, target_language: str) -> str:
    response = get_client(OPENAI_API_KEY).chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT.format(target_language=target_language)},
            {"role": "user", "content": text},
        ],
    )
    return (response.choices[0].message.content or "").strip()


def error_message(exc: Exception) -> str:
    if isinstance(exc, openai.AuthenticationError):
        return "API 키 인증에 실패했습니다. .env의 OPENAI_API_KEY를 확인하세요."
    if isinstance(exc, openai.RateLimitError):
        return "요청 한도를 초과했거나 크레딧이 부족합니다. 잠시 후 다시 시도하세요."
    if isinstance(exc, openai.APIConnectionError):
        return "OpenAI 서버에 연결할 수 없습니다. 네트워크 상태를 확인하세요."
    if isinstance(exc, openai.NotFoundError):
        return f"모델 '{OPENAI_MODEL}'을(를) 찾을 수 없습니다. .env의 OPENAI_MODEL을 확인하세요."
    if isinstance(exc, openai.BadRequestError):
        return "잘못된 요청입니다. 입력 내용이나 모델 설정을 확인하세요."
    return f"번역 중 알 수 없는 오류가 발생했습니다: {type(exc).__name__}"


def clear_all() -> None:
    st.session_state.source_text = ""
    st.session_state.result = None
    st.session_state.result_label = None


st.set_page_config(page_title="다국어 번역기", page_icon="🌐", layout="centered")

st.markdown(
    """
    <style>
    .block-container { max-width: 760px; padding-top: 2.5rem; }
    h1 { font-size: clamp(1.8rem, 7vw, 2.75rem) !important; word-break: keep-all; }
    .app-subtitle { opacity: 0.7; margin-top: -0.6rem; margin-bottom: 1.2rem; }
    .char-count { text-align: right; font-size: 0.85rem; opacity: 0.65; margin-top: -0.6rem; }
    .char-count.over { color: #e5484d; opacity: 1; font-weight: 600; }
    /* 좁은 화면에서도 언어 버튼 3개를 가로 한 줄로 유지 */
    .st-key-lang_buttons [data-testid="stHorizontalBlock"] { flex-wrap: nowrap; }
    .st-key-lang_buttons [data-testid="stColumn"] { min-width: 0 !important; }
    .st-key-lang_buttons button { padding-left: 0.25rem; padding-right: 0.25rem; }
    /* 번역 결과의 복사 아이콘을 마우스를 올리지 않아도 항상 표시 (터치 기기 대응) */
    .st-key-result_card [data-testid="stCode"] > div:has([data-testid="stElementToolbarButton"]),
    .st-key-result_card [data-testid="stCode"] > div:has([data-testid="stElementToolbarButton"]) * {
        opacity: 1 !important; visibility: visible !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.session_state.setdefault("source_text", "")
st.session_state.setdefault("result", None)
st.session_state.setdefault("result_label", None)

st.title("🌐 다국어 번역기")
st.markdown('<p class="app-subtitle">글을 입력하고 번역할 언어를 선택하세요.</p>', unsafe_allow_html=True)

if not OPENAI_API_KEY:
    st.error("OPENAI_API_KEY가 설정되지 않았습니다. .env 파일에 API 키를 추가한 뒤 앱을 다시 실행하세요.")

text = st.text_area(
    "번역할 글",
    key="source_text",
    height=200,
    placeholder="여기에 번역할 글을 입력하세요. (Ctrl+Enter로 입력 확정)",
)

over = len(text) > MAX_CHARS
st.markdown(
    f'<div class="char-count{" over" if over else ""}" id="char-count">{len(text):,} / {MAX_CHARS:,}자</div>',
    unsafe_allow_html=True,
)
# Streamlit은 입력창에서 포커스가 빠질 때만 값을 보내므로, 글자 수는 브라우저에서 직접 실시간 갱신한다.
# (st.text_area의 max_chars는 초과 분량을 붙여넣으면 입력 전체를 조용히 무시하므로 사용하지 않는다.)
st.html(
    f"""<script>
    if (!window.__charCounterBound) {{
      window.__charCounterBound = true;
      document.addEventListener("input", (e) => {{
        if (!e.target.matches('textarea[aria-label="번역할 글"]')) return;
        const el = document.getElementById("char-count");
        if (!el) return;
        const n = e.target.value.length;
        el.textContent = n.toLocaleString("en-US") + " / {MAX_CHARS:,}자";
        el.classList.toggle("over", n > {MAX_CHARS});
      }});
    }}
    </script>""",
    unsafe_allow_javascript=True,
)

clicked = None
with st.container(key="lang_buttons"):
    for col, (label, lang) in zip(st.columns(len(LANGUAGES)), LANGUAGES.items()):
        if col.button(label, width="stretch", type="primary", disabled=not OPENAI_API_KEY):
            clicked = lang

if clicked:
    target_language, display_name = clicked
    if not text.strip():
        st.warning("번역할 글을 입력하세요.")
    elif over:
        st.warning(f"입력은 최대 {MAX_CHARS:,}자까지 가능합니다. (현재 {len(text):,}자)")
    else:
        try:
            with st.spinner(f"{display_name}(으)로 번역 중..."):
                translated = translate(text, target_language)
            if translated:
                st.session_state.result = translated
                st.session_state.result_label = display_name
            else:
                st.warning("모델이 빈 번역 결과를 반환했습니다. 다시 시도하세요.")
        except Exception as exc:  # noqa: BLE001 - 모든 오류를 사용자 메시지로 변환
            st.error(error_message(exc))

if st.session_state.result:
    with st.container(border=True, key="result_card"):
        st.markdown(f"**번역 결과 ({st.session_state.result_label})**")
        st.code(st.session_state.result, language=None, wrap_lines=True)
        st.caption("결과 오른쪽 위의 복사 아이콘을 눌러 복사할 수 있습니다.")

st.button("입력 지우기", on_click=clear_all)
