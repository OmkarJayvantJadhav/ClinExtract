#!/usr/bin/env bash
# One-command setup of a public ClinExtract demo on a fresh Ubuntu 22.04/24.04 server, e.g. an
# Oracle Cloud Always Free VM (docs/DEPLOY_FREE_ORACLE.md) or an AWS t4g.small (docs/DEPLOY_AWS.md).
#
#   git clone https://github.com/OmkarJayvantJadhav/ClinExtract.git && cd ClinExtract
#   sudo bash scripts/setup-server.sh                 # https://<public-ip>.sslip.io
#   sudo bash scripts/setup-server.sh myname.duckdns.org
#
# Safe to re-run: existing secrets in .env.production are kept, so re-running after
# `git pull` just rebuilds and restarts the stack.
set -euo pipefail

cd "$(dirname "$0")/.."
ENV_FILE=.env.production
COMPOSE=(docker compose -f docker-compose.prod.yml --env-file "$ENV_FILE")

log() { printf '\n==> %s\n' "$*"; }

if [[ $EUID -ne 0 ]]; then
  echo "Run with sudo: sudo bash $0 $*" >&2
  exit 1
fi

# --- Docker --------------------------------------------------------------------------
if ! command -v docker >/dev/null 2>&1 || ! docker compose version >/dev/null 2>&1; then
  log "Installing Docker"
  curl -fsSL https://get.docker.com | sh
fi
systemctl enable --now docker >/dev/null
if [[ -n "${SUDO_USER:-}" ]]; then
  usermod -aG docker "$SUDO_USER"
fi

# --- Firewall: Oracle's Ubuntu images reject everything but SSH in iptables -----------
log "Opening ports 80 and 443 in the host firewall"
for port in 80 443; do
  if ! iptables -C INPUT -p tcp --dport "$port" -m state --state NEW -j ACCEPT 2>/dev/null; then
    reject_line=$(iptables -L INPUT --line-numbers -n | awk '/REJECT/ {print $1; exit}')
    if [[ -n "$reject_line" ]]; then
      iptables -I INPUT "$reject_line" -p tcp --dport "$port" -m state --state NEW -j ACCEPT
    else
      iptables -A INPUT -p tcp --dport "$port" -m state --state NEW -j ACCEPT
    fi
  fi
done
if command -v netfilter-persistent >/dev/null 2>&1; then
  netfilter-persistent save >/dev/null 2>&1 || true
fi

# --- Swap on small machines (OCR and the image builds need memory) --------------------
mem_mb=$(awk '/MemTotal/ {print int($2 / 1024)}' /proc/meminfo)
if [[ "$mem_mb" -lt 4000 ]] && ! swapon --show | grep -q .; then
  log "Adding 2 GB of swap (${mem_mb} MB RAM)"
  fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile >/dev/null && swapon /swapfile
  grep -q '^/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

# --- Configuration -------------------------------------------------------------------
site="${1:-}"
if [[ -z "$site" && -f "$ENV_FILE" ]]; then
  site=$(sed -n 's/^SITE_ADDRESS=//p' "$ENV_FILE")
fi
if [[ -z "$site" ]]; then
  ip=$(curl -fsS -4 https://ifconfig.me || curl -fsS -4 https://api.ipify.org)
  site="${ip//./-}.sslip.io"
fi

secret() { openssl rand -hex 32; }
# One API process and one OCR worker fit a 2 GB server; bigger machines run two of each.
processes=$([[ "$mem_mb" -lt 3000 ]] && echo 1 || echo 2)
if [[ ! -f "$ENV_FILE" ]]; then
  log "Creating $ENV_FILE with fresh secrets"
  cat > "$ENV_FILE" <<EOF
SITE_ADDRESS=$site
POSTGRES_PASSWORD=$(secret)
RABBITMQ_USER=clinextract
RABBITMQ_PASSWORD=$(secret)
JWT_SECRET=$(secret)
# Fernet key: url-safe base64 of 32 random bytes. Without it stored documents cannot be read.
DOCUMENT_ENCRYPTION_KEY=$(openssl rand -base64 32 | tr '+/' '-_')

# Demo housekeeping: finished documents are purged after this many days
DOCUMENT_RETENTION_DAYS=3
BACKUP_RETENTION_DAYS=7

# Public demo accounts (one-click sign-in on the login page). Admin stays private.
DEMO_ACCOUNTS=operator,reviewer,viewer
DEMO_PASSWORD=Demo-$(openssl rand -hex 6)
ADMIN_SEED_PASSWORD=Adm1n-$(openssl rand -hex 12)

# How to read dates like 03/04/2025: MDY (US: March 4) or DMY (3 April)
DATE_ORDER=MDY

# Processes (raise on a bigger machine)
API_WORKERS=$processes
WORKER_CONCURRENCY=$processes

EXTRACTION_PROVIDER=rule_based
ALLOW_EXTERNAL_AI_PHI=false
EOF
  chmod 600 "$ENV_FILE"
elif ! grep -q "^SITE_ADDRESS=$site\$" "$ENV_FILE"; then
  sed -i "s/^SITE_ADDRESS=.*/SITE_ADDRESS=$site/" "$ENV_FILE"
fi
env_value() { sed -n "s/^$1=//p" "$ENV_FILE"; }

# --- Build and start -------------------------------------------------------------------
log "Building and starting the stack for https://$site (the first build takes several minutes)"
"${COMPOSE[@]}" up -d --build

log "Waiting for the API to become ready"
for _ in $(seq 1 60); do
  if "${COMPOSE[@]}" exec -T backend python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health/ready', timeout=3)" >/dev/null 2>&1; then
    ready=1
    break
  fi
  sleep 5
done
if [[ -z "${ready:-}" ]]; then
  echo "The API did not become ready. Check: ${COMPOSE[*]} logs backend" >&2
  exit 1
fi

log "Creating user accounts (existing accounts are left unchanged)"
demo_password=$(env_value DEMO_PASSWORD)
"${COMPOSE[@]}" exec -T \
  -e ADMIN_SEED_PASSWORD="$(env_value ADMIN_SEED_PASSWORD)" \
  -e OPERATOR_SEED_PASSWORD="$demo_password" \
  -e REVIEWER_SEED_PASSWORD="$demo_password" \
  -e VIEWER_SEED_PASSWORD="$demo_password" \
  backend python scripts/seed_users.py

cat <<EOF

ClinExtract is running at:  https://$site
(The HTTPS certificate is issued on the first visit; allow a minute.)

Demo accounts (shown on the sign-in page): operator, reviewer, viewer / $demo_password
Admin (keep private):                      admin / $(env_value ADMIN_SEED_PASSWORD)

Secrets are in $(pwd)/$ENV_FILE. Back up DOCUMENT_ENCRYPTION_KEY somewhere safe.
Update later with:  git pull && sudo bash scripts/setup-server.sh
EOF
