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

GROQ_API_KEY      = os.environ.get("GROQ_API_KEY", "")
GROQ_WHISPER_URL  = "https://api.groq.com/openai/v1/audio/transcriptions"
GROQ_CHAT_URL     = "https://api.groq.com/openai/v1/chat/completions"
SUPABASE_URL      = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY      = os.environ.get("SUPABASE_KEY", "")
GOOGLE_CLIENT_ID  = os.environ.get("GOOGLE_CLIENT_ID", "")
USER_PASSWORD     = os.environ.get("USER_PASSWORD", "")
ADMIN_PASSWORD    = os.environ.get("ADMIN_PASSWORD", "")


def supabase_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def log(tag: str, status: int, body: str = ""):
    print(f"[{tag}] {status} | {body[:300]}")


# ─────────────────────────────────────────
# 설정 / 인증
# ─────────────────────────────────────────
@app.get("/config")
async def get_config():
    return {
        "google_client_id": GOOGLE_CLIENT_ID,
        "supabase_anon_key": SUPABASE_KEY,
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


# ─────────────────────────────────────────
# 음성 → 텍스트 (Whisper)
# ─────────────────────────────────────────
@app.post("/transcribe")
async def transcribe(file: UploadFile = File(...)):
    if not GROQ_API_KEY:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY가 설정되지 않았습니다.")

    file_bytes = await file.read()
    print(f"[transcribe] 파일 수신: {file.filename}, {len(file_bytes)} bytes")

    if len(file_bytes) > 25 * 1024 * 1024:
        raise HTTPException(status_code=422, detail="파일이 너무 큽니다. 25MB 이하만 지원합니다.")
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

GROQ_API_KEY      = os.environ.get("GROQ_API_KEY", "")
GROQ_WHISPER_URL  = "https://api.groq.com/openai/v1/audio/transcriptions"
GROQ_CHAT_URL     = "https://api.groq.com/openai/v1/chat/completions"
SUPABASE_URL      = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY      = os.environ.get("SUPABASE_KEY", "")
GOOGLE_CLIENT_ID  = os.environ.get("GOOGLE_CLIENT_ID", "")
USER_PASSWORD     = os.environ.get("USER_PASSWORD", "")
ADMIN_PASSWORD    = os.environ.get("ADMIN_PASSWORD", "")


def supabase_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def log(tag: str, status: int, body: str = ""):
    print(f"[{tag}] {status} | {body[:300]}")


# ─────────────────────────────────────────
# 설정 / 인증
# ─────────────────────────────────────────
@app.get("/config")
async def get_config():
    return {
        "google_client_id": GOOGLE_CLIENT_ID,
        "supabase_anon_key": SUPABASE_KEY,
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


# ─────────────────────────────────────────
# 음성 → 텍스트 (Whisper)
# ─────────────────────────────────────────
@app.post("/transcribe")
async def transcribe(file: UploadFile = File(...)):
    if not GROQ_API_KEY:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY가 설정되지 않았습니다.")

    file_bytes = await file.read()
    print(f"[transcribe] 파일 수신: {file.filename}, {len(file_bytes)} bytes")

    if len(file_bytes) > 25 * 1024 * 1024:
        raise HTTPException(status_code=422, detail="파일이 너무 큽니다. 25MB 이하만 지원합니다.")

    ext = (file.filename or "audio.mp4").rsplit(".", 1)[-1].lower()
    mime_map = {"mp3": "audio/mpeg", "m4a": "audio/mp4", "wav": "audio/wav",
                "webm": "audio/webm", "ogg": "audio/ogg", "mp4": "audio/mp4"}
    mime = mime_map.get(ext, "audio/mp4")

    try:
        import tempfile, subprocess, os as _os, uuid

        # 고유한 임시 파일명 생성
        tmp_id = str(uuid.uuid4())[:8]
        tmp_dir = tempfile.gettempdir()
        tmp_in_path = _os.path.join(tmp_dir, f"audio_in_{tmp_id}.webm")
        tmp_out_path = _os.path.join(tmp_dir, f"audio_out_{tmp_id}.mp3")

        with open(tmp_in_path, "wb") as f:
            f.write(file_bytes)

        result = subprocess.run(
            ["ffmpeg", "-i", tmp_in_path, "-ar", "16000", "-ac", "1", "-y", tmp_out_path],
            capture_output=True, timeout=120
        )
        print(f"[ffmpeg transcribe] returncode: {result.returncode}")

        if result.returncode == 0:
            with open(tmp_out_path, "rb") as f:
                send_bytes = f.read()
            send_filename = "audio.mp3"
            send_mime = "audio/mpeg"
            print(f"[ffmpeg transcribe] mp3 변환 완료: {len(send_bytes)} bytes")
        else:
            print(f"[ffmpeg transcribe] 변환 실패 stderr:\n{result.stderr.decode()}")
            send_bytes = file_bytes
            send_filename = file.filename
            send_mime = mime

        for p in [tmp_in_path, tmp_out_path]:
            try: _os.remove(p)
            except: pass

        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                GROQ_WHISPER_URL,
                headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
                files={"file": (send_filename, send_bytes, send_mime)},
                data={
                    "model": "whisper-large-v3-turbo",
                    "response_format": "text",
                    "prompt": "한국어와 영어가 혼용된 회의 내용입니다. 한국어는 한국어로, 영어는 영어로 정확하게 전사해주세요.",
                },
            )
        log("Whisper", response.status_code, response.text)
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail=f"음성인식 실패: {response.text}")
        return {"transcript": response.text.strip()}
    except HTTPException:
        raise
    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────
