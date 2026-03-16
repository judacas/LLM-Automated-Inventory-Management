FROM python:3.11-slim

WORKDIR /app

# install system dependencies needed by pyodbc
RUN apt-get update && apt-get install -y \
    unixodbc \
    unixodbc-dev \
    && rm -rf /var/lib/apt/lists/*

# install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# copy source
COPY src ./src

# allow imports like: from mcp.tools.registry import registry
ENV PYTHONPATH=/app/src

EXPOSE 8000

CMD ["uvicorn", "mcp.main:app", "--host", "0.0.0.0", "--port", "8000"]