from pathlib import Path
import os

def scan_video_files(directory: str):
    video_extensions = {'.mp4', '.mkv', '.avi', '.mov', '.flv'}
    video_files = {}

    for root, dirs, files in os.walk(directory):
        category = Path(root).name
        video_files[category] = [
            file for file in files if Path(file).suffix in video_extensions
        ]

    return video_files

def get_available_video_files():
    directory = '/var/lib/ffplayout/tv-media/emisije/'
    return scan_video_files(directory)