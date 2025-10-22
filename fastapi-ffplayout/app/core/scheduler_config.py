from pydantic import BaseModel
from typing import List, Dict
from datetime import time

class Schedule(BaseModel):
    start_time: time
    end_time: time
    category: str

class SchedulerConfig(BaseModel):
    schedules: List[Schedule]
    output_directory: str
    video_directory: str

def get_scheduler_config() -> SchedulerConfig:
    return SchedulerConfig(
        schedules=[
            Schedule(start_time=time(9, 0), end_time=time(12, 0), category="Morning Show"),
            Schedule(start_time=time(12, 0), end_time=time(15, 0), category="Afternoon Show"),
            Schedule(start_time=time(15, 0), end_time=time(18, 0), category="Evening Show"),
            Schedule(start_time=time(18, 0), end_time=time(21, 0), category="Prime Time"),
        ],
        output_directory="/var/lib/ffplayout/playlists/",
        video_directory="/var/lib/ffplayout/tv-media/emisije/"
    )