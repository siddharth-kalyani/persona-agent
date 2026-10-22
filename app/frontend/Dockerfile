# Vanimo web app for the EC2 deployment (F11, app/deploy/ec2): the static build served by Caddy, which
# also forwards /api/* to the API container. The production cell serves the same build from S3 +
# CloudFront (app/infra) instead.
FROM node:24-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM caddy:2.10-alpine
COPY --from=build /app/dist /srv
# No Entra in this deployment (F11): an empty Microsoft sign-in config, so only password sign-in shows.
RUN printf '{"tenantId": "", "clientId": "", "apiBase": ""}\n' > /srv/config.json
