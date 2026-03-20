from pydantic import BaseModel, HttpUrl
from typing import Optional, List
from enum import Enum


class BookmarkType(str, Enum):
    web = "web"
    twitter = "twitter"
    youtube = "youtube"


class BookmarkCreate(BaseModel):
    url: str
    tags: List[str] = []


class BookmarkUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    read: Optional[bool] = None


class TagOut(BaseModel):
    id: int
    name: str


class BookmarkOut(BaseModel):
    id: int
    url: str
    title: Optional[str]
    description: Optional[str]
    thumbnail: Optional[str]
    type: str
    read: bool
    created_at: str
    updated_at: str
    tags: List[str] = []
