from pydantic import BaseModel
from typing import List, Optional

class VideoFile(BaseModel):
    name: str
    path: str
    category: Optional[str] = None

class Playlist(BaseModel):
    schedule: str
    videos: List[VideoFile]