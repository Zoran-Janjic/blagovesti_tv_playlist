import sys
import os
import json
from pathlib import Path
from datetime import datetime

# Adjust path to import app modules
sys.path.append(os.getcwd())

from app.services.playlist_generator import PlaylistGenerator
from app.core.config import settings

def test_generation():
    print("Testing Playlist Generation...")
    
    # Override settings for mock
    video_dir = "mock_media"
    out_dir = "test_output"
    Path(out_dir).mkdir(exist_ok=True)
    
    config = {
        "fixed_slots": {},
        "spica_after_every_item": True,
        "spica_file": "SPICA_BlagovestiTV.mp4",
        "strict_fixed_slots": False,
        "target_duration_hours": 23.0,
        "recurrence_exclusion_days": 10,
        "filler_categories": {"15min": "15min", "30min": "30min"}
    }
    
    generator = PlaylistGenerator(video_dir, out_dir, config)
    
    # Use existing example file as template
    template_path = "exampleGeneratedFile.json"
    if not Path(template_path).exists():
        print(f"Error: {template_path} not found.")
        return

    print(f"Generating playlist from template: {template_path}")
    playlist = generator.generate_playlist_from_template(template_path, date="2026-06-01")
    
    # Verify Output
    program = playlist.get("program", [])
    print(f"Generated {len(program)} items.")
    
    # Check for Filler
    fillers = [item for item in program if "15min" in item["source"] or "30min" in item["source"]]
    print(f"Fillers inserted: {len(fillers)}")
    if fillers:
        print("Sample Filler:", fillers[0]["source"])
        
    # Check for specific structure preservation
    # (e.g. check if spica is after every item if enabled)
    spicas = [item for item in program if "SPICA" in item["source"]]
    print(f"Spicas inserted: {len(spicas)}")
    
    # Recurrence Check (Second Run)
    print("\nRunning Generation Day 2 (Simulating recurrence check)...")
    playlist2 = generator.generate_playlist_from_template(template_path, date="2026-06-02")
    program2 = playlist2.get("program", [])
    
    # Compare first non-spica item
    def get_real_items(prog):
        return [p["source"] for p in prog if "SPICA" not in p["source"]]
        
    items1 = get_real_items(program)
    items2 = get_real_items(program2)
    
    print(f"Day 1 First Item: {items1[0] if items1 else 'None'}")
    print(f"Day 2 First Item: {items2[0] if items2 else 'None'}")
    
    if items1 and items2 and items1[0] != items2[0]:
        print("SUCCESS: Items changed (Recurrence logic working)")
    elif items1 and items2 and items1[0] == items2[0]:
        print("WARNING: Item repeated (Might be due to low content count in mock data)")
    
    # Save output for inspection
    with open(f"{out_dir}/test_playlist.json", 'w') as f:
        json.dump(playlist, f, indent=2)
    print(f"Saved to {out_dir}/test_playlist.json")

if __name__ == "__main__":
    test_generation()
