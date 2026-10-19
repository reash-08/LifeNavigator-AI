# Multi-stage production Dockerfile for LifeNavigator-AI Frontend
# Stage 1: Build static assets with Node.js
FROM node:20-alpine AS builder

WORKDIR /app

# Install dependencies using package-lock for reproducible builds
COPY package.json package-lock.json ./
RUN npm ci

# Copy source code and build
COPY . .

# Optional build-time API base URL (defaults to empty string for relative proxying)
ARG VITE_API_URL=""
ENV VITE_API_URL=${VITE_API_URL}

RUN npm run build

# Stage 2: Serve static files with lightweight, secure Nginx
FROM nginx:1.27-alpine AS production

# Clear default nginx assets
RUN rm -rf /usr/share/nginx/html/*

# Copy built distribution from builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy production Nginx reverse-proxy configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

# Healthcheck testing Nginx static server readiness
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD wget -q --spider http://127.0.0.1/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
