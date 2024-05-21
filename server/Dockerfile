FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

LABEL org.opencontainers.image.source=https://github.com/stenius/cforge
LABEL org.opencontainers.image.description="CForge Server"
LABEL org.opencontainers.image.licenses=BSD

# Run the server with Uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
