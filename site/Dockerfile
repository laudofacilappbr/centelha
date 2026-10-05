# syntax=docker/dockerfile:1

# ---------- build ----------
FROM node:22-alpine AS build
WORKDIR /app

# Variáveis de build (ficam embutidas no HTML/JS estático).
ARG PUBLIC_API_URL=""
ARG SITE_URL="https://centelha.com.br"
ARG PUBLIC_PLAUSIBLE_DOMAIN=""
ARG CATALOGO_API_URL=""
ARG CATALOGO_OBRIGATORIO=""
ARG AUDIO_URL=""
ENV PUBLIC_API_URL=$PUBLIC_API_URL \
    SITE_URL=$SITE_URL \
    PUBLIC_PLAUSIBLE_DOMAIN=$PUBLIC_PLAUSIBLE_DOMAIN \
    ASTRO_TELEMETRY_DISABLED=1

COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY . .
RUN npm run build

# ---------- runtime ----------
FROM nginx:alpine AS runtime
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY security-headers.conf /etc/nginx/snippets/security-headers.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=3s --retries=3 CMD wget -q -O /dev/null http://127.0.0.1/ || exit 1
