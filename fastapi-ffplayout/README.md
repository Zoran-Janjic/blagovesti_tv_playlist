# FastAPI FFPlayout

This project is a FastAPI application designed to manage video playlists based on fixed schedules and categories. It scans a specified directory for available video files, generates playlists, and saves them as JSON files.

## Project Structure

```
fastapi-ffplayout
├── app
│   ├── main.py                # Entry point of the FastAPI application
│   ├── __init__.py            # Marks the directory as a Python package
│   ├── api
│   │   ├── routes.py          # Defines API routes for generating playlists and retrieving video files
│   │   └── dependencies.py     # Contains dependency functions for routes
│   ├── core
│   │   ├── config.py          # Holds configuration settings for the application
│   │   └── scheduler_config.py # Contains scheduling task configurations
│   ├── services
│   │   ├── scanner.py         # Functions for scanning the directory for video files
│   │   ├── playlist_generator.py # Logic for generating playlists
│   │   └── storage.py         # Handles saving the generated playlist as a JSON file
│   ├── models
│   │   └── schemas.py         # Defines data models and schemas for validation
│   └── utils
│       └── fileutils.py       # Utility functions for file operations
├── tests
│   ├── conftest.py            # Configures fixtures for the test suite
│   ├── test_scanner.py        # Unit tests for the scanner functionality
│   └── test_playlist_generator.py # Unit tests for the playlist generation logic
├── requirements.txt            # Lists dependencies required for the project
├── pyproject.toml             # Configuration file for the project
├── .env.example                # Example of environment variables for configuration
└── README.md                  # Documentation for the project
```

## Installation

1. Clone the repository:
   ```
   git clone <repository-url>
   cd fastapi-ffplayout
   ```

2. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Set up environment variables as needed, using the `.env.example` as a reference.

## Usage

To run the FastAPI application, execute the following command:
```
uvicorn app.main:app --reload
```

You can access the API documentation at `http://127.0.0.1:8000/docs`.

## Features

- Scans a specified directory for video files.
- Generates playlists based on fixed schedules and categories.
- Saves generated playlists as JSON files in a specified output directory.
- Provides API endpoints for generating playlists and retrieving available video files.

## Contributing

Contributions are welcome! Please open an issue or submit a pull request for any enhancements or bug fixes.