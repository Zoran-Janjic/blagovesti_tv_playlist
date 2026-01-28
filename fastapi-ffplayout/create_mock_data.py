import os
from pathlib import Path
import random

def create_mock_media(base_dir: Path):
    categories = [
        "Psaltir", "Molitve", "Duhovne pouke", "Deciji", "Serije", 
        "Dokumentarni", "Putopisi", "Muzika", "Ostalo", 
        "15min", "30min", "Spica_folder"
    ]
    
    if not base_dir.exists():
        base_dir.mkdir(parents=True)
        
    for cat in categories:
        cat_dir = base_dir / cat
        cat_dir.mkdir(exist_ok=True)
        
        # Create dummy files
        count = 5
        if cat in ["15min", "30min"]: count = 3
        
        for i in range(count):
            filename = f"MockVideo_{cat}_{i+1:03d}.mp4"
            if cat == "Serije":
                filename = f"MockSeries_S01E{i+1:02d}.mp4"
            
            # Using empty files for now, as ffprobe will fail on them
            # UNLESS we use the generator's fallback duration logic (which exists!)
            (cat_dir / filename).touch()

    # Create Spica explicitly
    (base_dir / "SPICA_BlagovestiTV.mp4").touch()
    
    print(f"Mock media created at {base_dir}")

if __name__ == "__main__":
    create_mock_media(Path("mock_media"))
