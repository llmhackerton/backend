from fastapi import FastAPI, Request, Depends, Body
from fastapi.responses import RedirectResponse, JSONResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from authlib.integrations.starlette_client import OAuth
from dotenv import load_dotenv
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.user_model import User
from app.schemas.user_schemas import UserUpdateSchema
from app.schemas.story_schemas import (
    StoryCreate,
    StoryLoad,
    StoryImageOut,
    StoryMakeResponse,
    StoryData,       # StoryData에 moral: bool = True 필드가 있어야 함 (아래 노트 참고)
)
from app.services.story_service import create_story, create_images_for_story

import os
import httpx
import requests
import io
import uuid
from fastapi.staticfiles import StaticFiles


load_dotenv()

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key=os.environ["SECRET_KEY"])

templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

oauth = OAuth()
oauth.register(
    name="naver",
    client_id=os.environ["NAVER_CLIENT_ID"],
    client_secret=os.environ["NAVER_CLIENT_SECRET"],
    access_token_url="https://nid.naver.com/oauth2.0/token",
    authorize_url="https://nid.naver.com/oauth2.0/authorize",
    api_base_url="https://openapi.naver.com",
    client_kwargs={"scope": "openid profile email"},
)

BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")

from fastapi.middleware.cors import CORSMiddleware

origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_current_user(request: Request):
    return request.session.get("user")

# ---------- CLOVA (Text LLM) ----------
CLOVA_API_KEY    = os.getenv("CLOVA_API_KEY")
CLOVA_REQUEST_ID = os.getenv("CLOVA_REQUEST_ID")
CLOVA_MODEL      = os.getenv("CLOVA_MODEL", "HCX-005")
CLOVA_ENDPOINT   = f"https://clovastudio.stream.ntruss.com/testapp/v3/chat-completions/{CLOVA_MODEL}"

# ---------- NAVER TTS ----------
TTS_API_URL       = "https://naveropenapi.apigw.ntruss.com/tts-premium/v1/tts"
TTS_CLIENT_ID     = os.getenv("NAVER_CLIENT_ID")
TTS_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET")


@app.get("/")
async def home(request: Request, user: dict | None = Depends(get_current_user)):
    if not user:
        return templates.TemplateResponse("login.html", {"request": request})
    return templates.TemplateResponse("index.html", {"request": request, "user": user})


@app.get("/login/naver")
async def login_naver(request: Request):
    redirect_uri = f"{BASE_URL}/auth/naver/callback"
    return await oauth.naver.authorize_redirect(request, redirect_uri)


@app.get("/auth/naver/callback")
async def auth_naver_callback(request: Request, db: Session = Depends(get_db)):
    token = await oauth.naver.authorize_access_token(request)

    async with httpx.AsyncClient() as client:
        r = await client.get(
            "https://openapi.naver.com/v1/nid/me",
            headers={"Authorization": f'Bearer {token["access_token"]}'},
            timeout=10.0,
        )
    data = r.json()
    resp = (data or {}).get("response", {})

    user = db.query(User).filter(User.naver_id == resp.get("id")).first()
    if not user:
        user = User(naver_id=resp.get("id"), name=resp.get("name"))
        db.add(user)
        db.commit()
        db.refresh(user)

    request.session["user"] = {
        "id": user.id,
        "naver_id": resp.get("id"),
        "name": resp.get("name") or resp.get("nickname"),
        "raw": resp,
    }
    return RedirectResponse("/")


@app.get("/logout")
async def logout(request: Request):
    request.session.pop("user", None)
    return RedirectResponse("/")


@app.get("/profile")
async def profile(request: Request, user: dict | None = Depends(get_current_user)):
    if not user:
        return RedirectResponse("/login/naver", status_code=303)
    return templates.TemplateResponse("profile.html", {"request": request, "user": user})


@app.post("/profile/update")
def profile_update(
    request: Request,
    schema: UserUpdateSchema,
    db: Session = Depends(get_db),
):
    current = get_current_user(request)
    if not current:
        return RedirectResponse("/login/naver", status_code=303)

    update_data = schema.dict(exclude_unset=True)
    if update_data:
        db.query(User).filter(User.id == current["id"]).update(update_data)
        db.commit()
        # 세션 표시 이름 갱신
        if "name" in update_data:
            current["name"] = update_data["name"]
            request.session["user"] = current

    return RedirectResponse("/profile", status_code=303)


@app.get("/story")
def make_story(request: Request, user: dict | None = Depends(get_current_user)):
    if not user:
        return RedirectResponse("/login/naver", status_code=303)
    return templates.TemplateResponse("story.html", {"request": request, "user": user})


@app.post("/story/make", response_model=StoryMakeResponse)
async def create_story_process(
    request: Request,
    payload: StoryCreate = Body(...),
    db: Session = Depends(get_db),
):
    user = get_current_user(request)
    if not user:
        return JSONResponse({"detail": "login required"}, status_code=401)

    row = create_story(db, payload, user["id"])

    story_load = StoryLoad(id=row.id, title=payload.title, paragraphs=payload.paragraphs)
    results = create_images_for_story(db, story_load)
    images_out = [StoryImageOut(idx=r.idx, file_path=r.file_path, prompt=r.prompt) for r in (results or [])]

    return StoryMakeResponse(story_id=row.id, title=payload.title, images=images_out)



