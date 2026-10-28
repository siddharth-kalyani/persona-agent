#!/usr/bin/env bash
# Deploys one release on the EC2 instance (F14). GitHub Actions runs it as root through SSM Run Command
# after pushing the release's two images to ECR. Run it by hand to go back to an earlier release:
#
#   sudo bash /opt/PersonaAgent/app/deploy/ec2/deploy.sh <account>.dkr.ecr.ap-south-1.amazonaws.com <commit sha>
#
# 1. pulls the release's images (the ECR credential helper signs in with the instance role: no keys here);
# 2. points .env at them (VANIMO_API_IMAGE, VANIMO_WEB_IMAGE), so every compose command uses this release;
# 3. `docker compose up -d`: migrations first (the migrate service), then the API, then the web server;
# 4. waits for the API's health check, the database and the web server, and puts the previous images back
#    if any of them fails;
# 5. removes images no container uses any more (ECR keeps every release for a later rollback).
set -euo pipefail

registry="${1:?usage: deploy.sh <registry> <commit sha>}"
tag="${2:?usage: deploy.sh <registry> <commit sha>}"
cd "$(dirname "$0")"

log() { printf '%s %s\n' "$(date -u +%H:%M:%SZ)" "$*"; }
fail() {
  log "ERROR: $*"
  exit 1
}

[ -f .env ] || fail ".env is missing next to compose.yml (README step 16)"
command -v docker-credential-ecr-login >/dev/null || fail "the ECR credential helper isn't installed (README step I5)"

api="$registry/vanimo-api:$tag"
web="$registry/vanimo-web:$tag"

current() { sed -n "s/^$1=//p" .env | tail -n 1; }
set_env() { # replaces the key's line in .env (or removes it when the value is empty)
  sed -i "/^$1=/d" .env
  if [ -n "$2" ]; then printf '%s=%s\n' "$1" "$2" >>.env; fi
}

previous_api="$(current VANIMO_API_IMAGE)"
previous_web="$(current VANIMO_WEB_IMAGE)"

log "pulling ${tag:0:12}"
# The release's images, before anything changes: a failed pull leaves the running release alone.
VANIMO_API_IMAGE="$api" VANIMO_WEB_IMAGE="$web" docker compose pull --quiet api web

set_env VANIMO_API_IMAGE "$api"
set_env VANIMO_WEB_IMAGE "$web"

rollback() {
  log "rolling back: $1"
  set_env VANIMO_API_IMAGE "$previous_api"
  set_env VANIMO_WEB_IMAGE "$previous_web"
  docker compose up -d --remove-orphans || log "the previous release didn't start either: check 'docker compose logs'"
  docker compose logs --tail 40 migrate api || true
  fail "$1"
}

healthy() {
  local id status
  for _ in $(seq 1 60); do
    id="$(docker compose ps -q api)"
    status="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{end}}' "$id" 2>/dev/null || true)"
    if [ "$status" = healthy ] && curl -fsS -o /dev/null http://127.0.0.1:8080/config.json; then
      return 0
    fi
    sleep 5
  done
  return 1
}

log "starting (migrations first)"
docker compose up -d --remove-orphans || rollback "docker compose up failed"
healthy || rollback "the new release wasn't healthy within 5 minutes"
docker compose exec -T api python -c \
  "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/readyz', timeout=5)" ||
  rollback "the API can't reach the database"

printf '%s\n' "$tag" >.deployed
docker image prune -af >/dev/null || true
docker compose ps --format 'table {{.Service}}\t{{.Status}}'
log "deployed ${tag:0:12}"
