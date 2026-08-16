# Rico frontend — production image.
#
# Multi-stage: deps → build → minimal runtime running `next start`. Runs as the
# non-root `node` user. No secrets baked in (apps/web/.dockerignore excludes all
# env/token artifacts).
#
# BUILD-TIME configuration: the /proxy rewrite target and NEXT_PUBLIC_* values
# are inlined at `npm run build` time, so the image is environment-specific.
# Supply the backend origin as build args (defaults to the canonical
# production host) — the resulting image must not be reused across environments
# with different backend origins.

FROM node:20-slim AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM node:20-slim AS build
WORKDIR /app
ARG BACKEND_API_BASE_URL=https://api.ricohunt.com
ARG NEXT_PUBLIC_API_BASE_URL=https://api.ricohunt.com
ARG NEXT_PUBLIC_APP_URL=https://ricohunt.com
ENV BACKEND_API_BASE_URL=$BACKEND_API_BASE_URL \
    NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL \
    NEXT_PUBLIC_APP_URL=$NEXT_PUBLIC_APP_URL \
    NEXT_TELEMETRY_DISABLED=1
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:20-slim AS runtime
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1
COPY --from=build /app/package.json ./package.json
COPY --from=build /app/node_modules ./node_modules
COPY --from=build /app/.next ./.next
COPY --from=build /app/public ./public
COPY --from=build /app/next.config.js ./next.config.js
COPY --from=build /app/tailwind.config.ts ./tailwind.config.ts
COPY --from=build /app/postcss.config.js ./postcss.config.js

USER node
EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD node -e "fetch('http://127.0.0.1:3000').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"

CMD ["npm", "run", "start"]