# 텍스트 → 회의록 생성 (LLM)
# ─────────────────────────────────────────
class MinutesRequest(BaseModel):
    transcript: str


@app.post("/generate-minutes")
async def generate_minutes(req: MinutesRequest):
    if not GROQ_API_KEY:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY가 설정되지 않았습니다.")

    print(f"[generate-minutes] transcript 길이: {len(req.transcript)}")
    prompt = f"""다음은 회의 음성을 텍스트로 변환한 내용입니다.

{req.transcript}

위 내용을 바탕으로 아래 형식의 회의록을 작성해주세요. 반드시 JSON 형식으로만 응답하고 다른 텍스트는 포함하지 마세요.

{{"title":"회의 제목","date":"일시 (언급된 경우, 없으면 미기재)","attendees":["참석자1"],"agenda":["안건1"],"discussions":[{{"topic":"주제","content":"논의 내용"}}],"decisions":["결정사항1"],"action_items":[{{"task":"할일","owner":"담당자","due":"기한"}}],"next_meeting":"다음 회의 일정 (없으면 미정)"}}"""

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                GROQ_CHAT_URL,
                headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
                json={
                    "model": "llama-3.3-70b-versatile",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 2048,
                },
            )
        log("Groq LLM", response.status_code, response.text)
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail=f"회의록 생성 실패: {response.text}")

        content = response.json()["choices"][0]["message"]["content"].strip()
        content = content.replace("```json", "").replace("```", "").strip()
        try:
            minutes = json.loads(content)
        except Exception:
            print(f"[generate-minutes] JSON 파싱 실패: {content[:300]}")
            raise HTTPException(status_code=500, detail="회의록 파싱 실패. 다시 시도해주세요.")
        return {"minutes": minutes}
    except HTTPException:
        raise
    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────
# 녹음 파일 업로드 / Signed URL
# ─────────────────────────────────────────
@app.post("/upload-recording")
async def upload_recording(file: UploadFile = File(...)):
    import tempfile, subprocess
    file_bytes = await file.read()
    filename = file.filename or "recording.webm"
    print(f"[upload-recording] 파일: {filename}, {len(file_bytes)} bytes")

    try:
        # ffmpeg으로 duration 메타데이터 추가 (seek 가능하게)
        with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tmp_in:
            tmp_in.write(file_bytes)
            tmp_in_path = tmp_in.name

        tmp_out_path = tmp_in_path.replace(".webm", "_fixed.webm")

        result = subprocess.run(
            ["ffmpeg", "-i", tmp_in_path, "-c", "copy", "-y", tmp_out_path],
            capture_output=True, timeout=60
        )
        print(f"[ffmpeg] returncode: {result.returncode}")

        if result.returncode == 0:
            with open(tmp_out_path, "rb") as f:
                file_bytes = f.read()
            print(f"[ffmpeg] 변환 완료: {len(file_bytes)} bytes")
        else:
            print(f"[ffmpeg] 실패, 원본 사용: {result.stderr.decode()[:200]}")

        # 임시 파일 정리
        import os as _os
        for p in [tmp_in_path, tmp_out_path]:
            try: _os.remove(p)
            except: pass

        async with httpx.AsyncClient(timeout=120) as client:
            res = await client.post(
                f"{SUPABASE_URL}/storage/v1/object/recordings/{filename}",
                headers={
                    "apikey": SUPABASE_KEY,
                    "Authorization": f"Bearer {SUPABASE_KEY}",
                    "Content-Type": "audio/webm",
                },
                content=file_bytes,
            )
        log("Supabase Storage Upload", res.status_code, res.text)
        if res.status_code not in (200, 201):
            raise HTTPException(status_code=500, detail=f"업로드 실패: {res.text}")
        recording_url = f"{SUPABASE_URL}/storage/v1/object/recordings/{filename}"
        return {"url": recording_url}
    except HTTPException:
        raise
    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/recording-url")
