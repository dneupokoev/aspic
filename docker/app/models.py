from dataclasses import dataclass
from typing import Optional
from datetime import datetime

@dataclass
class File:
    token: str
    filename: str
    filepath: str
    size: int
    mime_type: str
    deleted_comment_id: Optional[int]
    created_at: datetime

@dataclass
class Comment:
    id: int
    file_token: str
    action_type: str
    author_name: str
    author_ip: str
    content: str
    created_at: datetime