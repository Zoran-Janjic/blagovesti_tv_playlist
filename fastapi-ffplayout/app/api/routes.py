from fastapi import APIRouter, HTTPException
from app.services.scanner import scan_video_files
from app.services.playlist_generator import PlaylistGenerator
from app.core.config import settings
from datetime import datetime
from pathlib import Path

router = APIRouter()

@router.get("/videos")
async def get_video_files():
    try:
        video_files = scan_video_files(settings.video_directory)
        return {"video_directory": settings.video_directory, "video_files": video_files}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/generate-playlist")
async def create_playlist(date: str = None):
    """Generate playlist for a specific date (YYYY-MM-DD), defaults to today."""
    try:
        # parse date or use today
        if date:
            date_obj = datetime.strptime(date, "%Y-%m-%d")
        else:
            date_obj = datetime.now()
        
        # create output path: playlists/YYYY/MM/YYYY-MM-DD.json
        out_root = Path(settings.output_directory)
        year = f"{date_obj.year:04d}"
        month = f"{date_obj.month:02d}"
        dest_dir = out_root / year / month
        dest_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{date_obj.strftime('%Y-%m-%d')}.json"
        playlist_file = dest_dir / filename
        
        # generate playlist with proper config
        config = {
            "fixed_slots": settings.fixed_slots,
            "spica_every_n": settings.spica_every_n,
            "spica_file": settings.spica_file
        }
        generator = PlaylistGenerator(settings.video_directory, str(dest_dir), config)
        playlist = generator.generate_playlist(date=date_obj.strftime('%Y-%m-%d'))
        generator.save_playlist(playlist, str(playlist_file))
        
        return {
            "message": f"Playlist generated successfully for {date_obj.strftime('%Y-%m-%d')}",
            "playlist_file": str(playlist_file),
            "total_items": len(playlist["program"])  # changed from playlist["items"] to playlist["program"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

        Correct format matching FFPlayout structure (channel, date, program[] with in, out, duration, source)
✅ Spica insertion every 3 regular items (deciji → dokumentarni → duhovne_pouke → spica → molitve → muzika → psaltir → spica)
✅ Round-robin category rotation (deciji, dokumentarni, duhovne_pouke, molitve, muzika, psaltir, putopisi, serije)
✅ Sequential file playback within categories (deciji_01 → deciji_02 → deciji_03, then wraps back to deciji_01)
✅ Absolute paths from mock_media
✅ State tracking working (.playlist_state.json tracks last played index per category)
✅ 60 items generated (3 cycles through all categories with spica breaks)
