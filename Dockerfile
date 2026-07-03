# --- console build ---
FROM node:24-slim AS console
WORKDIR /build
COPY apps/console/package.json apps/console/package-lock.json ./
RUN npm ci
COPY apps/console/ ./
RUN npm run build

# --- runtime ---
FROM python:3.12-slim
WORKDIR /app
COPY apps/agent/pyproject.toml ./
COPY apps/agent/src ./src
RUN pip install --no-cache-dir -e .
COPY data ./data
COPY --from=console /build/dist ./src/agent_service/static
EXPOSE 8080
CMD ["uvicorn", "agent_service.main:app", "--host", "0.0.0.0", "--port", "8080"]
