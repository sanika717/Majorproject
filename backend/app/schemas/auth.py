from typing import Optional
from pydantic import BaseModel
from backend.app.models.user import UserRole

class UserRegister(BaseModel):
    username: str
    email: str
    password: str
    role: Optional[UserRole] = UserRole.USER

class UserLogin(BaseModel):
    username_or_email: str
    password: str

class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    role: UserRole
    is_active: bool

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
