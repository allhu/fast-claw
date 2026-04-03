from pydantic import BaseModel, HttpUrl
from typing import Optional, List
from datetime import datetime

class StoreCreate(BaseModel):
    url: str
    source: Optional[str] = "unknown"

class ContactResponse(BaseModel):
    id: int
    store_id: int
    email: Optional[str] = None
    phone: Optional[str] = None
    instagram: Optional[str] = None
    facebook: Optional[str] = None
    whatsapp: Optional[str] = None

    class Config:
        from_attributes = True

class StoreResponse(BaseModel):
    id: int
    url: str
    source: str
    status: str
    created_at: datetime
    contacts: List[ContactResponse] = []

    class Config:
        from_attributes = True

class TaskCreate(BaseModel):
    task_type: str
    parameters: Optional[dict] = None

class TaskResponse(BaseModel):
    id: int
    task_type: str
    status: str
    parameters: Optional[str] = None
    result_summary: Optional[str] = None
    
    # New tracking fields
    progress_text: Optional[str] = None
    current_keyword: Optional[str] = None
    items_found: int = 0
    items_saved: int = 0
    
    created_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class KeywordBase(BaseModel):
    word: str
    schedule_interval: Optional[str] = "weekly"
    source: Optional[str] = "manual"
    parent_id: Optional[int] = None

class KeywordCreate(KeywordBase):
    pass

class KeywordResponse(KeywordBase):
    id: int
    is_active: bool
    current_status: str
    source: str
    last_run_at: Optional[datetime] = None
    next_run_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True
