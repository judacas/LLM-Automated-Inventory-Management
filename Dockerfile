FROM python:3.11-slim

WORKDIR /app

# --- SQL Server ODBC Driver 18 for pyodbc ---
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gnupg2 \
    apt-transport-https \
    ca-certificates \
    unixodbc \
    unixodbc-dev \
 && curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add - \
 && curl https://packages.microsoft.com/config/debian/12/prod.list > /etc/apt/sources.list.d/mssql-release.list \
 && apt-get update \
 && ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql18 \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*


# install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# copy source
COPY src ./src

# allow imports like: from inventory_service.service import ...
ENV PYTHONPATH=/app/src

EXPOSE 8000

CMD ["uvicorn", "tool_api.app:app", "--host", "0.0.0.0", "--port", "8000"]
