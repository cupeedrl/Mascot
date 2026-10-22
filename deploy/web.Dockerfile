# Builds the React app and serves it with Caddy, which also proxies /api to FastAPI.
# Build context is the repository root (see docker-compose.prod.yml).

FROM node:22-alpine AS build
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
# No VITE_API_BASE_URL: the client falls back to the same-origin /api/v1.
RUN npm run build

FROM caddy:2-alpine
COPY deploy/Caddyfile /etc/caddy/Caddyfile
COPY --from=build /app/dist /srv
