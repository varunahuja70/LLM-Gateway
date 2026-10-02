from pydantic import BaseModel, EmailStr, Field


class SetupStatusResponse(BaseModel):
    is_setup: bool


class SetupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class LoginResponse(BaseModel):
    id: str
    email: str
    csrf_token: str


class MeResponse(BaseModel):
    id: str
    email: str
    csrf_token: str


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=12, max_length=128)


class MessageResponse(BaseModel):
    message: str