async def get_recording_url(path: str):
    print(f"[recording-url] path: {path}")
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            res = await client.post(
                f"{SUPABASE_URL}/storage/v1/object/sign/recordings/{path}",
                headers={
                    "apikey": SUPABASE_KEY,
                    "Authorization": f"Bearer {SUPABASE_KEY}",
                    "Content-Type": "application/json",
                },
                json={"expiresIn": 3600},
            )
        log("Supabase Signed URL", res.status_code, res.text)
        if res.status_code != 200:
            raise HTTPException(status_code=500, detail=res.text)
        signed_url = res.json().get("signedURL", "")
        return {"url": f"{SUPABASE_URL}/storage/v1{signed_url}"}
    except HTTPException:
        raise
    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/download-recording")
async def download_recording(path: str):
    """녹음 파일을 다운로드로 강제 제공"""
    print(f"[download-recording] path: {path}")
    try:
        # Signed URL 발급
        async with httpx.AsyncClient(timeout=30) as client:
            sign_res = await client.post(
                f"{SUPABASE_URL}/storage/v1/object/sign/recordings/{path}",
                headers={
                    "apikey": SUPABASE_KEY,
                    "Authorization": f"Bearer {SUPABASE_KEY}",
                    "Content-Type": "application/json",
                },
                json={"expiresIn": 300},
            )
        if sign_res.status_code != 200:
            raise HTTPException(status_code=500, detail=sign_res.text)

        signed_url = f"{SUPABASE_URL}/storage/v1{sign_res.json().get('signedURL', '')}"

        # 파일 스트리밍 다운로드
        async with httpx.AsyncClient(timeout=120) as client:
            file_res = await client.get(signed_url)

        if file_res.status_code != 200:
            raise HTTPException(status_code=500, detail="파일 다운로드 실패")

        from fastapi.responses import Response
        return Response(
            content=file_res.content,
            media_type="audio/webm",
            headers={"Content-Disposition": f'attachment; filename="{path}"'}
        )
    except HTTPException:
        raise
    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))
async def get_recording_url(path: str):
    print(f"[recording-url] path: {path}")
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            res = await client.post(
                f"{SUPABASE_URL}/storage/v1/object/sign/recordings/{path}",
                headers={
                    "apikey": SUPABASE_KEY,
                    "Authorization": f"Bearer {SUPABASE_KEY}",
                    "Content-Type": "application/json",
                },
                json={"expiresIn": 3600},
            )
        log("Supabase Signed URL", res.status_code, res.text)
        if res.status_code != 200:
            raise HTTPException(status_code=500, detail=res.text)
        signed_url = res.json().get("signedURL", "")
        return {"url": f"{SUPABASE_URL}/storage/v1{signed_url}"}
    except HTTPException:
        raise
    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────
# 프로젝트 CRUD
# ─────────────────────────────────────────
class ProjectCreate(BaseModel):
    name: str


class ProjectUpdate(BaseModel):
    name: str


@app.get("/projects")
async def get_projects():
    async with httpx.AsyncClient() as client:
        res = await client.get(
            f"{SUPABASE_URL}/rest/v1/projects?order=created_at.desc",
            headers=supabase_headers(),
        )
    log("Supabase GET /projects", res.status_code, res.text)
    if res.status_code != 200:
        raise HTTPException(status_code=500, detail=res.text)
    return res.json()


@app.post("/projects")
async def create_project(req: ProjectCreate):
    async with httpx.AsyncClient() as client:
        res = await client.post(
            f"{SUPABASE_URL}/rest/v1/projects",
            headers=supabase_headers(),
            json={"name": req.name},
        )
    log("Supabase POST /projects", res.status_code, res.text)
    if res.status_code not in (200, 201):
        raise HTTPException(status_code=500, detail=res.text)
    return res.json()[0]


