from typing import Optional
from pydantic import BaseModel

class UserUpdateSchema(BaseModel):

    name: Optional[str] = None 
    child_name: Optional[str] = None
    child_age: Optional[int] = None
    child_pers: Optional[str] = None
    child_gender: Optional[str] = None
