FROM python:3.13-slim

WORKDIR /app

COPY pyproject.toml ./
COPY kb_app/ kb_app/

RUN pip install --no-cache-dir -e .

ENV KB_DB_PATH=/data/kb.db

VOLUME /data

ENTRYPOINT ["kb"]
CMD ["--help"]
