# ── Build stage ────────────────────────────────────────────
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json ./
RUN npm install
COPY . .
RUN npm run build

# ── Serve stage ────────────────────────────────────────────
FROM nginx:stable-alpine-slim
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
COPY docker-entrypoint.sh /docker-entrypoint.d/40-runtime-config.sh

# Fix permissions for non-root nginx (UID 101)
RUN chmod +x /docker-entrypoint.d/40-runtime-config.sh && \
    chown -R 101:101 /usr/share/nginx/html && \
    chown -R 101:101 /var/cache/nginx && \
    chown -R 101:101 /var/log/nginx && \
    touch /var/run/nginx.pid && chown 101:101 /var/run/nginx.pid

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
