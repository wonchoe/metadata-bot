FROM python:3.12-slim

# ExifTool — the core tool (Perl-based, handles 200+ EXIF tags, photos & video)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libimage-exiftool-perl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p data/uploads data/outputs

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
