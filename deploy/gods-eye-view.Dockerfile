# Dedicated upstream service: its Vite middleware serves both the globe and public-data APIs.
# Keep this separate from NOX FastAPI so the two applications' /api routes never collide.
FROM node:24.14.0-slim

ENV PUPPETEER_SKIP_DOWNLOAD=1 \
    HOST=0.0.0.0 \
    PORT=10000 \
    GEV_ALLOWED_HOSTS=nox-gods-eye-view.onrender.com

RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
RUN git init \
    && git remote add origin https://github.com/bilawalsidhu/gods-eye-view.git \
    && git fetch --depth 1 origin 505d2cb5861905c76a98465799a29e1fd71b869b \
    && git checkout --detach FETCH_HEAD \
    && chown -R node:node /app

USER node
RUN npm ci

EXPOSE 10000
CMD ["node", "scripts/docker-start.mjs"]
