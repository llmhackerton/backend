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

IMAGEN_MODEL = os.getenv("GEMINI_IMAGE_MODEL", "imagen-3.0-generate-002")

def create_story(db: Session, payload: StoryCreate, user_id: int) -> Story:
    content = json.dumps([p.dict() for p in payload.paragraphs], ensure_ascii=False)
    row = Story(user_id=user_id, title=payload.title, content=content)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row

def _ensure_dir(path: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)

def build_base_style_prompt(story_title: str) -> str:
    return (
        "아래 원칙을 모든 장면에 동일하게 적용해.\n"
        f"- 동화 제목: {story_title}\n"
        "- 주인공의 외형/의상/헤어스타일/소품은 첫 장면에서 정한 설정을 끝까지 유지해.\n"
        "- 장면에 언급되지 않은 인물/사물/문구는 넣지 마.\n"
        "- 그림에 글자/워터마크/로고/텍스트를 넣지 마.\n"
        "- 따뜻한 색감, 부드러운 일러스트, 아동 친화적 스타일, 1:1 구도.\n"
        "- 배경은 장면에 필요한 요소만 간결하게.\n"
        "\nApply the following rules consistently across all scenes:\n"
        f"- Story title: {story_title}\n"
        "- Keep the main character's appearance/outfit/hair/props consistent across scenes.\n"
        "- Do NOT add any characters/objects/text that are not mentioned.\n"
        "- No text/watermark/logo in the image.\n"
        "- Warm palette, soft children's illustration style, square (1:1) composition.\n"
        "- Keep backgrounds minimal and relevant to the scene.\n"
    )

def _build_prompt(story_title: str, scene_title: str, scene_text: str, scene_idx: int, scene_total: int, base_style: str) -> str:
    return (
        "아래의 장면 설명과 규칙을 ‘정확히’ 반영한 유아용 동화 일러스트 1장을 생성해.\n"
        f"{base_style}\n"
        f"[장면 {scene_idx}/{scene_total}]\n"
        f"- 장면 제목: {scene_title}\n"
        f"- 장면 요약: {scene_text}\n"
        "- 반드시 요약에 언급된 행동/감정/사물 중심으로 그려.\n"
        "- 추가 인물/소품을 임의로 만들지 마.\n"
        "- 카메라 구도는 주인공과 핵심 사건이 한눈에 보이도록.\n"
        "\nGenerate ONE children's story illustration that matches the scene EXACTLY.\n"
        f"{base_style}\n"
        f"[Scene {scene_idx}/{scene_total}]\n"
        f"- Scene title: {scene_title}\n"
        f"- Scene summary (Korean): {scene_text}\n"
        "- Depict ONLY what is described (characters, objects, emotions, actions).\n"
        "- Do NOT invent extra characters or items.\n"
        "- Ensure the main character is clearly visible; keep the same look as previous scenes.\n"
    )

def create_images_for_story(db: Session, story: StoryLoad) -> List[StoryImageOut]:
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY 또는 GOOGLE_API_KEY 환경변수를 설정하세요.")

    client = genai.Client(api_key=api_key)
    story_id = story.id
    out_dir = os.path.join("static", "stories", str(story_id))
    results: List[StoryImageOut] = []

    total = len(story.paragraphs)
    base_style = build_base_style_prompt(story.title)

    for idx, para in enumerate(story.paragraphs, start=1):
        prompt = _build_prompt(
            story_title=story.title,
            scene_title=para.title,
            scene_text=para.text,
            scene_idx=idx,
            scene_total=total,
            base_style=base_style,
        )
        try:
            resp = client.models.generate_images(
                model=IMAGEN_MODEL,
                prompt=prompt,
                config=types.GenerateImagesConfig(
                    number_of_images=1,
                    output_mime_type="image/png",
                ),
            )
        except genai_errors.APIError as e:
            print("GenAI API error:", e)
            continue
        except Exception as e:
            print("Unexpected image gen error:", e)
            continue

        if not resp.generated_images:
            continue

        generated = resp.generated_images[0]
        if not generated or not getattr(generated, "image", None):
            continue

        image_obj = generated.image
        file_path = os.path.join(out_dir, f"{idx:02d}.png")
        _ensure_dir(file_path)
        image_obj.save(file_path) 

        db.add(StoryImage(
            story_id=story_id,
            idx=idx,
            prompt=prompt, 
            file_path=file_path,
            mime_type="image/png",
        ))
        results.append(StoryImageOut(idx=idx, file_path=file_path, prompt=""))
        time.sleep(0.2)

    db.commit()
    return results
