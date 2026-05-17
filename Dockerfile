FROM python:3.10

RUN apt update && apt install -y ffmpeg nodejs npm git

WORKDIR /app

COPY . .

RUN pip install --upgrade pip

RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "bot.py"]
