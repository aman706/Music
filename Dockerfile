FROM python:3.10

RUN apt update && apt install -y ffmpeg nodejs npm git

WORKDIR /app

COPY . .

RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Debug: print pytgcalls types so we know exact import paths
RUN python -c "import pytgcalls.types.stream as s; print(dir(s))"

CMD ["python", "bot.py"]