@app.patch("/projects/{project_id}")
async def update_project(project_id: str, req: ProjectUpdate):
    async with httpx.AsyncClient() as client:
        res = await client.patch(
            f"{SUPABASE_URL}/rest/v1/projects?id=eq.{project_id}",
            headers=supabase_headers(),
            json={"name": req.name},
        )
    log("Supabase PATCH /projects", res.status_code, res.text)
    if res.status_code not in (200, 204):
        raise HTTPException(status_code=500, detail=res.text)
    return {"success": True}


@app.delete("/projects/{project_id}")
async def delete_project(project_id: str):
    async with httpx.AsyncClient() as client:
        res = await client.delete(
            f"{SUPABASE_URL}/rest/v1/projects?id=eq.{project_id}",
            headers=supabase_headers(),
        )
    log("Supabase DELETE /projects", res.status_code, res.text)
    if res.status_code not in (200, 204):
        raise HTTPException(status_code=500, detail=res.text)
    return {"success": True}


# ─────────────────────────────────────────
# 회의록 CRUD
# ─────────────────────────────────────────
@app.get("/projects/{project_id}/meetings")
async def get_meetings(project_id: str):
    async with httpx.AsyncClient() as client:
        res = await client.get(
            f"{SUPABASE_URL}/rest/v1/meetings?project_id=eq.{project_id}&order=created_at.desc",
            headers=supabase_headers(),
        )
    log("Supabase GET /meetings", res.status_code, res.text)
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
            json=req.model_dump(),
        )
    log("Supabase POST /meetings", res.status_code, res.text)
    if res.status_code not in (200, 201):
        raise HTTPException(status_code=500, detail=res.text)
    return res.json()[0]


class MeetingUpdate(BaseModel):
    title: str


@app.patch("/meetings/{meeting_id}")
async def update_meeting(meeting_id: str, req: MeetingUpdate):
    async with httpx.AsyncClient() as client:
        res = await client.patch(
            f"{SUPABASE_URL}/rest/v1/meetings?id=eq.{meeting_id}",
            headers=supabase_headers(),
            json={"title": req.title},
        )
    log("Supabase PATCH /meetings", res.status_code, res.text)
    if res.status_code not in (200, 204):
        raise HTTPException(status_code=500, detail=res.text)
    return {"success": True}


@app.delete("/meetings/{meeting_id}")
async def delete_meeting(meeting_id: str):
    async with httpx.AsyncClient() as client:
        # 먼저 회의록 조회해서 recording_url 확인
        get_res = await client.get(
            f"{SUPABASE_URL}/rest/v1/meetings?id=eq.{meeting_id}&select=recording_url",
            headers=supabase_headers(),
        )
        log("Supabase GET /meetings (before delete)", get_res.status_code, get_res.text)

        # recording_url 있으면 Storage에서도 삭제
        if get_res.status_code == 200:
            rows = get_res.json()
            if rows and rows[0].get("recording_url"):
                filename = rows[0]["recording_url"].split("/recordings/")[-1].split("?")[0]
                del_res = await client.delete(
                    f"{SUPABASE_URL}/storage/v1/object/recordings/{filename}",
                    headers={
                        "apikey": SUPABASE_KEY,
                        "Authorization": f"Bearer {SUPABASE_KEY}",
                    },
                )
                log("Supabase Storage DELETE", del_res.status_code, del_res.text)

        # 회의록 DB 삭제
        res = await client.delete(
            f"{SUPABASE_URL}/rest/v1/meetings?id=eq.{meeting_id}",
            headers=supabase_headers(),
        )
    log("Supabase DELETE /meetings", res.status_code, res.text)
    if res.status_code not in (200, 204):
        raise HTTPException(status_code=500, detail=res.text)
    return {"success": True}


