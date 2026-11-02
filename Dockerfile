FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# catálogo de sequências (sequencias_db.py): o diretório é um volume para o
# catálogo sobreviver a `docker rm`. Sem `-v`, o banco vive só no container.
RUN mkdir -p /app/dados
VOLUME ["/app/dados"]

EXPOSE 8080

CMD ["gunicorn", "--bind", "0.0.0.0:8080", "main:app"]
