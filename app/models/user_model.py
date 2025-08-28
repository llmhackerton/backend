from sqlalchemy import Column, Integer, String, Text, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base

class User(Base):
    __tablename__ = "user"
    id = Column(Integer, primary_key=True)
    naver_id = Column(String, nullable=False, unique=True)
    name = Column(String, nullable=False)
