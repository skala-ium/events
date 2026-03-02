import os
import json
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

# ── LLM 제공자 교체 시 이 함수만 수정 ──────────────────────────────────────
def _get_model():
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
    return genai.GenerativeModel("gemini-2.5-flash")
# ────────────────────────────────────────────────────────────────────────────

PROMPT_TEMPLATE = """
다음은 교육 플랫폼 슬랙 채널에 올라온 교수님의 과제 공지 메시지야.
아래 JSON 형식으로만 응답해. 다른 텍스트는 절대 포함하지 마.

{{
  "title": "과제 제목 (간결하게 한 문장)",
  "content": "공지 전체 내용 원문",
  "deadline": 마감일이 텍스트에 없으면, null,
  "topic": "과제 주제/분야 (예: 머신러닝, 데이터분석 등)",
  "requirements": ["요구사항1", "요구사항2", "..."]
}}

공지 메시지:
{text}
"""

async def parse_announcement(text: str) -> dict:
    model = _get_model()
    prompt = PROMPT_TEMPLATE.format(text=text)

    response = model.generate_content(prompt)
    raw = response.text.strip()

    # 마크다운 코드블록 제거
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]

    return json.loads(raw.strip())
