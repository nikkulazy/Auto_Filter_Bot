FROM python:3.12.2

# System dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    git \
    ffmpeg \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /DreamxBotz

# Copy requirements first (better caching)
COPY requirements.txt .

# Install Python packages
RUN pip install --no-cache-dir --upgrade pip --root-user-action=ignore && \
    pip install --no-cache-dir -r requirements.txt --root-user-action=ignore && \
    pip install --no-cache-dir yt-dlp --root-user-action=ignore

# Copy bot code
COPY . .

# Start bot
CMD ["python3", "bot.py"]
