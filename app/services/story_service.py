# app/services/story_service.py
import os
import json
import time
from typing import List

from dotenv import load_dotenv, find_dotenv
from sqlalchemy.orm import Session
from google import genai
from google.genai import types
from google.genai import errors as genai_errors

from app.models.story_model import Story, StoryImage
from app.schemas.story_schemas import StoryCreate, StoryLoad, StoryImageOut

load_dotenv(find_dotenv(), override=False)
API_KEY = os.getenv("GEMINI_API_KEY")
IMAGEN_MODEL = "imagen-4.0-generate-001"


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _build_prompt(book_title: str, p_title: str, p_text: str) -> str:
    return (
        f"[동화책 삽화]\n"
        f"책 제목: {book_title}\n"
        f"장면 제목: {p_title}\n"
        f"장면 설명: {p_text}\n\n"
        f"스타일: 파스텔톤, 따뜻하고 부드러운 그림체, 어린이 친화적, 고해상도, 페이지 전체 삽화\n"
        f"구도: 중심 인물과 핵심 사건이 명확히 보이도록\n"
        f"주의: 이미지 안에 텍스트/자막/워터마크 넣지 말 것"
    )


def create_story(db: Session, story: StoryCreate) -> Story:
    newstory = Story(
        title=story.title,
        content=json.dumps(story.model_dump(), ensure_ascii=False),
    )
    db.add(newstory)
    db.commit()
    db.refresh(newstory)
    return newstory


def get_story(db: Session, story_id: int) -> dict | None:
    row = db.query(Story).filter(Story.id == story_id).first()
    return json.loads(row.content) if row else None


def create_images_for_story(db: Session, story: StoryLoad) -> List[StoryImageOut]:
    if not API_KEY:
        raise RuntimeError("GEMINI_API_KEY 환경변수가 설정되어 있지 않습니다.")

    client = genai.Client(api_key=API_KEY)

    story_id = story.id
    save_root = os.path.join("static", "stories", str(story_id))
    ensure_dir(save_root)

    existing = {
        img.idx
        for img in db.query(StoryImage).filter(StoryImage.story_id == story_id).all()
    }

    results: List[StoryImageOut] = []

    for idx, para in enumerate(story.paragraphs):
        if idx in existing:
            continue

        prompt = _build_prompt(story.title, para.title, para.text)

        resp = None
        for attempt in range(1, 4):
            try:
                resp = client.models.generate_images(
                    model=IMAGEN_MODEL,
                    prompt=prompt,
                    config=types.GenerateImagesConfig(
                        number_of_images=1,
                        aspect_ratio="1:1",
                    ),
                )
                break
            except genai_errors.ClientError as e:
                if getattr(e, "status_code", None) in (429, 500, 503):
                    time.sleep(5 * attempt)
                    continue
                resp = None
                break

        if not resp or not getattr(resp, "generated_images", None):
            continue

        file_path = os.path.join(save_root, f"{idx}.png")
        with open(file_path, "wb") as f:
            f.write(resp.generated_images[0].image.image_bytes)

        img_row = StoryImage(
            story_id=story_id,
            idx=idx,
            prompt=prompt,
            file_path=file_path,
            mime_type="image/png",
        )
        db.add(img_row)
        results.append(StoryImageOut(idx=idx, file_path=file_path, prompt=prompt))

        time.sleep(0.5)

    db.commit()
    return results
