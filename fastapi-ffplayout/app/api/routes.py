from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from app.services.scanner import scan_video_files
from app.services.playlist_generator import PlaylistGenerator
from app.core.config import settings
from datetime import datetime, timedelta
from pathlib import Path
import json

router = APIRouter()

@router.get("/")
async def root():
    """Root endpoint - API health check."""
    return {
        "service": "ffplayout-api",
        "status": "healthy",
        "version": "1.0.0",
        "created_by": "Zoran Janjic",
        "endpoints": {
            "docs": "/docs",
            "generate_playlist": "/generate-playlist?date=YYYY-MM-DD",
            "generate_week": "/generate-week?start_date=YYYY-MM-DD",
            "list_playlists": "/playlists",
            "get_videos": "/videos"
        }
    }

@router.get("/healthz")
async def health_check():
    """Health check endpoint for monitoring."""
    return {"status": "healthy", "service": "blagovesti-tv-api"}


@router.get("/videos")
async def get_video_files():
    try:
        video_files = scan_video_files(settings.video_directory)
        return {"video_directory": settings.video_directory, "video_files": video_files}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/generate-playlist")
async def create_playlist(date: str = None, return_file: bool = False):
    """
    Generate playlist for a specific date (YYYY-MM-DD), defaults to today.
    
    Args:
        date: Date in YYYY-MM-DD format
        return_file: If True, returns metadata. If False (default), returns the full playlist JSON
    """
    try:
        if date:
            date_obj = datetime.strptime(date, "%Y-%m-%d")
        else:
            date_obj = datetime.now()
        
        out_root = Path(settings.output_directory)
        year = f"{date_obj.year:04d}"
        month = f"{date_obj.month:02d}"
        dest_dir = out_root / year / month
        dest_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{date_obj.strftime('%Y-%m-%d')}.json"
        playlist_file = dest_dir / filename
        
        config = {
            "fixed_slots": settings.fixed_slots,
            "spica_every_n": settings.spica_every_n,
            "spica_file": settings.spica_file
        }
        generator = PlaylistGenerator(settings.video_directory, str(dest_dir), config)
        playlist = generator.generate_playlist(date=date_obj.strftime('%Y-%m-%d'))
        generator.save_playlist(playlist, str(playlist_file))
        
        # Return the actual playlist JSON by default
        if return_file:
            return {
                "message": f"Playlist generated successfully for {date_obj.strftime('%Y-%m-%d')}",
                "playlist_file": str(playlist_file),
                "download_url": f"/playlists/{year}/{month}/{filename}",
                "total_items": len(playlist["program"])
            }
        else:
            # Return the full playlist
            return playlist
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/generate-week")
async def create_week_playlists(start_date: str = None):
    """Generate playlists for 7 consecutive days starting from start_date (defaults to today)."""
    try:
        if start_date:
            date_obj = datetime.strptime(start_date, "%Y-%m-%d")
        else:
            date_obj = datetime.now()
        
        results = []
        
        for day_offset in range(7):
            target_date = date_obj + timedelta(days=day_offset)
            
            out_root = Path(settings.output_directory)
            year = f"{target_date.year:04d}"
            month = f"{target_date.month:02d}"
            dest_dir = out_root / year / month
            dest_dir.mkdir(parents=True, exist_ok=True)
            filename = f"{target_date.strftime('%Y-%m-%d')}.json"
            playlist_file = dest_dir / filename
            
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
                "download_url": f"/playlists/{year}/{month}/{filename}",
                "total_items": len(playlist["program"])
            })
        
        return {
            "message": f"Generated 7-day playlists from {date_obj.strftime('%Y-%m-%d')} to {(date_obj + timedelta(days=6)).strftime('%Y-%m-%d')}",
            "playlists": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/playlists/{year}/{month}/{filename}")
async def download_playlist(year: str, month: str, filename: str):
    """Download a generated playlist file."""
    file_path = Path(settings.output_directory) / year / month / filename
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"Playlist not found: {filename}")
    
    return FileResponse(
        path=str(file_path),
        media_type="application/json",
        filename=filename
    )

@router.get("/playlists")
async def list_playlists():
    """List all generated playlists."""
    playlists = []
    out_dir = Path(settings.output_directory)
    
    if out_dir.exists():
        for year_dir in sorted(out_dir.iterdir(), reverse=True):
            if year_dir.is_dir() and year_dir.name.isdigit():
                for month_dir in sorted(year_dir.iterdir(), reverse=True):
                    if month_dir.is_dir() and month_dir.name.isdigit():
                        for playlist in sorted(month_dir.glob("*.json"), reverse=True):
                            playlists.append({
                                "date": playlist.stem,
                                "download_url": f"/playlists/{year_dir.name}/{month_dir.name}/{playlist.name}",
                                "size_kb": round(playlist.stat().st_size / 1024, 2)
                            })
    
    return {"playlists": playlists, "count": len(playlists)}