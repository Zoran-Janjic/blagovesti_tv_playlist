"""Generate daily playlist matching FFPlayout expected format."""
from pathlib import Path
from datetime import datetime
from typing import Dict, List
import json

class PlaylistGenerator:
    def __init__(self, video_directory: str, output_directory: str, config: dict):
        self.video_dir = Path(video_directory)
        self.output_dir = Path(output_directory)
        self.fixed_slots = config.get("fixed_slots", {})
        self.spica_every_n = config.get("spica_every_n", 3)
        self.spica_file = config.get("spica_file", "SPICA_BlagovestiTV.mp4")
        
        # State tracking for sequential playback
        self.state = self._load_state()
        
    def _load_state(self) -> dict:
        """Load state from file to track last played index per category."""
        state_file = self.output_dir / ".playlist_state.json"
        if state_file.exists():
            try:
                return json.loads(state_file.read_text())
            except:
                return {}
        return {}
    
    def _save_state(self):
        """Save state to file."""
        state_file = self.output_dir / ".playlist_state.json"
        state_file.write_text(json.dumps(self.state, indent=2))
    
    def _scan_videos(self) -> Dict[str, List[str]]:
        """Scan video directory and return dict of category -> sorted absolute file paths."""
        videos = {}
        if not self.video_dir.exists():
            return videos
        
        for folder in sorted(self.video_dir.iterdir()):
            if folder.is_dir():
                category = folder.name
                files = sorted([
                    str(f.resolve())  # use absolute paths
                    for f in folder.iterdir() 
                    if f.suffix.lower() in ('.mp4', '.mkv', '.mov', '.avi')
                ])
                if files:
                    videos[category] = files
        return videos
    
    def _get_next_video(self, category: str, videos: Dict[str, List[str]]) -> str:
        """Get next video from category using round-robin state."""
        files = videos.get(category, [])
        if not files:
            return None
        
        idx = self.state.get(category, 0) % len(files)
        chosen = files[idx]
        self.state[category] = idx + 1
        return chosen
    
    def _find_spica(self, videos: Dict[str, List[str]]) -> str:
        """Find spica file in any category."""
        for cat, files in videos.items():
            for f in files:
                if self.spica_file in f:
                    return f
        return None
    
    def generate_playlist(self, date: str = None) -> dict:
        """Generate FFPlayout format playlist."""
        if date:
            date_obj = datetime.strptime(date, "%Y-%m-%d")
        else:
            date_obj = datetime.now()
        
        videos = self._scan_videos()
        spica_path = self._find_spica(videos)
        
        program = []
        items_since_last_spica = 0  # track items since last spica insertion
        
        # Default duration for videos without metadata (15 min = 900 seconds)
        DEFAULT_DURATION = 900.0
        SPICA_DURATION = 25.066667
        
        # Categories for filling (exclude spica)
        fill_categories = [c for c in sorted(videos.keys()) if "spica" not in c.lower()]
        fill_idx = 0
        
        # Generate items - simple sequential fill
        max_items = 60  # limit for demo; in production fill 24 hours
        
        while len(program) < max_items and fill_categories:
            # Insert spica after every N regular items
            if items_since_last_spica >= self.spica_every_n and spica_path:
                program.append({
                    "in": 0.0,
                    "out": SPICA_DURATION,
                    "duration": SPICA_DURATION,
                    "source": spica_path
                })
                items_since_last_spica = 0  # reset counter after inserting spica
                continue
            
            # Get next content from categories (round-robin)
            cat = fill_categories[fill_idx % len(fill_categories)]
            fill_idx += 1
            video = self._get_next_video(cat, videos)
            
            if video:
                program.append({
                    "in": 0.0,
                    "out": DEFAULT_DURATION,
                    "duration": DEFAULT_DURATION,
                    "source": video
                })
                items_since_last_spica += 1  # increment counter for regular items only
        
        # Save state for next run
        self._save_state()
        
        return {
            "channel": "Channel 1",
            "date": date_obj.strftime("%Y-%m-%d"),
            "program": program
        }

    def save_playlist(self, playlist: dict, filepath: str):
        """Save playlist dict to JSON file."""
        Path(filepath).write_text(json.dumps(playlist, indent=2, ensure_ascii=False))