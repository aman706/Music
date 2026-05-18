FROM python:3.10

RUN apt update && apt install -y ffmpeg nodejs npm git

WORKDIR /app

COPY . .

RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Install yt-dlp's JS challenge solver
RUN pip install yt-dlp[default]
RUN python -m yt_dlp_plugins.extractor || true
RUN yt-dlp --install-compat-options || true

CMD ["python", "bot.py"]
