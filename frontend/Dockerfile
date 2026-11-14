FROM node:24-bookworm-slim AS dependencies
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
RUN chown node:node /app
USER node
COPY --chown=node:node frontend/package.json frontend/package-lock.json ./
RUN npm ci

FROM dependencies AS build
COPY --chown=node:node frontend/ ./
COPY --chown=node:node docs/ ./docs/
ARG STELLARIS_API_ORIGIN=http://api:8000
ENV STELLARIS_API_ORIGIN=$STELLARIS_API_ORIGIN
ENV STELLARIS_DOCS_ROOT=/app/docs
RUN npm run build

FROM dependencies AS development
ENV NODE_ENV=development WATCHPACK_POLLING=true HOSTNAME=0.0.0.0 PORT=3000
RUN mkdir -p /app/.next && sha256sum package.json package-lock.json > node_modules/.stellaris-dependencies.sha256
EXPOSE 3000
HEALTHCHECK --interval=15s --timeout=5s --start-period=600s --retries=3 CMD node -e "fetch('http://127.0.0.1:3000/api/v1/session').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"
CMD ["sh", "-c", "if ! sha256sum --check --status node_modules/.stellaris-dependencies.sha256 2>/dev/null; then npm ci --prefer-offline --no-audit --no-fund && sha256sum package.json package-lock.json > node_modules/.stellaris-dependencies.sha256 || exit 1; fi; exec npm run dev -- --webpack --hostname 0.0.0.0"]

FROM node:24-bookworm-slim AS runtime
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 HOSTNAME=0.0.0.0 PORT=3000
COPY --from=build --chown=node:node /app/.next/standalone ./
COPY --from=build --chown=node:node /app/.next/static ./.next/static
COPY --from=build --chown=node:node /app/public ./public
COPY --from=build --chown=node:node /app/docs ./docs
USER node
EXPOSE 3000
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=3 CMD node -e "fetch('http://127.0.0.1:3000/api/v1/session').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"
CMD ["node", "server.js"]
