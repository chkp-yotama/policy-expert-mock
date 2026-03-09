FROM python:3.12-slim

WORKDIR /app

# Install uv for fast dependency resolution
RUN pip install --no-cache-dir uv

# Copy project definition first for layer caching
COPY pyproject.toml .

# Copy source
COPY main.py config.py state.py ./
COPY routers/ routers/
COPY scenarios/ scenarios/

# Install dependencies
RUN uv pip install --system -e .

EXPOSE 8080

ENV MOCK_HOST=0.0.0.0
ENV MOCK_PORT=8080

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080", "--log-level", "info"]
