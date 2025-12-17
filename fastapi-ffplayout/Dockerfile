FROM python:3.11-slim

# Install ffmpeg
RUN apt-get update && \
    apt-get install -y ffmpeg && \
    rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/

# Create mock_media folder structure
RUN mkdir -p /app/mock_media/deciji \
    /app/mock_media/dokumentarni \
    /app/mock_media/duhovne_pouke \
    /app/mock_media/molitve \
    /app/mock_media/muzika \
    /app/mock_media/psaltir \
    /app/mock_media/putopisi \
    /app/mock_media/serije \
    /app/mock_media/spica_folder

# Generate tiny mock videos (small resolution for faster build)
RUN cd /app/mock_media/spica_folder && \
    ffmpeg -f lavfi -i color=c=black:s=320x240:d=600 -f lavfi -i anullsrc -c:v libx264 -preset ultrafast -t 600 -c:a aac -ar 44100 -ac 2 SPICA_BlagovestiTV.mp4 && \
    ffmpeg -f lavfi -i color=c=black:s=320x240:d=600 -f lavfi -i anullsrc -c:v libx264 -preset ultrafast -t 600 -c:a aac -ar 44100 -ac 2 spica_folder_01.mp4 && \
    ffmpeg -f lavfi -i color=c=black:s=320x240:d=600 -f lavfi -i anullsrc -c:v libx264 -preset ultrafast -t 600 -c:a aac -ar 44100 -ac 2 spica_folder_02.mp4 && \
    ffmpeg -f lavfi -i color=c=black:s=320x240:d=600 -f lavfi -i anullsrc -c:v libx264 -preset ultrafast -t 600 -c:a aac -ar 44100 -ac 2 spica_folder_03.mp4 && \
    ffmpeg -f lavfi -i color=c=black:s=320x240:d=600 -f lavfi -i anullsrc -c:v libx264 -preset ultrafast -t 600 -c:a aac -ar 44100 -ac 2 spica_folder_04.mp4 && \
    ffmpeg -f lavfi -i color=c=black:s=320x240:d=600 -f lavfi -i anullsrc -c:v libx264 -preset ultrafast -t 600 -c:a aac -ar 44100 -ac 2 spica_folder_05.mp4

RUN cd /app/mock_media/deciji && \
    for i in 01 02 03 04 05; do \
    ffmpeg -f lavfi -i color=c=black:s=320x240:d=600 -f lavfi -i anullsrc -c:v libx264 -preset ultrafast -t 600 -c:a aac -ar 44100 -ac 2 deciji_$i.mp4; \
    done

RUN cd /app/mock_media/dokumentarni && \
    for i in 01 02 03 04 05; do \
    ffmpeg -f lavfi -i color=c=black:s=320x240:d=600 -f lavfi -i anullsrc -c:v libx264 -preset ultrafast -t 600 -c:a aac -ar 44100 -ac 2 dokumentarni_$i.mp4; \
    done

RUN cd /app/mock_media/duhovne_pouke && \
    for i in 01 02 03 04 05; do \
    ffmpeg -f lavfi -i color=c=black:s=320x240:d=600 -f lavfi -i anullsrc -c:v libx264 -preset ultrafast -t 600 -c:a aac -ar 44100 -ac 2 duhovne_pouke_$i.mp4; \
    done

RUN cd /app/mock_media/molitve && \
    for i in 01 02 03 04 05; do \
    ffmpeg -f lavfi -i color=c=black:s=320x240:d=600 -f lavfi -i anullsrc -c:v libx264 -preset ultrafast -t 600 -c:a aac -ar 44100 -ac 2 molitve_$i.mp4; \
    done

RUN cd /app/mock_media/muzika && \
    for i in 01 02 03 04 05; do \
    ffmpeg -f lavfi -i color=c=black:s=320x240:d=600 -f lavfi -i anullsrc -c:v libx264 -preset ultrafast -t 600 -c:a aac -ar 44100 -ac 2 muzika_$i.mp4; \
    done

RUN cd /app/mock_media/psaltir && \
    ffmpeg -f lavfi -i color=c=black:s=320x240:d=600 -f lavfi -i anullsrc -c:v libx264 -preset ultrafast -t 600 -c:a aac -ar 44100 -ac 2 Otac_Joil_katizma_10.mp4 && \
    ffmpeg -f lavfi -i color=c=black:s=320x240:d=600 -f lavfi -i anullsrc -c:v libx264 -preset ultrafast -t 600 -c:a aac -ar 44100 -ac 2 Otac_Joil_katizma_11.mp4 && \
    for i in 01 02 03 04 05; do \
    ffmpeg -f lavfi -i color=c=black:s=320x240:d=600 -f lavfi -i anullsrc -c:v libx264 -preset ultrafast -t 600 -c:a aac -ar 44100 -ac 2 psaltir_$i.mp4; \
    done

RUN cd /app/mock_media/putopisi && \
    for i in 01 02 03 04 05; do \
    ffmpeg -f lavfi -i color=c=black:s=320x240:d=600 -f lavfi -i anullsrc -c:v libx264 -preset ultrafast -t 600 -c:a aac -ar 44100 -ac 2 putopisi_$i.mp4; \
    done

RUN cd /app/mock_media/serije && \
    for i in 01 02 03 04 05; do \
    ffmpeg -f lavfi -i color=c=black:s=320x240:d=600 -f lavfi -i anullsrc -c:v libx264 -preset ultrafast -t 600 -c:a aac -ar 44100 -ac 2 serije_$i.mp4; \
    done

# Create playlists directory
RUN mkdir -p /app/playlists

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]