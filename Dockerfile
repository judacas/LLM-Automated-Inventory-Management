FROM python:3.11-slim-bookworm

WORKDIR /app

# --- SQL Server ODBC Driver 18 for pyodbc ---
# --- SQL Server ODBC Driver 18 for pyodbc (Debian slim) ---
# --- SQL Server ODBC Driver 18 for pyodbc (Debian 12 / bookworm) ---
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        curl \
        gnupg \
        ca-certificates \
        unixodbc \
        unixodbc-dev; \
    curl -fsSL https://packages.microsoft.com/keys/microsoft.asc \
      | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg; \
    curl -fsSL https://packages.microsoft.com/config/debian/12/prod.list \
      | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/microsoft-prod.gpg] https://#g' \
      > /etc/apt/sources.list.d/microsoft-prod.list; \
    apt-get update; \
    ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql18; \
    apt-get clean; \
    rm -rf /var/lib/apt/lists/*

# install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# copy source
COPY src ./src

# allow imports like: from inventory_service.service import ...
ENV PYTHONPATH=/app/src

EXPOSE 8000

CMD ["uvicorn", "tool_api.app:app", "--host", "0.0.0.0", "--port", "8000"]