@app.get("/health")
async def health():
    return {"status": "ok"}
    ext = (file.filename or "audio.mp4").rsplit(".", 1)[-1].lower()
    mime_map = {"mp3": "audio/mpeg", "m4a": "audio/mp4", "wav": "audio/wav",
                "webm": "audio/webm", "ogg": "audio/ogg", "mp4": "audio/mp4"}
    mime = mime_map.get(ext, "audio/mp4")

    try:
        import tempfile, subprocess, os as _os

        # webm → mp3 변환 (Whisper 호환성 향상)
        with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False) as tmp_in:
            tmp_in.write(file_bytes)
            tmp_in_path = tmp_in.name

        tmp_out_path = tmp_in_path.replace(f".{ext}", ".mp3")
        result = subprocess.run(
            ["ffmpeg", "-i", tmp_in_path, "-ar", "16000", "-ac", "1", "-y", tmp_out_path],
            capture_output=True, timeout=120
        )
        print(f"[ffmpeg transcribe] returncode: {result.returncode}")

        if result.returncode == 0:
            with open(tmp_out_path, "rb") as f:
                send_bytes = f.read()
            send_filename = "audio.mp3"
            send_mime = "audio/mpeg"
            print(f"[ffmpeg transcribe] mp3 변환 완료: {len(send_bytes)} bytes")
        else:
            print(f"[ffmpeg transcribe] 변환 실패, 원본 사용: {result.stderr.decode()[:200]}")
            send_bytes = file_bytes
            send_filename = file.filename
            send_mime = mime

        for p in [tmp_in_path, tmp_out_path]:
            try: _os.remove(p)
            except: pass

        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                GROQ_WHISPER_URL,
                headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
                files={"file": (send_filename, send_bytes, send_mime)},
                data={
                    "model": "whisper-large-v3-turbo",
                    "response_format": "text",
                    "prompt": "한국어와 영어가 혼용된 회의 내용입니다. 한국어는 한국어로, 영어는 영어로 정확하게 전사해주세요.",
                },
            )
        log("Whisper", response.status_code, response.text)
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail=f"음성인식 실패: {response.text}")
        return {"transcript": response.text.strip()}
    except HTTPException:
        raise
    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────
# 텍스트 → 회의록 생성 (LLM)
# ─────────────────────────────────────────
class MinutesRequest(BaseModel):
    transcript: str


@app.post("/generate-minutes")
async def generate_minutes(req: MinutesRequest):
    if not GROQ_API_KEY:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY가 설정되지 않았습니다.")

    print(f"[generate-minutes] transcript 길이: {len(req.transcript)}")
    prompt = f"""다음은 회의 음성을 텍스트로 변환한 내용입니다.

{req.transcript}

위 내용을 바탕으로 아래 형식의 회의록을 작성해주세요. 반드시 JSON 형식으로만 응답하고 다른 텍스트는 포함하지 마세요.

{{"title":"회의 제목","date":"일시 (언급된 경우, 없으면 미기재)","attendees":["참석자1"],"agenda":["안건1"],"discussions":[{{"topic":"주제","content":"논의 내용"}}],"decisions":["결정사항1"],"action_items":[{{"task":"할일","owner":"담당자","due":"기한"}}],"next_meeting":"다음 회의 일정 (없으면 미정)"}}"""

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                GROQ_CHAT_URL,
                headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
                json={
                    "model": "llama-3.3-70b-versatile",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 2048,
                },
            )
        log("Groq LLM", response.status_code, response.text)
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail=f"회의록 생성 실패: {response.text}")

        content = response.json()["choices"][0]["message"]["content"].strip()
        content = content.replace("```json", "").replace("```", "").strip()
        try:
            minutes = json.loads(content)
        except Exception:
            print(f"[generate-minutes] JSON 파싱 실패: {content[:300]}")
            raise HTTPException(status_code=500, detail="회의록 파싱 실패. 다시 시도해주세요.")
        return {"minutes": minutes}
    except HTTPException:
        raise
    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────
