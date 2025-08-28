# app/services/test.py
import json
from app.core.database import SessionLocal
from app.schemas.story_schemas import StoryCreate, StoryLoad
from app.services.story_service import create_story, create_images_for_story

payload = {
    "title": "민준의 우주 대모험",
    "paragraphs": [
        {
            "title": "시작",
            "text": "민준의 마음속에는 우주을(를) 향한 작은 꿈이 자라났어요. 민준은(는) 오늘, 우주을(를) 향해 작은 발걸음을 내딛었어요. 따뜻 분위기 속에서 이야기의 문이 열렸답니다."
        },
        {
            "title": "모험 1",
            "text": "친구들의 응원이 힘이 되어 민준은(는) 용기를 냈답니다. 그러다 갑자기 나타난 문제를 함께 해결하기로 했어요. 따뜻 감정이 민준의 마음을 가만히 감싸 주었지요."
        },
        {
            "title": "모험 2",
            "text": "민준은(는) 낯선 순간에도 깊게 숨을 쉬고 천천히 주변을 살폈어요. 그러다 우주의 비밀을 알아내기 위해 조심스럽게 다가갔어요. 따뜻 감정이 민준의 마음을 가만히 감싸 주었지요."
        },
        {
            "title": "모험 3",
            "text": "작은 실수를 해도 민준은(는) 다시 일어나 한 걸음 더 내디뎠어요. 그러다 우주의 비밀을 알아내기 위해 조심스럽게 다가갔어요. 따뜻 감정이 민준의 마음을 가만히 감싸 주었지요."
        },
        {
            "title": "모험 4",
            "text": "작은 실수를 해도 민준은(는) 다시 일어나 한 걸음 더 내디뎠어요. 그러다 갑자기 나타난 문제를 함께 해결하기로 했어요. 따뜻 감정이 민준의 마음을 가만히 감싸 주었지요."
        },
        {
            "title": "마무리",
            "text": "돌아보니, 작은 변화들이 큰 용기가 되었음을 알게 되었어요. 그래서 민준은(는) 알게 되었어요. “천천히 가도 좋아요, 중요한 건 멈추지 않는 마음이에요.”"
        }
    ]
}


def main():
    db = SessionLocal()
    try:
        # 1) 스토리 저장
        story_in = StoryCreate(**payload)
        row = create_story(db, story_in)

        # 2) StoryLoad 변환
        story_load = StoryLoad(
            id=row.id,
            title=story_in.title,
            paragraphs=story_in.paragraphs
        )

        # 3) 이미지 생성
        results = create_images_for_story(db, story_load)

        # 4) 출력
        print("Story ID:", row.id)
        print("Title   :", story_in.title)
        print("Images:")
        if results:
            for r in results:
                print(f"  - idx={r.idx}, path={r.file_path}")
        else:
            print("  (생성된 이미지가 없습니다)")
    finally:
        db.close()


if __name__ == "__main__":
    main()
