import os
import json
import httpx
import traceback
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
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
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
USER_PASSWORD = os.environ.get("USER_PASSWORD", "")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")


def supabase_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


@app.get("/config")
async def get_config():
    return {
        "google_client_id": GOOGLE_CLIENT_ID,
        "supabase_anon_key": SUPABASE_KEY
    }


class LoginRequest(BaseModel):
    password: str


@app.post("/login")
async def login(req: LoginRequest):
    if req.password == ADMIN_PASSWORD:
        return {"role": "admin"}
    elif req.password == USER_PASSWORD:
        return {"role": "user"}
    else:
        raise HTTPException(status_code=401, detail="비밀번호가 올바르지 않습니다.")


# ─── 음성 → 텍스트 ───
@app.post("/transcribe")
async def transcribe(file: UploadFile = File(...)):
    if not GROQ_API_KEY:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY가 설정되지 않았습니다.")
    file_bytes = await file.read()
    if len(file_bytes) > 25 * 1024 * 1024:
        raise HTTPException(status_code=422, detail="파일이 너무 큽니다. 25MB 이하만 지원합니다.")
    ext = (file.filename or "audio.mp4").rsplit(".", 1)[-1].lower()
    mime_map = {"mp3":"audio/mpeg","m4a":"audio/mp4","wav":"audio/wav","webm":"audio/webm","ogg":"audio/ogg","mp4":"audio/mp4"}
    mime = mime_map.get(ext, "audio/mp4")
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                GROQ_WHISPER_URL,
                headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
                files={"file": (file.filename, file_bytes, mime)},
                data={"model": "whisper-large-v3-turbo", "response_format": "text"},
            )
        if response.status_code != 200:
            print(f"Whisper 오류: {response.status_code} {response.text}")
            raise HTTPException(status_code=500, detail=f"음성인식 실패: {response.text}")
        return {"transcript": response.text.strip()}
    except HTTPException:
        raise
    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


# ─── 회의록 생성 ───
class MinutesRequest(BaseModel):
    transcript: str

@app.post("/generate-minutes")
async def generate_minutes(req: MinutesRequest):
    if not GROQ_API_KEY:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY가 설정되지 않았습니다.")
    prompt = f"""다음은 회의 음성을 텍스트로 변환한 내용입니다.\n\n{req.transcript}\n\n위 내용을 바탕으로 아래 형식의 회의록을 작성해주세요. 반드시 JSON 형식으로만 응답하고 다른 텍스트는 포함하지 마세요.\n\n{{"title":"회의 제목","date":"일시 (언급된 경우, 없으면 미기재)","attendees":["참석자1"],"agenda":["안건1"],"discussions":[{{"topic":"주제","content":"논의 내용"}}],"decisions":["결정사항1"],"action_items":[{{"task":"할일","owner":"담당자","due":"기한"}}],"next_meeting":"다음 회의 일정 (없으면 미정)"}}"""
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                GROQ_CHAT_URL,
                headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
                json={"model": "llama-3.3-70b-versatile", "messages": [{"role": "user", "content": prompt}], "max_tokens": 2048},
            )
        print(f"Groq 응답: {response.status_code} {response.text[:200]}")
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail=f"회의록 생성 실패: {response.text}")
        content = response.json()["choices"][0]["message"]["content"].strip()
        content = content.replace("```json", "").replace("```", "").strip()
        try:
            minutes = json.loads(content)
        except Exception:
            raise HTTPException(status_code=500, detail="회의록 파싱 실패. 다시 시도해주세요.")
        return {"minutes": minutes}
    except HTTPException:
        raise
    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


# ─── 프로젝트 CRUD ───
class ProjectCreate(BaseModel):
    name: str

class ProjectUpdate(BaseModel):
    name: str

@app.get("/projects")
async def get_projects():
    async with httpx.AsyncClient() as client:
        res = await client.get(
            f"{SUPABASE_URL}/rest/v1/projects?order=created_at.desc",
            headers=supabase_headers()
        )
    if res.status_code != 200:
        raise HTTPException(status_code=500, detail=res.text)
    return res.json()

