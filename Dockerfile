FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Alembic config and migrations
COPY alembic.ini /alembic.ini
COPY alembic/ /alembic/

# Application source
COPY ./app /app

# Entrypoint
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Render injects $PORT (default 10000); local Docker uses 8000.
# Both are handled by entrypoint.sh — no fixed EXPOSE needed,
# but we document the local default for clarity.
EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
