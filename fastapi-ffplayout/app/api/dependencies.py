from fastapi import Depends
from app.services.scanner import scan_video_files
from app.core.config import settings

def get_video_files():
    return scan_video_files(settings.video_directory)