@app.post("/projects")
async def create_project(req: ProjectCreate):
    async with httpx.AsyncClient() as client:
        res = await client.post(
            f"{SUPABASE_URL}/rest/v1/projects",
            headers=supabase_headers(),
            json={"name": req.name}
        )
    if res.status_code not in (200, 201):
        raise HTTPException(status_code=500, detail=res.text)
    return res.json()[0]

@app.patch("/projects/{project_id}")
async def update_project(project_id: str, req: ProjectUpdate):
    async with httpx.AsyncClient() as client:
        res = await client.patch(
            f"{SUPABASE_URL}/rest/v1/projects?id=eq.{project_id}",
            headers=supabase_headers(),
            json={"name": req.name}
        )
    if res.status_code not in (200, 204):
        raise HTTPException(status_code=500, detail=res.text)
    return {"success": True}

@app.delete("/projects/{project_id}")
async def delete_project(project_id: str):
    async with httpx.AsyncClient() as client:
        res = await client.delete(
            f"{SUPABASE_URL}/rest/v1/projects?id=eq.{project_id}",
            headers=supabase_headers()
        )
    if res.status_code not in (200, 204):
        raise HTTPException(status_code=500, detail=res.text)
    return {"success": True}


# ─── 회의록 CRUD ───
@app.get("/projects/{project_id}/meetings")
async def get_meetings(project_id: str):
    async with httpx.AsyncClient() as client:
        res = await client.get(
            f"{SUPABASE_URL}/rest/v1/meetings?project_id=eq.{project_id}&order=created_at.desc",
            headers=supabase_headers()
        )
    if res.status_code != 200:
        raise HTTPException(status_code=500, detail=res.text)
    return res.json()

class MeetingSave(BaseModel):
    project_id: str
    title: str
    date: str
    attendees: str
    minutes_json: str
    transcript: str
    recording_url: str = ""

@app.post("/meetings")
async def save_meeting(req: MeetingSave):
    async with httpx.AsyncClient() as client:
        res = await client.post(
            f"{SUPABASE_URL}/rest/v1/meetings",
            headers=supabase_headers(),
            json=req.model_dump()
        )
    if res.status_code not in (200, 201):
        raise HTTPException(status_code=500, detail=res.text)
    return res.json()[0]


@app.post("/upload-recording")
async def upload_recording(file: UploadFile = File(...)):
    file_bytes = await file.read()
    filename = file.filename or "recording.webm"

    async with httpx.AsyncClient(timeout=60) as client:
        res = await client.post(
            f"{SUPABASE_URL}/storage/v1/object/recordings/{filename}",
            headers={
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type": file.content_type or "audio/webm",
            },
            content=file_bytes
        )
    if res.status_code not in (200, 201):
        raise HTTPException(status_code=500, detail=f"업로드 실패: {res.text}")

    recording_url = f"{SUPABASE_URL}/storage/v1/object/recordings/{filename}"
    return {"url": recording_url}


class MeetingUpdate(BaseModel):
    title: str


@app.patch("/meetings/{meeting_id}")
async def update_meeting(meeting_id: str, req: MeetingUpdate):
    async with httpx.AsyncClient() as client:
        res = await client.patch(
            f"{SUPABASE_URL}/rest/v1/meetings?id=eq.{meeting_id}",
            headers=supabase_headers(),
            json={"title": req.title}
        )
    if res.status_code not in (200, 204):
        raise HTTPException(status_code=500, detail=res.text)
    return {"success": True}


@app.delete("/meetings/{meeting_id}")
async def delete_meeting(meeting_id: str):
    async with httpx.AsyncClient() as client:
        res = await client.delete(
            f"{SUPABASE_URL}/rest/v1/meetings?id=eq.{meeting_id}",
            headers=supabase_headers()
        )
    if res.status_code not in (200, 204):
        raise HTTPException(status_code=500, detail=res.text)
    return {"success": True}


@app.get("/health")
async def health():
    return {"status": "ok"}