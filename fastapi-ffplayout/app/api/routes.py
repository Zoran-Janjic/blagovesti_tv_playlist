from fastapi import APIRouter, HTTPException
from app.services.scanner import scan_video_files
from app.services.playlist_generator import PlaylistGenerator
from app.core.config import settings
from datetime import datetime, timedelta
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
            "total_items": len(playlist["program"])
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/generate-week")
async def create_week_playlists(start_date: str = None):
    """Generate playlists for 7 consecutive days starting from start_date (defaults to today)."""
    try:
        # parse start date or use today
        if start_date:
            date_obj = datetime.strptime(start_date, "%Y-%m-%d")
        else:
            date_obj = datetime.now()
        
        results = []
        
        for day_offset in range(7):
            target_date = date_obj + timedelta(days=day_offset)
            
            # create output path
            out_root = Path(settings.output_directory)
            year = f"{target_date.year:04d}"
            month = f"{target_date.month:02d}"
            dest_dir = out_root / year / month
            dest_dir.mkdir(parents=True, exist_ok=True)
            filename = f"{target_date.strftime('%Y-%m-%d')}.json"
            playlist_file = dest_dir / filename
            
            # generate playlist
            config = {
                "fixed_slots": settings.fixed_slots,
                "spica_every_n": settings.spica_every_n,
                "spica_file": settings.spica_file
            }
            generator = PlaylistGenerator(settings.video_directory, str(dest_dir), config)
            playlist = generator.generate_playlist(date=target_date.strftime('%Y-%m-%d'))
            generator.save_playlist(playlist, str(playlist_file))
            
            results.append({
                "date": target_date.strftime('%Y-%m-%d'),
                "playlist_file": str(playlist_file),
                "total_items": len(playlist["program"])
            })
        
        return {
            "message": f"Generated 7-day playlists from {date_obj.strftime('%Y-%m-%d')} to {(date_obj + timedelta(days=6)).strftime('%Y-%m-%d')}",
            "playlists": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))