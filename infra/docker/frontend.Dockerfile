FROM node:20-alpine AS builder

RUN corepack enable

WORKDIR /repo

COPY package.json pnpm-workspace.yaml pnpm-lock.yaml ./
COPY packages ./packages
COPY apps/web ./apps/web

RUN pnpm install --frozen-lockfile
RUN pnpm --filter @amezia/web run build

FROM nginx:alpine

COPY infra/docker/frontend.nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /repo/apps/web/dist/web/browser /usr/share/nginx/html

EXPOSE 80
