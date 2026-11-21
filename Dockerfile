# Serwer wyszukiwania źródeł EU4 (bez modelu językowego), np. dla agenta ElevenLabs.
FROM python:3.12-slim
WORKDIR /app
COPY . .
RUN python eu4.py setup --no-model && .eu4/.venv/bin/pip install --no-cache-dir -r sources/eu4/mechanics/requirements-server.txt && rm -rf /root/.cache/pip
ENV EU4_RAG_DB=/app/.eu4/shared/knowledge.sqlite3
EXPOSE 8000
# SEARCH_API_TOKEN ustaw w sekretach hostingu, nie w obrazie.
CMD ["/app/.eu4/.venv/bin/python", "-m", "uvicorn", "--app-dir", "sources/eu4/mechanics", "--factory", "server:build_app", "--host", "0.0.0.0", "--port", "8000"]
