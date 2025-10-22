from pydantic_settings import BaseSettings
from pathlib import Path

# resolve project root and local mock_media by default for development
BASE_DIR = Path(__file__).resolve().parents[2]
DEFAULT_MOCK = str((BASE_DIR / "mock_media").resolve())

print(f"BASE_DIR set to: {BASE_DIR}")
print(f"DEFAULT_MOCK set to: {DEFAULT_MOCK}")

class Settings(BaseSettings):
    video_directory: str = DEFAULT_MOCK
    output_directory: str = str((BASE_DIR / "playlists").resolve())
    
    # Fixed daily time slots -> category mapping
    fixed_slots: dict = {
        "06:00:00": "psaltir",      # Psaltir morning (katizma sequential)
        "07:14:00": "molitve",      # Jutarnja molitva (fixed)
        "13:00:00": "serije",       # Series/films slot 1
        "18:00:00": "molitve",      # Evening prayer
        "19:00:00": "deciji",       # Children's program
        "20:00:00": "serije",       # Series/films slot 2
        "22:24:00": "psaltir",      # Psaltir evening (katizma sequential)
        "23:00:00": "serije",       # Series/films slot 3
    }
    
    # Category folder name mappings (folder name substring -> logical category)
    category_map: dict = {
        "psaltir": "psaltir",
        "molitv": "molitve",
        "duhov": "duhovne_pouke",
        "decij": "deciji",
        "serij": "serije",
        "dokument": "dokumentarni",
        "putopis": "putopisi",
        "muzik": "muzika",
        "ostalo": "ostalo",
        "spica": "spica",
    }
    
    # How often to insert spica (after N regular items)
    spica_every_n: int = 3
    
    # Spica file name
    spica_file: str = "SPICA_BlagovestiTV.mp4"

    class Config:
        env_file = ".env"

settings = Settings()