# 녹음 파일 업로드 / Signed URL
# ─────────────────────────────────────────
@app.post("/upload-recording")
async def upload_recording(file: UploadFile = File(...)):
    import tempfile, subprocess
    file_bytes = await file.read()
    filename = file.filename or "recording.webm"
    print(f"[upload-recording] 파일: {filename}, {len(file_bytes)} bytes")

    try:
        # ffmpeg으로 duration 메타데이터 추가 (seek 가능하게)
        with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tmp_in:
            tmp_in.write(file_bytes)
            tmp_in_path = tmp_in.name

        tmp_out_path = tmp_in_path.replace(".webm", "_fixed.webm")

        result = subprocess.run(
            ["ffmpeg", "-i", tmp_in_path, "-c", "copy", "-y", tmp_out_path],
            capture_output=True, timeout=60
        )
        print(f"[ffmpeg] returncode: {result.returncode}")

        if result.returncode == 0:
            with open(tmp_out_path, "rb") as f:
                file_bytes = f.read()
            print(f"[ffmpeg] 변환 완료: {len(file_bytes)} bytes")
        else:
            print(f"[ffmpeg] 실패, 원본 사용: {result.stderr.decode()[:200]}")

        # 임시 파일 정리
        import os as _os
        for p in [tmp_in_path, tmp_out_path]:
            try: _os.remove(p)
            except: pass

        async with httpx.AsyncClient(timeout=120) as client:
            res = await client.post(
                f"{SUPABASE_URL}/storage/v1/object/recordings/{filename}",
                headers={
                    "apikey": SUPABASE_KEY,
                    "Authorization": f"Bearer {SUPABASE_KEY}",
                    "Content-Type": "audio/webm",
                },
                content=file_bytes,
            )
        log("Supabase Storage Upload", res.status_code, res.text)
        if res.status_code not in (200, 201):
            raise HTTPException(status_code=500, detail=f"업로드 실패: {res.text}")
        recording_url = f"{SUPABASE_URL}/storage/v1/object/recordings/{filename}"
        return {"url": recording_url}
    except HTTPException:
        raise
    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/recording-url")
async def get_recording_url(path: str):
    print(f"[recording-url] path: {path}")
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            res = await client.post(
                f"{SUPABASE_URL}/storage/v1/object/sign/recordings/{path}",
                headers={
                    "apikey": SUPABASE_KEY,
                    "Authorization": f"Bearer {SUPABASE_KEY}",
                    "Content-Type": "application/json",
                },
                json={"expiresIn": 3600},
            )
        log("Supabase Signed URL", res.status_code, res.text)
        if res.status_code != 200:
            raise HTTPException(status_code=500, detail=res.text)
        signed_url = res.json().get("signedURL", "")
        return {"url": f"{SUPABASE_URL}/storage/v1{signed_url}"}
    except HTTPException:
        raise
    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/download-recording")
async def download_recording(path: str):
    """녹음 파일을 다운로드로 강제 제공"""
    print(f"[download-recording] path: {path}")
    try:
        # Signed URL 발급
        async with httpx.AsyncClient(timeout=30) as client:
            sign_res = await client.post(
                f"{SUPABASE_URL}/storage/v1/object/sign/recordings/{path}",
                headers={
                    "apikey": SUPABASE_KEY,
                    "Authorization": f"Bearer {SUPABASE_KEY}",
                    "Content-Type": "application/json",
                },
                json={"expiresIn": 300},
            )
        if sign_res.status_code != 200:
            raise HTTPException(status_code=500, detail=sign_res.text)

        signed_url = f"{SUPABASE_URL}/storage/v1{sign_res.json().get('signedURL', '')}"

        # 파일 스트리밍 다운로드
        async with httpx.AsyncClient(timeout=120) as client:
            file_res = await client.get(signed_url)

        if file_res.status_code != 200:
            raise HTTPException(status_code=500, detail="파일 다운로드 실패")

        from fastapi.responses import Response
        return Response(
            content=file_res.content,
            media_type="audio/webm",
            headers={"Content-Disposition": f'attachment; filename="{path}"'}
        )
    except HTTPException:
        raise
    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))
async def get_recording_url(path: str):
    print(f"[recording-url] path: {path}")
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            res = await client.post(
                f"{SUPABASE_URL}/storage/v1/object/sign/recordings/{path}",
                headers={
                    "apikey": SUPABASE_KEY,
                    "Authorization": f"Bearer {SUPABASE_KEY}",
                    "Content-Type": "application/json",
                },
                json={"expiresIn": 3600},
            )
        log("Supabase Signed URL", res.status_code, res.text)
        if res.status_code != 200:
            raise HTTPException(status_code=500, detail=res.text)
        signed_url = res.json().get("signedURL", "")
        return {"url": f"{SUPABASE_URL}/storage/v1{signed_url}"}
    except HTTPException:
        raise
    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────
# 프로젝트 CRUD
# ─────────────────────────────────────────
class ProjectCreate(BaseModel):
    name: str


class ProjectUpdate(BaseModel):
    name: str


@app.get("/projects")
async def get_projects():
    async with httpx.AsyncClient() as client:
        res = await client.get(
            f"{SUPABASE_URL}/rest/v1/projects?order=created_at.desc",
            headers=supabase_headers(),
        )
    log("Supabase GET /projects", res.status_code, res.text)
    if res.status_code != 200:
        raise HTTPException(status_code=500, detail=res.text)
    return res.json()


