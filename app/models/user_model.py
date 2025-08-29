from sqlalchemy import Column, Integer, String, Text, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base

class User(Base):
    __tablename__ = "user"
    id = Column(Integer, primary_key=True)
    naver_id = Column(String, nullable=False, unique=True)
    name = Column(String, nullable=False)
    child_name = Column(String, nullable=True)
    child_age = Column(Integer, nullable=True)
    child_pers = Column(String, nullable=True)
    child_gender = Column(String, nullable=True)

    stories = relationship(
        "Story",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
