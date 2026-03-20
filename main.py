import os
import json
import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

load_dotenv()

app = FastAPI(title="Proceedings API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_WHISPER_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"


# ─────────────────────────────────────────
# 음성 → 텍스트 변환 (청크 단위)
# ─────────────────────────────────────────
@app.post("/transcribe")
async def transcribe(file: UploadFile = File(...)):
    if not GROQ_API_KEY:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY가 설정되지 않았습니다.")

    file_bytes = await file.read()
    if len(file_bytes) > 25 * 1024 * 1024:
        raise HTTPException(status_code=422, detail="파일이 너무 큽니다. 25MB 이하만 지원합니다.")

    ext = (file.filename or "audio.webm").rsplit(".", 1)[-1].lower()
    mime_map = {"mp3": "audio/mpeg", "m4a": "audio/mp4", "wav": "audio/wav", "webm": "audio/webm", "ogg": "audio/ogg"}
    mime = mime_map.get(ext, "audio/webm")

    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(
            GROQ_WHISPER_URL,
            headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
            files={"file": (file.filename, file_bytes, mime)},
            data={"model": "whisper-large-v3-turbo", "response_format": "text"},
        )
    if response.status_code != 200:
        raise HTTPException(status_code=500, detail=f"음성인식 실패: {response.text}")

    return {"transcript": response.text.strip()}


# ─────────────────────────────────────────
# 텍스트 → 회의록 생성
# ─────────────────────────────────────────
class MinutesRequest(BaseModel):
    transcript: str


@app.post("/generate-minutes")
async def generate_minutes(req: MinutesRequest):
    if not GROQ_API_KEY:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY가 설정되지 않았습니다.")

    prompt = f"""다음은 회의 음성을 텍스트로 변환한 내용입니다.

{req.transcript}

위 내용을 바탕으로 아래 형식의 회의록을 작성해주세요. 반드시 JSON 형식으로만 응답하고 다른 텍스트는 포함하지 마세요.

{{"title":"회의 제목","date":"일시 (언급된 경우, 없으면 미기재)","attendees":["참석자1"],"agenda":["안건1"],"discussions":[{{"topic":"주제","content":"논의 내용"}}],"decisions":["결정사항1"],"action_items":[{{"task":"할일","owner":"담당자","due":"기한"}}],"next_meeting":"다음 회의 일정 (없으면 미정)"}}"""

    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            GROQ_CHAT_URL,
            headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
            json={"model": "llama-3.3-70b-versatile", "messages": [{"role": "user", "content": prompt}], "max_tokens": 2048},
        )
    if response.status_code != 200:
        raise HTTPException(status_code=500, detail=f"회의록 생성 실패: {response.text}")

    content = response.json()["choices"][0]["message"]["content"].strip()
    content = content.replace("```json", "").replace("```", "").strip()

    try:
        minutes = json.loads(content)
    except Exception:
        raise HTTPException(status_code=500, detail="회의록 파싱 실패. 다시 시도해주세요.")

    return {"minutes": minutes}


@app.get("/health")
async def health():
    return {"status": "ok"}