@app.post("/projects")
async def create_project(req: ProjectCreate):
    async with httpx.AsyncClient() as client:
        res = await client.post(
            f"{SUPABASE_URL}/rest/v1/projects",
            headers=supabase_headers(),
            json={"name": req.name},
        )
    log("Supabase POST /projects", res.status_code, res.text)
    if res.status_code not in (200, 201):
        raise HTTPException(status_code=500, detail=res.text)
    return res.json()[0]


@app.patch("/projects/{project_id}")
async def update_project(project_id: str, req: ProjectUpdate):
    async with httpx.AsyncClient() as client:
        res = await client.patch(
            f"{SUPABASE_URL}/rest/v1/projects?id=eq.{project_id}",
            headers=supabase_headers(),
            json={"name": req.name},
        )
    log("Supabase PATCH /projects", res.status_code, res.text)
    if res.status_code not in (200, 204):
        raise HTTPException(status_code=500, detail=res.text)
    return {"success": True}


@app.delete("/projects/{project_id}")
async def delete_project(project_id: str):
    async with httpx.AsyncClient() as client:
        res = await client.delete(
            f"{SUPABASE_URL}/rest/v1/projects?id=eq.{project_id}",
            headers=supabase_headers(),
        )
    log("Supabase DELETE /projects", res.status_code, res.text)
    if res.status_code not in (200, 204):
        raise HTTPException(status_code=500, detail=res.text)
    return {"success": True}


# ─────────────────────────────────────────
# 회의록 CRUD
# ─────────────────────────────────────────
@app.get("/projects/{project_id}/meetings")
async def get_meetings(project_id: str):
    async with httpx.AsyncClient() as client:
        res = await client.get(
            f"{SUPABASE_URL}/rest/v1/meetings?project_id=eq.{project_id}&order=created_at.desc",
            headers=supabase_headers(),
        )
    log("Supabase GET /meetings", res.status_code, res.text)
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
            json=req.model_dump(),
        )
    log("Supabase POST /meetings", res.status_code, res.text)
    if res.status_code not in (200, 201):
        raise HTTPException(status_code=500, detail=res.text)
    return res.json()[0]


class MeetingUpdate(BaseModel):
    title: str


@app.patch("/meetings/{meeting_id}")
async def update_meeting(meeting_id: str, req: MeetingUpdate):
    async with httpx.AsyncClient() as client:
        res = await client.patch(
            f"{SUPABASE_URL}/rest/v1/meetings?id=eq.{meeting_id}",
            headers=supabase_headers(),
            json={"title": req.title},
        )
    log("Supabase PATCH /meetings", res.status_code, res.text)
    if res.status_code not in (200, 204):
        raise HTTPException(status_code=500, detail=res.text)
    return {"success": True}


@app.delete("/meetings/{meeting_id}")
async def delete_meeting(meeting_id: str):
    async with httpx.AsyncClient() as client:
        # 먼저 회의록 조회해서 recording_url 확인
        get_res = await client.get(
            f"{SUPABASE_URL}/rest/v1/meetings?id=eq.{meeting_id}&select=recording_url",
            headers=supabase_headers(),
        )
        log("Supabase GET /meetings (before delete)", get_res.status_code, get_res.text)

        # recording_url 있으면 Storage에서도 삭제
        if get_res.status_code == 200:
            rows = get_res.json()
            if rows and rows[0].get("recording_url"):
                filename = rows[0]["recording_url"].split("/recordings/")[-1].split("?")[0]
                del_res = await client.delete(
                    f"{SUPABASE_URL}/storage/v1/object/recordings/{filename}",
                    headers={
                        "apikey": SUPABASE_KEY,
                        "Authorization": f"Bearer {SUPABASE_KEY}",
                    },
                )
                log("Supabase Storage DELETE", del_res.status_code, del_res.text)

        # 회의록 DB 삭제
        res = await client.delete(
            f"{SUPABASE_URL}/rest/v1/meetings?id=eq.{meeting_id}",
            headers=supabase_headers(),
        )
    log("Supabase DELETE /meetings", res.status_code, res.text)
    if res.status_code not in (200, 204):
        raise HTTPException(status_code=500, detail=res.text)
    return {"success": True}


@app.get("/health")
async def health():
    return {"status": "ok"}