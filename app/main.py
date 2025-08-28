from fastapi import FastAPI, Request, Depends
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from authlib.integrations.starlette_client import OAuth
from dotenv import load_dotenv
import os, httpx
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.user_model import User

load_dotenv()

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key=os.environ["SECRET_KEY"])

templates = Jinja2Templates(directory="templates")

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

def get_current_user(request: Request):
    return request.session.get("user")

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

    if not db.query(User).filter(User.naver_id == resp.get("id")).first():
        new_user = User(  
                    naver_id = resp.get("id"),
                    name = resp.get("name"))
        db.add(new_user)
        db.commit()
        db.refresh(new_user)

    user = db.query(User).filter(User.naver_id == resp.get("id")).first()

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


