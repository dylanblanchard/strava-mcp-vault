FROM python:3.13-slim AS builder

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.13-slim

WORKDIR /app

COPY --from=builder /install /usr/local

COPY . .

RUN mkdir -p /app/data

EXPOSE 8080

CMD ["python", "server.py"]
