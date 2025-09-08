# An example using multi-stage image builds to create a final image without uv.

# First, build the application in the `/app` directory.
# See `Dockerfile` for details.
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

# Disable Python downloads, because we want to use the system interpreter
# across both images. If using a managed Python version, it needs to be
# copied from the build image into the final image; see `standalone.Dockerfile`
# for an example.
ENV UV_PYTHON_DOWNLOADS=0

WORKDIR /app
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-dev
COPY . /app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev


# Then, use a final image without uv
FROM python:3.12-slim-bookworm
# It is important to use the image that matches the builder, as the path to the
# Python executable must be the same, e.g., using `python:3.11-slim-bookworm`
# will fail.

# Create a non-privileged user to run the application
RUN groupadd --gid 1001 app && \
    useradd --uid 1001 --gid 1001 --create-home app
# Copy the application from the builder
COPY --from=builder --chown=app:app /app /app

# Copy and set up the enhanced entrypoint script
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Set the working directory
WORKDIR /app

# Place executables in the environment at the front of the path
ENV PATH="/app/.venv/bin:$PATH"

# Set default environment variables for common parameters
ENV MODEL_TYPE="rest"
ENV MODEL_NAME="RestGenerator"
ENV CONFIG_FILE="ifd_bot_config.yaml"
ENV PROBES="lmrc"
ENV REPORT_PREFIX="chatbot-security"

ENTRYPOINT ["/app/entrypoint.sh"]
