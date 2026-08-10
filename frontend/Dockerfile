FROM node:20-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
# npm install (pas ci) : le lockfile est généré sous Windows et n'a pas les variantes
# natives Linux (@emnapi/*, Tailwind v4) — même contournement que la CI.
RUN npm install --no-audit --no-fund
COPY . .
ARG NEXT_PUBLIC_ARGUS_API=http://localhost:8000
ENV NEXT_PUBLIC_ARGUS_API=$NEXT_PUBLIC_ARGUS_API
RUN npm run build

FROM node:20-slim AS run
WORKDIR /app
ENV NODE_ENV=production
COPY --from=build /app/.next/standalone ./
COPY --from=build /app/.next/static ./.next/static
COPY --from=build /app/public ./public
EXPOSE 3000
CMD ["node", "server.js"]
