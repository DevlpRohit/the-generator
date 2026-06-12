FROM python:3.11-slim

WORKDIR /app

# System deps: ffmpeg for video processing, gcc for some Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Tell moviepy/imageio to use the system ffmpeg instead of downloading its own
ENV FFMPEG_BINARY=/usr/bin/ffmpeg

# Install Python dependencies first (cached layer unless requirements change)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY . .

# Create runtime directories (projects/ is generated at runtime)
RUN mkdir -p projects voice_profiles

EXPOSE 7860

CMD ["python", "app.py"]
