"""Generate daily playlist matching FFPlayout expected format."""
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List
import json
import subprocess
import random
import re

class PlaylistGenerator:
    def __init__(self, video_directory: str, output_directory: str, config: dict):
        self.video_dir = Path(video_directory)
        self.output_dir = Path(output_directory)
        self.fixed_slots = config.get("fixed_slots", {})
        self.spica_every_n = config.get("spica_every_n", 3)
        self.spica_file = config.get("spica_file", "SPICA_BlagovestiTV.mp4")
        
        # State tracking for sequential playback
        self.state = self._load_state()
        
        # Daily movie/series selection (will repeat 3 times)
        self.daily_movies = {}
        
    def _load_state(self) -> dict:
        """Load state from file to track last played index per category."""
        state_file = self.output_dir / ".playlist_state.json"
        if state_file.exists():
            try:
                with open(state_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Warning: Could not load state file: {e}")
                return {}
        return {}
    
    def _save_state(self):
        """Save state to file."""
        state_file = self.output_dir / ".playlist_state.json"
        try:
            # Ensure directory exists
            state_file.parent.mkdir(parents=True, exist_ok=True)
            with open(state_file, 'w', encoding='utf-8') as f:
                json.dump(self.state, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Warning: Could not save state file: {e}")
    
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
    
    def _get_next_video(self, category: str, videos: Dict[str, List[dict]], skip_daily: bool = True) -> dict:
        """
        Get next video from category using round-robin state.
        
        Args:
            category: Category name
            videos: Videos dictionary
            skip_daily: If True, skip videos that are selected as daily movies
        """
        files = videos.get(category, [])
        if not files:
            return None
        
        # Get current index for this category
        state_key = f"{category}_index"
        idx = self.state.get(state_key, 0) % len(files)
        
        # If we need to skip daily movies, find next non-daily video
        if skip_daily and category in self.daily_movies:
            daily_path = self.daily_movies[category]["path"]
            attempts = 0
            max_attempts = len(files)
            
            while files[idx]["path"] == daily_path and attempts < max_attempts:
                idx = (idx + 1) % len(files)
                attempts += 1
            
            # If all videos are the daily video (only 1 video in category), use it anyway
            if attempts >= max_attempts:
                idx = self.state.get(state_key, 0) % len(files)
        
        chosen = files[idx]
        
        # Update state to next video
        self.state[state_key] = (idx + 1) % len(files)
        
        return chosen
    
    def _is_movie_category(self, category: str) -> bool:
        """Check if category contains movies/series that should repeat."""
        movie_categories = ["serije", "dokumentarni", "deciji"]
        return category in movie_categories
    
    def _is_spica_category(self, category: str) -> bool:
        """Check if category is a SPICA-related folder."""
        category_lower = category.lower()
        return category_lower == "spica" or category_lower == "spica_folder" or "spica" in category_lower
    
    def _extract_series_info(self, filename: str) -> dict:
        """
        Extract series name, season, and episode number from filename.
        Examples:
          - KatarinaVelika_SEZONA2_1_serija.mp4 -> {name: "KatarinaVelika", season: 2, episode: 1}
          - SeriesName_S01E05.mp4 -> {name: "SeriesName", season: 1, episode: 5}
        """
        # Pattern 1: Name_SEZONAX_Y_serija.ext
        pattern1 = r'(.+?)_SEZONA(\d+)_(\d+)_serija'
        match = re.search(pattern1, filename, re.IGNORECASE)
        if match:
            return {
                "name": match.group(1),
                "season": int(match.group(2)),
                "episode": int(match.group(3))
            }
        
        # Pattern 2: Name_S##E##.ext
        pattern2 = r'(.+?)_S(\d+)E(\d+)'
        match = re.search(pattern2, filename, re.IGNORECASE)
        if match:
            return {
                "name": match.group(1),
                "season": int(match.group(2)),
                "episode": int(match.group(3))
            }
        
        return None
    
    def _group_series_by_name(self, videos: List[dict]) -> Dict[str, List[dict]]:
        """Group series files by series name and sort by season/episode."""
        series_groups = {}
        
        for video in videos:
            filename = Path(video["path"]).name
            series_info = self._extract_series_info(filename)
            
            if series_info:
                series_name = series_info["name"]
                if series_name not in series_groups:
                    series_groups[series_name] = []
                
                video_with_info = video.copy()
                video_with_info["series_info"] = series_info
                series_groups[series_name].append(video_with_info)
        
        # Sort each series by season and episode
        for series_name in series_groups:
            series_groups[series_name].sort(
                key=lambda x: (x["series_info"]["season"], x["series_info"]["episode"])
            )
        
        return series_groups
    
    def _select_daily_movies(self, videos: Dict[str, List[dict]], date_str: str) -> dict:
        """Select one movie/series per category for the day that will repeat 3 times."""
        daily_selection = {}
        
        # Categories that should have daily repeating content
        movie_categories = ["serije", "dokumentarni", "deciji"]
        
        for category in movie_categories:
            files = videos.get(category, [])
            if not files:
                continue
            
            # Special handling for serije (sequential episodes)
            if category == "serije":
                series_groups = self._group_series_by_name(files)
                
                if series_groups:
                    # Get state key for this date
                    state_key = f"{category}_episode_{date_str}"
                    
                    # Check if we already selected an episode for this date
                    if state_key in self.state:
                        # Use the stored selection
                        stored_path = self.state[state_key]
                        for video in files:
                            if video["path"] == stored_path:
                                daily_selection[category] = video
                                break
                    else:
                        # Select next episode in sequence
                        last_episode_key = f"{category}_last_episode"
                        last_episode_path = self.state.get(last_episode_key)
                        
                        # Find which series to continue
                        selected_video = None
                        
                        if last_episode_path:
                            # Find the last played episode and get next one
                            for series_name, episodes in series_groups.items():
                                for i, ep in enumerate(episodes):
                                    if ep["path"] == last_episode_path:
                                        # Found last episode, get next one
                                        next_idx = (i + 1) % len(episodes)
                                        selected_video = episodes[next_idx]
                                        break
                                if selected_video:
                                    break
                        
                        # If no last episode or series completed, start from first series
                        if not selected_video:
                            first_series = next(iter(series_groups.values()))
                            selected_video = first_series[0]
                        
                        daily_selection[category] = selected_video
                        
                        # Store the selection for this date
                        self.state[state_key] = selected_video["path"]
                        self.state[last_episode_key] = selected_video["path"]
                else:
                    # No series format detected, use round-robin
                    state_key = f"{category}_daily_{date_str}"
                    if state_key in self.state:
                        stored_path = self.state[state_key]
                        for video in files:
                            if video["path"] == stored_path:
                                daily_selection[category] = video
                                break
                    else:
                        # Use round-robin selection
                        idx_key = f"{category}_daily_index"
                        idx = self.state.get(idx_key, 0) % len(files)
                        daily_selection[category] = files[idx]
                        self.state[idx_key] = (idx + 1) % len(files)
                        self.state[state_key] = files[idx]["path"]
            else:
                # For other categories (dokumentarni, deciji), use round-robin selection
                state_key = f"{category}_daily_{date_str}"
                if state_key in self.state:
                    stored_path = self.state[state_key]
                    for video in files:
                        if video["path"] == stored_path:
                            daily_selection[category] = video
                            break
                else:
                    # Use round-robin selection
                    idx_key = f"{category}_daily_index"
                    idx = self.state.get(idx_key, 0) % len(files)
                    daily_selection[category] = files[idx]
                    self.state[idx_key] = (idx + 1) % len(files)
                    self.state[state_key] = files[idx]["path"]
        
        return daily_selection
    
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
    
    def _should_play_movie(self, current_time: datetime) -> bool:
        """Determine if it's time to play daily movies (3 times: noon, late afternoon, evening)."""
        hour = current_time.hour
        
        # Around noon: 12:00-14:00
        if 12 <= hour < 14:
            return True
        # Late afternoon: 16:00-18:00
        elif 16 <= hour < 18:
            return True
        # Evening: 20:00-22:00
        elif 20 <= hour < 22:
            return True
        
        return False
    
    def save_playlist(self, playlist: dict, filepath: str):
        """Save playlist dict to JSON file."""
        Path(filepath).write_text(json.dumps(playlist, indent=2, ensure_ascii=False))
        
    def generate_playlist(self, date: str = None) -> dict:
        """
        Generate FFPlayout format playlist for full 24 hours with fixed time slots.
        
        Features:
        - Movies/series (serije, dokumentarni, deciji) selected for the day repeat 3 times
        - For serije, episodes progress sequentially day by day
        - All other categories use round-robin to cycle through content without repetition
        - Fixed time slots are strictly enforced
        - SPICA appears after every N items (excluding fixed slots and movies)
        """
        if date:
            date_obj = datetime.strptime(date, "%Y-%m-%d")
        else:
            date_obj = datetime.now()
        
        date_str = date_obj.strftime("%Y-%m-%d")
        
        videos = self._scan_videos()
        spica_path_info = self._find_spica(videos)
        
        # Select daily movies/series that will repeat 3 times
        self.daily_movies = self._select_daily_movies(videos, date_str)
        movie_play_count = {cat: 0 for cat in self.daily_movies.keys()}
        
        # Build category mapping: logical_category -> [video_info]
        category_videos = {}
        for folder, files in videos.items():
            # Skip SPICA folders completely from category mapping
            if self._is_spica_category(folder):
                continue
                
            logical_cat = self._map_folder_to_category(folder)
            if logical_cat not in category_videos:
                category_videos[logical_cat] = []
            category_videos[logical_cat].extend(files)
        
        # Parse fixed slots into datetime -> category (sorted by time)
        day_start = datetime.combine(date_obj.date(), datetime.strptime("06:00:00", "%H:%M:%S").time())
        day_end = day_start + timedelta(days=1)
        
        fixed_schedule = []
        for time_str, cat in self.fixed_slots.items():
            try:
                slot_time = datetime.combine(date_obj.date(), datetime.strptime(time_str, "%H:%M:%S").time())
                if slot_time < day_start:
                    slot_time += timedelta(days=1)
                fixed_schedule.append((slot_time, cat))
            except:
                continue
        
        # Sort by time
        fixed_schedule.sort(key=lambda x: x[0])
        
        program = []
        cursor = day_start
        items_since_last_spica = 0
        fixed_idx = 0
        
        # Categories for filling gaps (exclude movie categories - SPICA already excluded above)
        fill_categories = [c for c in sorted(category_videos.keys()) 
                          if c not in ["serije", "dokumentarni", "deciji"]]
        fill_idx = 0
        
        # Track last added item to prevent consecutive spicas
        last_was_spica = False
        
        # Track if we've played movies in current time window
        last_movie_hour = {cat: -1 for cat in self.daily_movies.keys()}
        
        # Generate full 24-hour schedule
        while cursor < day_end:
            # Check if we need to jump to a fixed slot
            if fixed_idx < len(fixed_schedule):
                slot_time, slot_cat = fixed_schedule[fixed_idx]
                
                # If we're past or at the slot time, insert it NOW
                if cursor >= slot_time:
                    # If it's a movie category and we have daily selection, use that
                    if slot_cat in self.daily_movies and movie_play_count[slot_cat] < 3:
                        video_info = self.daily_movies[slot_cat]
                        movie_play_count[slot_cat] += 1
                    else:
                        # Use round-robin for non-movie categories
                        video_info = self._get_next_video(slot_cat, category_videos)
                    
                    if video_info:
                        duration = float(video_info["duration"])
                        program.append({
                            "in": 0.0,
                            "out": float(duration),
                            "duration": float(duration),
                            "source": video_info["path"]
                        })
                        # Fixed slots reset the SPICA counter
                        items_since_last_spica = 0
                        last_was_spica = False
                        cursor += timedelta(seconds=duration)
                    
                    # Move to next fixed slot
                    fixed_idx += 1
                    continue
                
                # If next slot is coming soon (within next video), wait for it
                elif cursor < slot_time < cursor + timedelta(minutes=5):
                    # Jump cursor to slot time
                    cursor = slot_time
                    continue
            
            # Check if it's time to play daily movies (outside fixed slots)
            if self._should_play_movie(cursor):
                movie_played = False
                for cat, video_info in self.daily_movies.items():
                    if (cursor.hour != last_movie_hour[cat] and 
                        movie_play_count[cat] < 3):
                        
                        duration = float(video_info["duration"])
                        program.append({
                            "in": 0.0,
                            "out": float(duration),
                            "duration": float(duration),
                            "source": video_info["path"]
                        })
                        # Movies reset the SPICA counter
                        items_since_last_spica = 0
                        last_was_spica = False
                        last_movie_hour[cat] = cursor.hour
                        movie_play_count[cat] += 1
                        cursor += timedelta(seconds=duration)
                        movie_played = True
                        break
                
                if movie_played:
                    continue
            
            # Insert SPICA after every N regular content items (and not if last was spica)
            if items_since_last_spica >= self.spica_every_n and spica_path_info and not last_was_spica:
                duration = float(spica_path_info["duration"])
                program.append({
                    "in": 0.0,
                    "out": float(duration),
                    "duration": float(duration),
                    "source": spica_path_info["path"]
                })
                items_since_last_spica = 0
                last_was_spica = True
                cursor += timedelta(seconds=duration)
                continue
            
            # Fill with regular content from categories (round-robin)
            if fill_categories:
                cat = fill_categories[fill_idx % len(fill_categories)]
                fill_idx += 1
                video_info = self._get_next_video(cat, category_videos)
                
                if video_info:
                    duration = float(video_info["duration"])
                    program.append({
                        "in": 0.0,
                        "out": float(duration),
                        "duration": float(duration),
                        "source": video_info["path"]
                    })
                    items_since_last_spica += 1  # Only regular content counts toward SPICA
                    last_was_spica = False
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