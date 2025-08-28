from pydantic import BaseModel
from typing import List

class Paragraph(BaseModel):
    title: str
    text: str

class StoryCreate(BaseModel):
    title: str
    paragraphs: List[Paragraph]

class StoryLoad(BaseModel):
    id: int
    title: str
    paragraphs: List[Paragraph]

class StoryImageOut(BaseModel):
    idx: int
    file_path: str
    prompt: str