#!/usr/bin/env bash
# Server side of the deploy, installed as /usr/local/bin/deploy-grok-invoices.
# Reads a tar of the release from stdin. Usage: deploy-grok-invoices <40-char git sha>
set -euo pipefail

ROOT=/srv/grok-invoices
KEEP_RELEASES=5

sha="${1:-}"
if [[ ! "$sha" =~ ^[0-9a-f]{40}$ ]]; then
  echo "usage: deploy-grok-invoices <40-char git sha>" >&2
  exit 64
fi

exec 9>"$ROOT/.deploy.lock"
flock 9

release="$ROOT/releases/$sha"
compose=(docker compose --project-name grok-invoices --file "$ROOT/compose.yaml")

rm -rf "$release"
mkdir -p "$release"
tar --extract --no-same-owner --directory "$release"

echo "==> Building ${sha:0:12}"
docker build --quiet --tag "grok-invoices:$sha" "$release" </dev/null

previous=""
if [[ -L "$ROOT/current" ]]; then
  previous="$(basename "$(readlink "$ROOT/current")")"
fi

echo "==> Starting ${sha:0:12}"
if ! RELEASE="$sha" "${compose[@]}" up --detach --wait --wait-timeout 60 </dev/null; then
  echo "==> Health check failed. Recent logs:" >&2
  RELEASE="$sha" "${compose[@]}" logs --tail 50 </dev/null >&2 || true
  if [[ -n "$previous" && "$previous" != "$sha" ]]; then
    echo "==> Rolling back to ${previous:0:12}" >&2
    RELEASE="$previous" "${compose[@]}" up --detach --wait --wait-timeout 60 </dev/null >&2 \
      || echo "==> Rollback failed too" >&2
  fi
  exit 1
fi

ln -sfn "$release" "$ROOT/current"

# Only ever removes this app's own releases and image tags.
cd "$ROOT/releases"
ls -1t | tail -n "+$((KEEP_RELEASES + 1))" | while read -r old; do
  [[ "$old" =~ ^[0-9a-f]{40}$ && "$old" != "$sha" && "$old" != "$previous" ]] || continue
  rm -rf "${ROOT:?}/releases/$old"
  docker image rm "grok-invoices:$old" >/dev/null 2>&1 || true
done

echo "==> Deployed ${sha:0:12}"
