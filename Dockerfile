FROM python:3.13-slim AS base

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libmagic1 \
    libreoffice \
    pandoc &&\
    rm -rf /var/lib/apt/lists/*

FROM base AS builder
ENV PATH="/usr/local/bin:$PATH"
ENV PYTHONPATH="/app:${PYTHONPATH}"
# Copy uv from the official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Enable bytecode compilation and copy mode
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
# First copy only dependency files for better layer caching
COPY pyproject.toml uv.lock ./
# Install project dependencies (production only - no dev dependencies)  
RUN uv export --no-dev --format requirements.txt -o requirements.txt && \
    uv pip install --system -r requirements.txt

# Copy specific files and directories instead of everything
COPY main.py ./
COPY src/ ./src/
COPY .env ./
COPY src/prompts ./src/prompts/

# Expose the port that the FastAPI app runs on
EXPOSE 5000
CMD ["python", "main.py"]
