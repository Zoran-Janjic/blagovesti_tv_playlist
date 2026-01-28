"""Generate daily playlist matching FFPlayout expected format."""
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List
import json
import subprocess
import random
import re
import os

class PlaylistGenerator:
    def __init__(self, video_directory: str, output_directory: str, config: dict):
        self.video_dir = Path(video_directory)
        self.output_dir = Path(output_directory)
        self.fixed_slots = config.get("fixed_slots", {})
        self.spica_after_every_item = config.get("spica_after_every_item", True)
        self.spica_file = config.get("spica_file", "SPICA_BlagovestiTV.mp4")
        self.strict_fixed_slots = config.get("strict_fixed_slots", False)
        self.target_duration_hours = config.get("target_duration_hours", 23.0)
        self.recurrence_days = config.get("recurrence_exclusion_days", 10)
        self.filler_categories = config.get("filler_categories", {"15min": "15min", "30min": "30min"})
        
        # State tracking for playback history
        self.state = self._load_state()
        
        # Daily movie/series selection (will repeat 3 times)
        self.daily_movies = {}
        
    def _load_state(self) -> dict:
        """
        Load state from file.
        State structure:
        {
            "last_played": {
                "absolute_path_to_video": "2023-10-27T10:00:00"
            },
            ... old legacy index keys might remain but are ignored ...
        }
        """
        state_file = self.output_dir / ".playlist_state.json"
        if state_file.exists():
            try:
                with open(state_file, 'r', encoding='utf-8') as f:
                    state = json.load(f)
                    if "last_played" not in state:
                        state["last_played"] = {}
                    return state
            except Exception as e:
                print(f"Warning: Could not load state file: {e}")
                return {"last_played": {}}
        return {"last_played": {}}
    
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
            
    def _update_last_played(self, filepath: str, date_obj: datetime):
        """Update the last played timestamp for a file."""
        if "last_played" not in self.state:
            self.state["last_played"] = {}
        self.state["last_played"][filepath] = date_obj.isoformat()
    
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
        """Scan video directory and return dict of category -> list of {path, duration, mtime}."""
        videos = {}
        if not self.video_dir.exists():
            return videos
        
        for folder in sorted(self.video_dir.iterdir()):
            if folder.is_dir():
                folder_name = folder.name
                
                # Use mapped category instead of raw folder name
                # But we handle Spica separately generally? 
                # _map_folder_to_category handles spica -> spica.
                category = self._map_folder_to_category(folder_name)
                
                # Skip if category is None or unwanted? (Usually returns 'ostalo')
                
                files = []
                for f in sorted(folder.iterdir()):
                    if f.suffix.lower() in ('.mp4', '.mkv', '.mov', '.avi'):
                        abs_path = str(f.resolve())
                        files.append({
                            "path": abs_path, 
                            "duration": self._get_video_duration(abs_path),
                            "mtime": f.stat().st_mtime,
                            "filename": f.name
                        })
                if files:
                    if category not in videos:
                        videos[category] = []
                    videos[category].extend(files)
        return videos
    
    def _was_played_recently(self, filepath: str, date_obj: datetime) -> bool:
        """Check if video was played within recurrence_exclusion_days."""
        last_played_map = self.state.get("last_played", {})
        if filepath not in last_played_map:
            return False
            
        try:
            last_played_date = datetime.fromisoformat(last_played_map[filepath])
            # If stored as full datetime, we might want to compare dates or full delta
            # Let's compare just dates to be safe 10 'calendar days'
            delta_days = (date_obj.date() - last_played_date.date()).days
            return delta_days < self.recurrence_days
        except ValueError:
            return False

    def _get_next_video(self, category: str, videos: Dict[str, List[dict]], skip_daily: bool = True, target_date: datetime = None) -> dict:
        """
        Get next video from category using Priority Logic & Recurrence Rule.
        
        Priority Logic:
        1. Candidates = Files NOT played in the last X days.
        2. Sort Candidates by Least Recently Played (or Never Played).
        3. If all files were played recently (Hard constraint violation), fall back to Least Recently Played.
        """
        files = videos.get(category, [])
        if not files:
            return None
            
        current_date_obj = target_date if target_date else datetime.now()
        
        # Filter out currently selected daily movies if requested
        candidates = []
        if skip_daily and category in self.daily_movies:
            daily_path = self.daily_movies[category]["path"]
            candidates = [f for f in files if f["path"] != daily_path]
            if not candidates: candidates = files
        else:
            candidates = files

        # Filter by Recurrence Rule (10 days)
        valid_candidates = [f for f in candidates if not self._was_played_recently(f["path"], current_date_obj)]
        
        # If no valid candidates (all played recently), fallback to ALL candidates (soft failure)
        # We prefer to repeat something than show nothing.
        # But we still want to pick the "oldest" among them.
        selection_pool = valid_candidates if valid_candidates else candidates

        last_played_map = self.state.get("last_played", {})
        
        def sort_key(video):
            path = video["path"]
            if path not in last_played_map:
                # Never played. Priority 0.
                return (0, 0, video["mtime"])
            else:
                # Already played.
                timestamp_str = last_played_map[path]
                return (1, timestamp_str, video["mtime"])
        
        selection_pool.sort(key=sort_key)
        
        if not selection_pool:
            return None
            
        chosen = selection_pool[0]
        
        # Important: We do not update state here for 'peek' operations entirely, 
        # but the logic assumes if we pick it, we will use it.
        # For the generator, we update the in-memory state.
        self._update_last_played(chosen["path"], current_date_obj)
        
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
        """Extract series info from filename."""
        # Pattern 1: Name_SEZONA2_1_serija.ext
        pattern1 = r'(.+?)_SEZONA(\d+)_(\d+)_serija'
        match = re.search(pattern1, filename, re.IGNORECASE)
        if match:
            return {"name": match.group(1), "season": int(match.group(2)), "episode": int(match.group(3))}
        
        # Pattern 2: Name_S##E##.ext
        pattern2 = r'(.+?)_S(\d+)E(\d+)'
        match = re.search(pattern2, filename, re.IGNORECASE)
        if match:
            return {"name": match.group(1), "season": int(match.group(2)), "episode": int(match.group(3))}
        
        return None
    
    def _group_series_by_name(self, videos: List[dict]) -> Dict[str, List[dict]]:
        """Group series files by series name and sort by season/episode."""
        series_groups = {}
        for video in videos:
            filename = video["filename"]
            series_info = self._extract_series_info(filename)
            if series_info:
                name = series_info["name"]
                if name not in series_groups:
                    series_groups[name] = []
                video_with_info = video.copy()
                video_with_info["series_info"] = series_info
                series_groups[name].append(video_with_info)
        
        for name in series_groups:
            series_groups[name].sort(key=lambda x: (x["series_info"]["season"], x["series_info"]["episode"]))
        
        return series_groups
    
    def _select_daily_movies(self, videos: Dict[str, List[dict]], date_str: str) -> dict:
        """Select one movie/series per category for the day that will repeat 3 times."""
        daily_selection = {}
        movie_categories = ["serije", "dokumentarni", "deciji"]
        
        for category in movie_categories:
            files = videos.get(category, [])
            if not files:
                continue
            
            # Series Handling: Sequential
            if category == "serije":
                series_groups = self._group_series_by_name(files)
                if series_groups:
                    # Logic: Find last played episode for this category, pick next
                    last_ep_key = f"{category}_last_episode_path"
                    last_path = self.state.get(last_ep_key)
                    
                    selected_video = None
                    if last_path:
                        # Find next in sequence
                        for name, eps in series_groups.items():
                            for i, ep in enumerate(eps):
                                if ep["path"] == last_path:
                                    next_idx = (i + 1) % len(eps)
                                    selected_video = eps[next_idx]
                                    break
                            if selected_video: break
                    
                    if not selected_video:
                        # Start from first series, first episode
                        if series_groups:
                             selected_video = next(iter(series_groups.values()))[0]
                    
                    if selected_video:
                        daily_selection[category] = selected_video
                        self.state[last_ep_key] = selected_video["path"]
                        # Also update last_played for this video so it counts as played
                        self._update_last_played(selected_video["path"], datetime.now())
                        continue

            # Default / Non-Sequential Logic: Use Priority System
            
            selected_video = self._get_next_video(category, videos, skip_daily=False, target_date=datetime.strptime(date_str, "%Y-%m-%d"))
            if selected_video:
                daily_selection[category] = selected_video

        return daily_selection
    
    def _find_spica(self, videos: Dict[str, List[dict]]) -> dict:
        """Find spica file in any category."""
        for cat, files in videos.items():
            for f in files:
                # Flexible matching for spica file
                if self.spica_file.lower() in f["filename"].lower() or "spica" in f["filename"].lower():
                     if "spica" in cat.lower() or "spica" in f["path"].lower():
                        return f
        return None
    
    def _find_psaltir_files(self, videos: Dict[str, List[dict]]) -> dict:
        """
        Find Psaltir_01 and Psaltir_02 specifically.
        Returns dict: {"01": video_info, "02": video_info}
        """
        psaltir_files = {}
        for cat, files in videos.items():
            if "psaltir" in cat.lower():
                for f in files:
                    fname = f["filename"].lower()
                    if "psaltir_01" in fname:
                        psaltir_files["01"] = f
                    elif "psaltir_02" in fname:
                        psaltir_files["02"] = f
        return psaltir_files

    def _map_folder_to_category(self, folder_name: str) -> str:
        """Map folder name to logical category."""
        folder = folder_name.lower()
        if "psaltir" in folder: return "psaltir"
        if "molitv" in folder: return "molitve"
        if "duhov" in folder or "pouke" in folder: return "duhovne_pouke"
        if "decij" in folder: return "deciji"
        if "serij" in folder or "film" in folder: return "serije"
        if "dokument" in folder: return "dokumentarni"
        if "putopis" in folder: return "putopisi"
        if "muzik" in folder: return "muzika"
        return "ostalo"
    
    def _should_play_movie(self, current_time: datetime) -> bool:
        """Determine if it's time to play daily movies."""
        h = current_time.hour
        # Noon, Late Afternoon, Evening slots
        return (12 <= h < 14) or (16 <= h < 18) or (20 <= h < 22)

    def save_playlist(self, playlist: dict, filepath: str):
        Path(filepath).write_text(json.dumps(playlist, indent=2, ensure_ascii=False))
        
    def generate_playlist(self, date: str = None) -> dict:
        """Generate playlist with Psaltir fixed slots and Priority-based rotation."""
        if date:
            date_obj = datetime.strptime(date, "%Y-%m-%d")
        else:
            date_obj = datetime.now()
        
        date_str = date_obj.strftime("%Y-%m-%d")
        videos = self._scan_videos()
        spica_info = self._find_spica(videos)
        psaltir_files = self._find_psaltir_files(videos)
        
        # Select daily movies
        self.daily_movies = self._select_daily_movies(videos, date_str)
        movie_play_count = {cat: 0 for cat in self.daily_movies.keys()}
        
        # Build category map (excluding Spica and Psaltir which are handled separately)
        category_videos = {}
        for folder, files in videos.items():
            if self._is_spica_category(folder): continue
            
            logical_cat = self._map_folder_to_category(folder)
            
            # Exclude Psaltir from general rotation pool
            if logical_cat == "psaltir":
                continue
                
            if logical_cat not in category_videos:
                category_videos[logical_cat] = []
            category_videos[logical_cat].extend(files)
            
        day_start = datetime.combine(date_obj.date(), datetime.strptime("06:00:00", "%H:%M:%S").time())
        day_end = day_start + timedelta(hours=self.target_duration_hours)
        program = []
        cursor = day_start
        
        # --- 1. PREPEND PSALTIR 01 (Morning) ---
        if "01" in psaltir_files:
            p_file = psaltir_files["01"]
            dur = float(p_file["duration"])
            program.append({
                "in": 0.0, "out": dur, "duration": dur, "source": p_file["path"]
            })
            cursor += timedelta(seconds=dur)
            # Add Spica after Psaltir? "SPICA se pojavljuje nakon SVAKOG videa"
            if self.spica_after_every_item and spica_info:
                s_dur = float(spica_info["duration"])
                program.append({
                    "in": 0.0, "out": s_dur, "duration": s_dur, "source": spica_info["path"]
                })
                cursor += timedelta(seconds=s_dur)

        # Parse fixed slots
        # Note: We removed Psaltir from fixed_slots processing in the new logic if we hardcode it.
        # But 'fixed_slots' config might still have it. We should probably ignore Psaltir keys in fixed_slots.
        
        fixed_schedule = []
        for time_str, cat in self.fixed_slots.items():
            if cat == "psaltir": continue # Handled manually
            
            try:
                slot_time = datetime.combine(date_obj.date(), datetime.strptime(time_str, "%H:%M:%S").time())
                if slot_time < day_start:
                    slot_time += timedelta(days=1)
                fixed_schedule.append((slot_time, cat))
            except:
                continue
        fixed_schedule.sort(key=lambda x: x[0])
        
        fill_categories = [c for c in sorted(category_videos.keys()) 
                           if c not in ["serije", "dokumentarni", "deciji"]]
        fill_idx = 0
        fixed_idx = 0
        
        # Track movie hours to avoid repeating same movie in same hour block
        last_movie_hour = {cat: -1 for cat in self.daily_movies.keys()}
        
        psaltir_02_played = False
        
        # Generate Content
        while cursor < day_end:
            
            # --- Check for Psaltir 02 (Midnight / End of day) ---
            # If we are crossing midnight or it's late, insert Psaltir 02 once.
            # Logic: "oko ponoći stavi Psaltir_02.mp4"
            # If cursor is near 00:00 next day (e.g. > 23:00 or local time check)
            # Actually, let's say if cursor.hour >= 23 or cursor.day > date_obj.day
            if not psaltir_02_played and "02" in psaltir_files:
                # Check if close to midnight or past it
                # day_start is 06:00. day_end is ~05:00 next day.
                # Midnight is 18 hours after start
                time_since_start = (cursor - day_start).total_seconds()
                if time_since_start > 17 * 3600: # After 23:00 roughly
                     p_file = psaltir_files["02"]
                     dur = float(p_file["duration"])
                     program.append({
                        "in": 0.0, "out": dur, "duration": dur, "source": p_file["path"]
                     })
                     cursor += timedelta(seconds=dur)
                     psaltir_02_played = True
                     
                     if self.spica_after_every_item and spica_info:
                        s_dur = float(spica_info["duration"])
                        program.append({
                            "in": 0.0, "out": s_dur, "duration": s_dur, "source": spica_info["path"]
                        })
                        cursor += timedelta(seconds=s_dur)
                     continue

            # Fixed Slots (Strict Mode)
            if self.strict_fixed_slots and fixed_idx < len(fixed_schedule):
                slot_time, slot_cat = fixed_schedule[fixed_idx]
                if cursor >= slot_time:
                    # Play Slot
                    vid = None
                    if slot_cat in self.daily_movies and movie_play_count.get(slot_cat, 0) < 3:
                        vid = self.daily_movies[slot_cat]
                        movie_play_count[slot_cat] += 1
                    else:
                        vid = self._get_next_video(slot_cat, category_videos, target_date=date_obj)
                    
                    if vid:
                        d = float(vid["duration"])
                        program.append({"in": 0.0, "out": d, "duration": d, "source": vid["path"]})
                        cursor += timedelta(seconds=d)
                        if self.spica_after_every_item and spica_info:
                             sd = float(spica_info["duration"])
                             program.append({"in": 0.0, "out": sd, "duration": sd, "source": spica_info["path"]})
                             cursor += timedelta(seconds=sd)
                    fixed_idx += 1
                    continue
                elif cursor < slot_time < cursor + timedelta(minutes=15):
                     cursor = slot_time
                     continue

            # Daily Movies Logic
            if self._should_play_movie(cursor):
                movie_played = False
                for cat, vid in self.daily_movies.items():
                    if cursor.hour != last_movie_hour[cat] and movie_play_count[cat] < 3:
                        d = float(vid["duration"])
                        program.append({"in": 0.0, "out": d, "duration": d, "source": vid["path"]})
                        cursor += timedelta(seconds=d)
                        last_movie_hour[cat] = cursor.hour
                        movie_play_count[cat] += 1
                        
                        if self.spica_after_every_item and spica_info:
                             sd = float(spica_info["duration"])
                             program.append({"in": 0.0, "out": sd, "duration": sd, "source": spica_info["path"]})
                             cursor += timedelta(seconds=sd)
                        
                        movie_played = True
                        break
                if movie_played:
                    continue

            # Fill Content
            if fill_categories:
                cat = fill_categories[fill_idx % len(fill_categories)]
                fill_idx += 1
                vid = self._get_next_video(cat, category_videos, target_date=date_obj)
                if vid:
                    d = float(vid["duration"])
                    program.append({"in": 0.0, "out": d, "duration": d, "source": vid["path"]})
                    cursor += timedelta(seconds=d)
                    if self.spica_after_every_item and spica_info:
                         sd = float(spica_info["duration"])
                         program.append({"in": 0.0, "out": sd, "duration": sd, "source": spica_info["path"]})
                         cursor += timedelta(seconds=sd)
                else:
                    cursor += timedelta(minutes=15)
            else:
                break
        
        self._save_state()
        return {
            "channel": "Channel 1",
            "date": date_str,
            "program": program
        }

    def _get_filler_video(self, gap_duration: float, videos: Dict[str, List[dict]], date_obj: datetime) -> dict:
        """Find a suitable filler video based on gap size."""
        # Config: filler_categories = {"15min": "15min_folder", "30min": "30min_folder"}
        
        # Thresholds (logic from user: /15min or /30min depending on gap)
        # Let's say:
        # Gap 10-20 min -> try 15min folder
        # Gap > 20 min -> try 30min folder
        # Gap < 10 min -> too small? return None (no filler)
        
        target_cat = None
        if 600 <= gap_duration <= 1300: # 10min to ~21min
            target_cat = self.filler_categories.get("15min")
        elif gap_duration > 1300: # > 21min
            target_cat = self.filler_categories.get("30min")
            
        if target_cat:
            # Try to get video from this filler category
            # We treat fillers as normal videos (recurrence applies? maybe not strictly needed for fillers but good practice)
            # Maybe relax recurrence for fillers? Let's use standard logic for now.
            return self._get_next_video(target_cat, videos, target_date=date_obj)
            
        return None

    def generate_playlist_from_template(self, template_path: str, date: str = None) -> dict:
        """
        Generate playlist based on Day_0 template structure.
        """
        if date:
            date_obj = datetime.strptime(date, "%Y-%m-%d")
        else:
            date_obj = datetime.now()
        
        date_str = date_obj.strftime("%Y-%m-%d")
        videos = self._scan_videos()
        spica_info = self._find_spica(videos)
        
        # Load Template
        try:
            with open(template_path, 'r', encoding='utf-8') as f:
                template_data = json.load(f)
        except Exception as e:
            print(f"Error loading template: {e}")
            return self.generate_playlist(date) # Fallback to old logic
            
        template_program = template_data.get("program", [])
        new_program = []
        
        # Pre-select daily movies just in case template relies on Fixed Slots or specific logic?
        # Actually, template replaces the generating loop. 
        # But we still need to know WHICH file to pick for a category slot.
        # How do we know the category of a slot in Day_0? 
        # We must INFER it from the source path in the template item.
        
        # Also need to respect Fixed Slots if they OVERRIDE the template? 
        # User said: "Day_0 kao Šablon: Generator će jednostavno 'prepisati' strukturu tvoje ručno napravljene playliste"
        # AND "Fiksni Termini: Glavne emisije i filmovi ostaju u svojim terminima"
        # This implies the Template IS the schedule structure.
        
        current_time = datetime.combine(date_obj.date(), datetime.strptime("06:00:00", "%H:%M:%S").time())
        # We might need to track strict time if we want to ensure fixed slots align?
        # Or does the template already contain the fixed slots? 
        # "Day_0... prepisati strukturu... Fiksni termini ostaju".
        # This likely means the template HAS the fixed slots in correct order.
        # We just replace the CONTENT of non-fixed items?
        
        for item in template_program:
            original_source = item.get("source", "")
            duration_slot = item.get("duration", 0)
            
            # Identify Category from Source Path
            # e.g. /var/lib/ffplayout/tv-media/Serije/Grigorije... -> "serije"
            # We can try to map the folder name.
            folder_name = os.path.basename(os.path.dirname(original_source))
            category = self._map_folder_to_category(folder_name)
            
            # Special Handling: Spica
            if self._is_spica_category(folder_name) or "SPICA" in os.path.basename(original_source):
                # Just add Spica
                if spica_info:
                     new_program.append({
                        "in": 0.0, 
                        "out": float(spica_info["duration"]), 
                        "duration": float(spica_info["duration"]), 
                        "source": spica_info["path"]
                    })
                continue
            
            # Special Handling: Psaltir (Keep Day_0 logic or use sequential?)
            # "Day_0 prepisati strukturu" -> implies if Day_0 has Psaltir_01, we put Psaltir_01?
            # Or do we rotate Psaltir? 
            # Psaltir logic in old code: 01 in morning, 02 at night?
            # User didn't explicitly say "Rotate Psaltir". But usually Psaltir is sequential.
            # Let's assume for mapped categories, we ROTATE using new logic.
            
            # Content Selection
            # Check if it's a "Fixed Item" that should remain exactly same? 
            # Maybe Psaltir 01/02 are fixed items?
            # If category is 'psaltir', maybe we find the specific one?
            
            selected_vid = self._get_next_video(category, videos, target_date=date_obj)
            
            if selected_vid:
                d = float(selected_vid["duration"])
                new_program.append({
                    "in": 0.0, "out": d, "duration": d, "source": selected_vid["path"]
                })
                
                # Check for Gap
                gap = duration_slot - d
                # Tolerance? If gap is large positive, we need filler.
                # If gap is negative (new video is longer), that's usually OK (schedule shifts), 
                # UNLESS fixed slots must be hit.
                
                if gap > 0:
                    filler = self._get_filler_video(gap, videos, date_obj)
                    if filler:
                         fd = float(filler["duration"])
                         new_program.append({
                            "in": 0.0, "out": fd, "duration": fd, "source": filler["path"]
                        })
                        
            else:
                # If no video found, keep original? Or skip?
                # Maybe keep original as fallback to avoid empty slot?
                # But original path might be from 10 days ago (if Day_0 is old).
                pass

        self._save_state()
        return {
            "channel": template_data.get("channel", "Channel 1"),
            "date": date_str,
            "program": new_program
        }