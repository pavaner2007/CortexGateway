# ─────────────────────────────────────────────────────────────────────────────
# Cortex Gateway — Frontend Dockerfile (Production)
#
# Stage 1: Node — build the React/Vite application
# Stage 2: nginx:alpine — serve compiled static files
#
# Phase 10: Non-root nginx on port 8080, security headers, proper SPA config,
#           gzip for JSON and JS responses.
#
# Build args:
#   VITE_API_URL — base URL for API calls from the browser.
#                  Leave empty ("") to use relative paths (recommended behind NGINX proxy).
# ─────────────────────────────────────────────────────────────────────────────

FROM node:22-slim AS builder

WORKDIR /app

# Install dependencies first (layer-cached when package files unchanged)
COPY package.json package-lock.json* ./
RUN npm ci --prefer-offline

COPY . .

ARG VITE_API_URL=""
ENV VITE_API_URL=$VITE_API_URL

# TypeScript compile + Vite build
RUN npm run build

# ─────────────────────────────────────────────────────────────────────────────

FROM nginx:1.27-alpine AS runtime

# Remove default NGINX config
RUN rm /etc/nginx/conf.d/default.conf

# Copy SPA nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy compiled frontend assets
COPY --from=builder /app/dist /usr/share/nginx/html

# Non-root setup: nginx worker runs as nginx user (alpine default).
# Main process listens on 8080 (non-privileged port).
# Required writable dirs for nginx temp files:
RUN mkdir -p /var/cache/nginx /var/run /var/log/nginx \
    && chown -R nginx:nginx /var/cache/nginx /var/run /var/log/nginx /usr/share/nginx/html \
    && chmod -R 755 /usr/share/nginx/html

USER nginx

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -q --spider http://localhost:8080 || exit 1

CMD ["nginx", "-g", "daemon off;"]
