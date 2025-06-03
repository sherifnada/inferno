FROM python:3.10-slim
WORKDIR /app
COPY pyproject.toml .
COPY uv.lock .
RUN pip install uv && uv sync
COPY main.py .
CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "80"]