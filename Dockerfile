FROM python:3.11-slim

WORKDIR /app

# install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# copy source
COPY src ./src

# allow imports like: from inventory_agent.service import ...
ENV PYTHONPATH=/app/src

EXPOSE 8000

CMD ["uvicorn", "tool_api.app:app", "--host", "0.0.0.0", "--port", "8000"]
