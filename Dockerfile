# ---------------------------------------------------------
# Stage 1: Build the React frontend
# ---------------------------------------------------------

FROM node:20-alpine AS frontend-builder

WORKDIR /app/frontend

# Install frontend dependencies first so Docker can cache them
COPY frontend/package.json frontend/package-lock.json ./

RUN npm ci

# Copy the React source code
COPY frontend/ ./

# Build the production frontend into frontend/dist
RUN npm run build


# ---------------------------------------------------------
# Stage 2: Build the FastAPI runtime image
# ---------------------------------------------------------

FROM python:3.11-slim AS runtime

# Keep Python logs visible immediately and avoid .pyc files
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000

WORKDIR /app

# Install Python dependencies
COPY requirements.txt ./

RUN python -m pip install --upgrade pip \
    && python -m pip install -r requirements.txt

# Copy the backend application
COPY src/ ./src/

# Copy the compiled React frontend from the Node build stage
COPY --from=frontend-builder \
    /app/frontend/dist \
    ./frontend/dist

# Document the default application port
EXPOSE 8000

# Render supplies PORT automatically in production.
# Locally, it falls back to 8000.
CMD ["sh", "-c", "python -m uvicorn src.api:app --host 0.0.0.0 --port ${PORT:-8000}"]