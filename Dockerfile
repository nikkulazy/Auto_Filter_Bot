FROM nikolaik/python-nodejs:python3.10-nodejs19

RUN sed -i 's|http://deb.debian.org/debian|http://archive.debian.org/debian|g' /etc/apt/sources.list && \
    sed -i '/security.debian.org/d' /etc/apt/sources.list && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
    ffmpeg \
    aria2 \
    ca-certificates \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && update-ca-certificates

COPY . /app/
WORKDIR /app/


RUN python -m pip install --no-cache-dir --upgrade pip
RUN pip3 install --no-cache-dir --upgrade --requirement requirements.txt
RUN pip3 install --no-cache-dir yt-dlp certifi

CMD ["python3", "bot.py"]
