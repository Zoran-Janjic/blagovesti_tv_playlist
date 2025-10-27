"""Generate daily playlist matching FFPlayout expected format."""
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List
import json
import subprocess

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
    
    def _get_video_duration(self, filepath: str) -> float:
        """Get video duration in seconds using ffprobe."""
        try:
            result = subprocess.run(
                [
                    'ffprobe',
                    '-v', 'error',
                    '-show_entries', 'format=duration',
                    '-of', 'default=noprint_wrappers=1:nokey=1',
                    filepath
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=10
            )
            duration = float(result.stdout.strip())
            return duration if duration > 0 else 900.0  # fallback to 15 min
        except Exception as e:
            print(f"Warning: Could not get duration for {filepath}: {e}")
            return 900.0  # fallback duration
    
    def _scan_videos(self) -> Dict[str, List[dict]]:
        """Scan video directory and return dict of category -> list of {path, duration}."""
        videos = {}
        if not self.video_dir.exists():
            return videos
        
        for folder in sorted(self.video_dir.iterdir()):
            if folder.is_dir():
                category = folder.name
                files = []
                for f in sorted(folder.iterdir()):
                    if f.suffix.lower() in ('.mp4', '.mkv', '.mov', '.avi'):
                        abs_path = str(f.resolve())
                        duration = self._get_video_duration(abs_path)
                        files.append({"path": abs_path, "duration": duration})
                if files:
                    videos[category] = files
        return videos
    
    def _get_next_video(self, category: str, videos: Dict[str, List[dict]]) -> dict:
        """Get next video from category using round-robin state."""
        files = videos.get(category, [])
        if not files:
            return None
        
        idx = self.state.get(category, 0) % len(files)
        chosen = files[idx]
        self.state[category] = idx + 1
        return chosen
    
    def _find_spica(self, videos: Dict[str, List[dict]]) -> dict:
        """Find spica file in any category."""
        for cat, files in videos.items():
            for f in files:
                if self.spica_file in f["path"]:
                    return f
        return None
    
    def _map_folder_to_category(self, folder_name: str) -> str:
        """Map folder name to logical category."""
        folder_lower = folder_name.lower()
        if "psaltir" in folder_lower:
            return "psaltir"
        elif "molitv" in folder_lower:
            return "molitve"
        elif "duhov" in folder_lower or "pouke" in folder_lower:
            return "duhovne_pouke"
        elif "decij" in folder_lower:
            return "deciji"
        elif "serij" in folder_lower or "film" in folder_lower:
            return "serije"
        elif "dokument" in folder_lower:
            return "dokumentarni"
        elif "putopis" in folder_lower:
            return "putopisi"
        elif "muzik" in folder_lower:
            return "muzika"
        else:
            return "ostalo"
    
    def generate_playlist(self, date: str = None) -> dict:
        """
        Generate FFPlayout format playlist for full 24 hours with fixed time slots.
        """
        if date:
            date_obj = datetime.strptime(date, "%Y-%m-%d")
        else:
            date_obj = datetime.now()
        
        videos = self._scan_videos()
        spica_path_info = self._find_spica(videos)
        
        # Build category mapping: logical_category -> [video_info]
        category_videos = {}
        for folder, files in videos.items():
            logical_cat = self._map_folder_to_category(folder)
            if logical_cat not in category_videos:
                category_videos[logical_cat] = []
            category_videos[logical_cat].extend(files)
        
        # Parse fixed slots into datetime -> category
        day_start = datetime.combine(date_obj.date(), datetime.strptime("06:00:00", "%H:%M:%S").time())
        day_end = day_start + timedelta(days=1)
        
        fixed_schedule = {}
        for time_str, cat in self.fixed_slots.items():
            try:
                slot_time = datetime.combine(date_obj.date(), datetime.strptime(time_str, "%H:%M:%S").time())
                if slot_time < day_start:
                    slot_time += timedelta(days=1)
                fixed_schedule[slot_time] = cat
            except:
                continue
        
        program = []
        cursor = day_start
        items_since_last_spica = 0
        
        # Categories for filling gaps (exclude spica)
        fill_categories = [c for c in sorted(category_videos.keys()) if c != "spica"]
        fill_idx = 0
        
        # Generate full 24-hour schedule
        while cursor < day_end:
            # Check if we have a fixed slot at current time
            if cursor in fixed_schedule:
                cat = fixed_schedule[cursor]
                video_info = self._get_next_video(cat, category_videos)
                
                if video_info:
                    duration = video_info["duration"]
                    program.append({
                        "in": 0.0,
                        "out": duration,
                        "duration": duration,
                        "source": video_info["path"]
                    })
                    items_since_last_spica += 1
                    cursor += timedelta(seconds=duration)
                else:
                    # No video in this category, skip ahead 15 min
                    cursor += timedelta(minutes=15)
                continue
            
            # Insert spica after every N regular items
            if items_since_last_spica >= self.spica_every_n and spica_path_info:
                duration = spica_path_info["duration"]
                program.append({
                    "in": 0.0,
                    "out": duration,
                    "duration": duration,
                    "source": spica_path_info["path"]
                })
                items_since_last_spica = 0
                cursor += timedelta(seconds=duration)
                continue
            
            # Fill with content from categories (round-robin)
            if fill_categories:
                cat = fill_categories[fill_idx % len(fill_categories)]
                fill_idx += 1
                video_info = self._get_next_video(cat, category_videos)
                
                if video_info:
                    duration = video_info["duration"]
                    program.append({
                        "in": 0.0,
                        "out": duration,
                        "duration": duration,
                        "source": video_info["path"]
                    })
                    items_since_last_spica += 1
                    cursor += timedelta(seconds=duration)
                else:
                    # No more videos in rotation, skip ahead
                    cursor += timedelta(minutes=15)
            else:
                # No categories available, stop
                break
        
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