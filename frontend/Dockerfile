# syntax=docker/dockerfile:1

# ---- Build stage -----------------------------------------------------------
FROM node:20-alpine AS build
WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci || npm install

COPY . .

# VITE_API_URL is baked into the static bundle at build time. Leave it empty
# (default) so the built app calls same-origin relative paths like
# "/api/alerts"; nginx below proxies "/api" to the gateway container so no
# CORS configuration is needed in production.
ARG VITE_API_URL=
ENV VITE_API_URL=${VITE_API_URL}

RUN npm run build

# ---- Runtime stage ----------------------------------------------------------
FROM nginx:1.27-alpine AS runtime

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/templates/default.conf.template

# GATEWAY_UPSTREAM is resolved by nginx's built-in envsubst templating at
# container start (see /etc/nginx/templates), so it can be overridden per
# environment (docker-compose, k8s) without rebuilding the image.
ENV GATEWAY_UPSTREAM=http://frontend_gateway:8080

EXPOSE 80
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s \
  CMD wget -qO- http://127.0.0.1/ >/dev/null 2>&1 || exit 1

CMD ["nginx", "-g", "daemon off;"]
