from typing import Optional, Any
from pydantic import BaseModel, ConfigDict
from datetime import datetime
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
class TokenRefresh(BaseModel):
    refresh_token: str
class TokenData(BaseModel):
    user_id: Optional[int] = None
class UserBase(BaseModel):
    id: int
    username: str
    email: str
    avatar: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)
class UserCreate(BaseModel):
    username: str
    email: str
    password: str
    model_config = ConfigDict(from_attributes=True)
class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[str] = None
    avatar: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)
class UserResponse(UserBase):
    boards: list["BoardResponse"] = []
    model_config = ConfigDict(from_attributes=True)
class BoardBase(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    owner_id: int
    model_config = ConfigDict(from_attributes=True)
class BoardCreate(BaseModel):
    name: str
    description: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)
class BoardUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)
class BoardResponse(BoardBase):
    lists: list["ListResponse"] = []
    members: list["UserResponse"] = []
    model_config = ConfigDict(from_attributes=True)
class ListBase(BaseModel):
    id: int
    name: str
    position: int
    board_id: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)
class ListCreate(BaseModel):
    name: str
    board_id: int
    model_config = ConfigDict(from_attributes=True)
class ListUpdate(BaseModel):
    name: Optional[str] = None
    position: Optional[int] = None
    model_config = ConfigDict(from_attributes=True)
class ListResponse(ListBase):
    cards: list["CardResponse"] = []
    model_config = ConfigDict(from_attributes=True)
class CardBase(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    position: int
    list_id: int
    created_at: datetime
    updated_at: datetime
    due_date: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)
class CardCreate(BaseModel):
    title: str
    description: Optional[str] = None
    list_id: int
    due_date: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)
class CardUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    position: Optional[int] = None
    due_date: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)
class CardResponse(CardBase):
    labels: list["LabelResponse"] = []
    comments: list["CommentResponse"] = []
    assignees: list["UserResponse"] = []
    model_config = ConfigDict(from_attributes=True)
class LabelBase(BaseModel):
    id: int
    name: str
    color: str
    board_id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
class LabelCreate(BaseModel):
    name: str
    color: str
    board_id: int
    model_config = ConfigDict(from_attributes=True)
class LabelUpdate(BaseModel):
    name: Optional[str] = None
    color: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)
class LabelResponse(LabelBase):
    model_config = ConfigDict(from_attributes=True)
class CommentBase(BaseModel):
    id: int
    content: str
    card_id: int
    author_id: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)
class CommentCreate(BaseModel):
    content: str
    card_id: int
    model_config = ConfigDict(from_attributes=True)
class CommentUpdate(BaseModel):
    content: str
    model_config = ConfigDict(from_attributes=True)
class CommentResponse(CommentBase):
    author: "UserResponse"
    model_config = ConfigDict(from_attributes=True)
class CardMove(BaseModel):
    card_id: int
    new_list_id: int
    new_position: int
    model_config = ConfigDict(from_attributes=True)
class BoardMemberAdd(BaseModel):
    user_id: int
    board_id: int
    model_config = ConfigDict(from_attributes=True)