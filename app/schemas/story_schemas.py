from typing import List, Optional, Union
from pydantic import BaseModel

class StoryParagraph(BaseModel):
    title: str
    text: str

class StoryCreate(BaseModel):
    title: str
    paragraphs: List[StoryParagraph]

class StoryLoad(BaseModel):
    id: int
    title: str
    paragraphs: List[StoryParagraph]

class StoryImageOut(BaseModel):
    idx: int
    file_path: str
    prompt: str

class StoryMakeResponse(BaseModel):
    story_id: int
    title: str
    images: List[StoryImageOut] = []

# /clova/make 입력용
class StoryData(BaseModel):
    title: Optional[str] = None
    hero: Optional[str] = None
    age: Optional[Union[int, str]] = None
    theme: Optional[str] = None
    extra: Optional[str] = None
