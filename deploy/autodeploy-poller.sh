#!/bin/bash
# Auto-deploy-on-push without opening any inbound port.
#
# Coolify's webhook endpoint lives on port 8000, which this VPS deliberately
# firewalls off the public internet — so instead of exposing it to GitHub, a
# cron job polls GitHub for a new HEAD on main (via the deploy key Coolify
# already holds) and triggers the deploy through Coolify's *localhost* API.
# Zero new attack surface; worst-case latency is one poll interval.
#
# Install (as root on the VPS; substitute your own values):
#   cp deploy/autodeploy-poller.sh /usr/local/bin/icm-autodeploy.sh
#   chmod +x /usr/local/bin/icm-autodeploy.sh
#   mkdir -p /var/lib/icm-autodeploy
#   /usr/local/bin/icm-autodeploy.sh   # first run records current HEAD
#   printf '*/2 * * * * root /usr/local/bin/icm-autodeploy.sh\n' > /etc/cron.d/icm-autodeploy
#
# Configuration: the deploy-key path inside the coolify container, the Coolify
# API token (Keys & Tokens -> API tokens, or see docs/deployment.md), and the
# application uuid (visible in the app's URL in the Coolify UI).
set -u

STATE=/var/lib/icm-autodeploy/head
LOG=/var/log/icm-autodeploy.log
REPO=git@github.com:Kriztophr/NS.git
KEY=/var/www/html/storage/app/ssh/keys/ssh_key@l0scg8s4c08gcc80ocgs4ws8   # path inside the coolify container
APP_UUID=t480sk0kc8gkc44k8s0cokg8
TOKEN_FILE=/root/.icm-coolify-token   # optional: file containing the bearer token
TOKEN=${COOLIFY_TOKEN:-$(cat "$TOKEN_FILE" 2>/dev/null || true)}

CUR=$(docker exec coolify sh -c \
  "GIT_SSH_COMMAND='ssh -i $KEY -o StrictHostKeyChecking=accept-new -o IdentitiesOnly=yes' \
   git ls-remote $REPO refs/heads/main" 2>/dev/null | cut -f1)
[ -z "$CUR" ] && { echo "$(date -Is) ls-remote failed" >> "$LOG"; exit 0; }

LAST=$(cat "$STATE" 2>/dev/null || true)
if [ "$CUR" != "$LAST" ]; then
  R=$(curl -sS -m 25 -H "Authorization: Bearer $TOKEN" \
    "http://localhost:8000/api/v1/deploy?uuid=$APP_UUID" 2>&1)
  echo "$(date -Is) new HEAD $CUR -> deploy: $R" >> "$LOG"
  echo "$CUR" > "$STATE"
else
  echo "$(date -Is) up-to-date at $CUR" >> "$LOG"
fi