CLOVA_HOST  = os.getenv("CLOVA_HOST", "https://clovastudio.apigw.ntruss.com")
CLOVA_MODEL = os.getenv("CLOVA_MODEL", "HCX-003")  # 사용 중인 모델명으로 교체 가능
CLOVA_KEY   = os.getenv("CLOVA_API_KEY")           # 'nv-'로 시작 권장

@app.post("/clova/make", response_model=StoryCreate)
def clova_make(payload: StoryData = Body(...)):
    title = (payload.title or "").strip() or "아이를 위한 짧은 동화"
    hero  = (payload.hero  or "").strip() or "아이"
    _age = None
    if payload.age is not None:
        try:
            _age = int(str(payload.age).strip())
        except ValueError:
            _age = None
    age = str(_age or "")
    theme = (payload.theme or "").strip()
    extra = (payload.extra or "").strip()

    # CLOVA X 프롬프트
    system = (
        "너는 유아용 동화 작가야. 3~5개의 장면으로 나누고, 각 장면은 2~3문장으로 간결하게 써줘. "
        "title과 paragraphs[{title,text}] 형태의 JSON만 반환해."
    )
    user_prompt = f"""동화 제목: {title}
주인공: {hero} (나이: {age or '미상'})
주제/분위기: {theme or '따뜻하고 용기있는 모험'}
추가지시: {extra or '각 장면은 2~3문장, 유아어휘'}"""

    # CLOVA X 요청 본문 (컨벤션에 맞게 조정)
    body = {
        "messages": [
            {"role":"system", "content": system},
            {"role":"user", "content": user_prompt},
        ],
        "maxTokens": 600,
        "temperature": 0.6,
        "topP": 0.8,
    }

    headers = {
        "X-NCP-CLOVASTUDIO-API-KEY": CLOVA_KEY or "",
        "X-NCP-CLOVASTUDIO-REQUEST-ID": str(uuid.uuid4()),
        "Content-Type": "application/json; charset=utf-8",
        "Accept": "application/json",
    }

    try:
        if not CLOVA_KEY:
            raise RuntimeError("CLOVA_API_KEY not set")

        # 엔드포인트는 실제 콘솔 문서에 맞춰 조정하세요.
        url = f"{CLOVA_HOST}/v3/chat-completions/{CLOVA_MODEL}"
        res = requests.post(url, headers=headers, json=body, timeout=30)
        res.raise_for_status()
        data = res.json()

        # 모델 응답에서 JSON만 추출 (콘솔 응답 구조에 맞게 파싱부 조정 가능)
        text = data.get("result", {}).get("message", "") or data.get("output","")
        # 혹시 모델이 가끔 코드블록으로 줄 때 대비
        import re, json as _json
        m = re.search(r"\{.*\}", text, flags=re.S)
        if m:
            obj = _json.loads(m.group(0))
            title = obj.get("title") or title
            paragraphs = obj.get("paragraphs") or []
        else:
            # 파싱 실패 시 간단히 분해
            paragraphs = [{"title": "장면 1", "text": text.strip()}]

    except Exception:
        # 실패 fallback : 간단한 3문단
        paragraphs = [
            {"title": "시작",   "text": f"{hero}는 {theme or '따뜻한 모험'}을(를) 시작했어요."},
            {"title": "도전",   "text": f"새로운 친구들과 함께 어려움을 이겨냈어요."},
            {"title": "마무리", "text": f"모두가 웃으며 집으로 돌아왔답니다."},
        ]

    return StoryCreate(title=title, paragraphs=paragraphs)


@app.post("/tts")
async def tts(req: Request):
    body    = await req.json()
    text    = (body.get("text") or "").strip()
    speaker = body.get("speaker", "nara")   # UI 기본값과 맞춤
    speed   = str(body.get("speed", "0"))   # -5 ~ 5

    if not text:
        return JSONResponse({"error": "text is empty"}, status_code=400)
    if len(text) > 3000:
        text = text[:3000]

    headers = {
        "X-NCP-APIGW-API-KEY-ID": TTS_CLIENT_ID,
        "X-NCP-APIGW-API-KEY":    TTS_CLIENT_SECRET,
    }
    data = {
        "speaker": speaker,
        "speed":   speed,
        "text":    text,
        # "format": "mp3",
    }

    try:
        r = requests.post(TTS_API_URL, headers=headers, data=data, timeout=30)
        r.raise_for_status()
        return StreamingResponse(io.BytesIO(r.content), media_type="audio/mpeg")
    except Exception as e:
        err_text = getattr(r, "text", "")
        return JSONResponse({"error": f"TTS 호출 실패: {e}", "raw": err_text}, status_code=500)


@app.get("/make/storybook")
async def tts_ui(request: Request, user: dict | None = Depends(get_current_user)):
    return templates.TemplateResponse("storybook.html", {"request": request, "user": user})
