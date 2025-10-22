from pathlib import Path
import json

def save_playlist(playlist, output_directory, filename='playlist.json'):
    output_path = Path(output_directory) / filename
    with open(output_path, 'w') as json_file:
        json.dump(playlist, json_file)