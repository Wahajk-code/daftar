FROM node:22-slim

ENV TZ=UTC \
    NEXT_TELEMETRY_DISABLED=1

# pnpm is pinned by the packageManager field in package.json.
RUN corepack enable

WORKDIR /app

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile

COPY . .

EXPOSE 3000
CMD ["pnpm", "dev", "--hostname", "0.0.0.0"]
