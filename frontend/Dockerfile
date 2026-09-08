# ─────────────────────────────────────────────────────────────────────────────
# Cortex Gateway — Frontend Dockerfile
# ─────────────────────────────────────────────────────────────────────────────

FROM node:22-slim AS builder

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci --prefer-offline

COPY . .

ARG VITE_API_URL=http://localhost:8000
ENV VITE_API_URL=$VITE_API_URL

RUN npm run build

# ─────────────────────────────────────────────────────────────────────────────

FROM nginx:1.27-alpine AS runtime

# Copy built assets
COPY --from=builder /app/dist /usr/share/nginx/html

# nginx config for SPA routing (react-router)
RUN printf 'server {\n\
    listen 5173;\n\
    root /usr/share/nginx/html;\n\
    index index.html;\n\
    location / {\n\
        try_files $uri $uri/ /index.html;\n\
    }\n\
    gzip on;\n\
    gzip_types text/plain text/css application/json application/javascript;\n\
}\n' > /etc/nginx/conf.d/default.conf

EXPOSE 5173

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -q --spider http://localhost:5173 || exit 1

CMD ["nginx", "-g", "daemon off;"]
