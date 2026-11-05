#!/usr/bin/env bash
# One-time server setup. Safe to re-run to update the deploy script or compose file.
# Usage: sudo ./install.sh "<deploy public key>" <public hostname>
set -euo pipefail

pubkey="${1:?deploy public key is required}"
host="${2:?public hostname is required}"
src="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT=/srv/grok-invoices
USER_NAME=deploy-grok

id "$USER_NAME" >/dev/null 2>&1 || useradd --system --create-home --shell /bin/bash "$USER_NAME"

install -d -m 755 "$ROOT" "$ROOT/releases"
[[ -e "$ROOT/.env" ]] || install -m 600 /dev/null "$ROOT/.env"
install -m 644 "$src/compose.prod.yaml" "$ROOT/compose.yaml"
install -m 755 "$src/deploy.sh" /usr/local/bin/deploy-grok-invoices

# The CI key can run the deploy script and nothing else.
sudoers="$(mktemp)"
echo "$USER_NAME ALL=(root) NOPASSWD: /usr/local/bin/deploy-grok-invoices" >"$sudoers"
visudo -cf "$sudoers" >/dev/null
install -m 440 "$sudoers" "/etc/sudoers.d/$USER_NAME"
rm -f "$sudoers"

ssh_dir="/home/$USER_NAME/.ssh"
install -d -m 700 -o "$USER_NAME" -g "$USER_NAME" "$ssh_dir"
printf 'restrict,command="sudo -n /usr/local/bin/deploy-grok-invoices \\"$SSH_ORIGINAL_COMMAND\\"" %s\n' "$pubkey" \
  >"$ssh_dir/authorized_keys"
chown "$USER_NAME:$USER_NAME" "$ssh_dir/authorized_keys"
chmod 600 "$ssh_dir/authorized_keys"

# Skip when the site exists, because certbot has edited it by then.
site=/etc/nginx/sites-available/grok-invoices
if [[ ! -e "$site" ]]; then
  sed "s/__HOST__/$host/g" "$src/nginx.conf" >"$site"
  ln -sfn "$site" /etc/nginx/sites-enabled/grok-invoices
  if ! nginx -t; then
    rm -f /etc/nginx/sites-enabled/grok-invoices "$site"
    echo "nginx config invalid; removed the new site" >&2
    exit 1
  fi
  systemctl reload nginx
  certbot --nginx --non-interactive --keep-until-expiring --redirect --domains "$host"
fi

echo "Installed. Public host: $host"
