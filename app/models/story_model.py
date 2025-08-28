from sqlalchemy import Column, Integer, String, Text, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base

class Story(Base):
    __tablename__ = "stories"
    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)

    images = relationship(
        "StoryImage",
        back_populates="story",
        cascade="all, delete-orphan",
        order_by="StoryImage.idx",
    )

class StoryImage(Base):
    __tablename__ = "story_images"
    id = Column(Integer, primary_key=True, autoincrement=True)
    story_id = Column(Integer, ForeignKey("stories.id", ondelete="CASCADE"), index=True, nullable=False)
    idx = Column(Integer, nullable=False)
    prompt = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    mime_type = Column(String, nullable=False, default="image/png")

    story = relationship("Story", back_populates="images")
