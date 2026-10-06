#!/usr/bin/env bash
# One-command production deployment on a fresh Linux server (Ubuntu/Debian, x86_64 or ARM).
#
#   git clone https://github.com/OmkarJayvantJadhav/ClinExtract.git && cd ClinExtract
#   sudo ./scripts/deploy.sh                 # uses a free <public-ip>.sslip.io hostname
#   sudo ./scripts/deploy.sh my.domain.org   # or your own domain (DNS A record -> this server)
#
# Re-running is safe: existing secrets in .env.production are kept and the stack is updated.
set -euo pipefail

cd "$(dirname "$0")/.."
COMPOSE=(docker compose -f docker-compose.prod.yml --env-file .env.production)

log() { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }

if [ "$(id -u)" -ne 0 ]; then
  echo "Please run with sudo: sudo ./scripts/deploy.sh [domain]" >&2
  exit 1
fi

# --- 1. Docker ----------------------------------------------------------------
if ! command -v docker >/dev/null 2>&1; then
  log "Installing Docker"
  curl -fsSL https://get.docker.com | sh
fi
systemctl enable --now docker >/dev/null 2>&1 || true

# --- 2. Host firewall ---------------------------------------------------------
# Oracle Cloud's Ubuntu images ship iptables rules that block everything except SSH.
if command -v iptables >/dev/null 2>&1; then
  for port in 80 443; do
    iptables -C INPUT -p tcp --dport "$port" -j ACCEPT 2>/dev/null \
      || iptables -I INPUT 1 -p tcp --dport "$port" -j ACCEPT
  done
  command -v netfilter-persistent >/dev/null 2>&1 && netfilter-persistent save >/dev/null 2>&1 || true
fi
if command -v ufw >/dev/null 2>&1 && ufw status | grep -q "Status: active"; then
  ufw allow 80/tcp >/dev/null && ufw allow 443/tcp >/dev/null
fi

# --- 3. Hostname --------------------------------------------------------------
if [ -n "${1:-}" ]; then
  SITE="$1"
else
  PUBLIC_IP="$(curl -fsS --max-time 10 https://api.ipify.org || curl -fsS --max-time 10 https://ifconfig.me)"
  SITE="$(echo "$PUBLIC_IP" | tr '.' '-').sslip.io"   # free wildcard DNS: resolves to PUBLIC_IP
fi

# --- 4. Secrets (generated once, kept on re-runs) -----------------------------
if [ ! -f .env.production ]; then
  log "Generating secrets in .env.production"
  rand() { openssl rand -hex "${1:-32}"; }
  fernet_key="$(openssl rand -base64 32 | tr '+/' '-_')"
  umask 077
  cat > .env.production <<EOF
SITE_ADDRESS=$SITE
POSTGRES_PASSWORD=$(rand 24)
RABBITMQ_USER=clinextract
RABBITMQ_PASSWORD=$(rand 24)
JWT_SECRET=$(rand 32)
DOCUMENT_ENCRYPTION_KEY=$fernet_key
DOCUMENT_RETENTION_DAYS=0
BACKUP_RETENTION_DAYS=14
METRICS_TOKEN=$(rand 16)
EXTRACTION_PROVIDER=rule_based
ALLOW_EXTERNAL_AI_PHI=false
EOF
  FIRST_RUN=1
else
  sed -i "s|^SITE_ADDRESS=.*|SITE_ADDRESS=$SITE|" .env.production
  FIRST_RUN=0
fi
chmod 600 .env.production

# --- 5. Start ------------------------------------------------------------------
log "Building and starting ClinExtract (first build takes several minutes)"
"${COMPOSE[@]}" up -d --build

log "Waiting for the API to become ready"
for _ in $(seq 1 60); do
  if "${COMPOSE[@]}" exec -T backend python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/api/v1/health/ready', timeout=3).status == 200 else 1)" 2>/dev/null; then
    READY=1; break
  fi
  sleep 5
done
if [ "${READY:-0}" != 1 ]; then
  echo "The API did not become ready. Inspect with: ${COMPOSE[*]} logs backend" >&2
  exit 1
fi

# --- 6. First admin -------------------------------------------------------------
if [ "$FIRST_RUN" = 1 ]; then
  log "Creating the admin account"
  ADMIN_PW="Cx-$(openssl rand -hex 6)-Ad9!"
  OTHER_PW="Cx-$(openssl rand -hex 12)-Zz7!"   # other seed users get an unknown password; reset them in the UI
  "${COMPOSE[@]}" exec -T \
    -e ADMIN_SEED_PASSWORD="$ADMIN_PW" -e REVIEWER_SEED_PASSWORD="$OTHER_PW" \
    -e OPERATOR_SEED_PASSWORD="$OTHER_PW" -e VIEWER_SEED_PASSWORD="$OTHER_PW" \
    backend python scripts/seed_users.py >/dev/null
fi

cat <<EOF

=====================================================================
 ClinExtract is live:  https://$SITE
EOF
if [ "$FIRST_RUN" = 1 ]; then
cat <<EOF
 Admin login:          admin / $ADMIN_PW
 (shown once - change it in Settings after signing in)
EOF
fi
cat <<EOF

 Secrets: $(pwd)/.env.production  (back up DOCUMENT_ENCRYPTION_KEY!)
 Logs:    ${COMPOSE[*]} logs -f
 Update:  git pull && sudo ./scripts/deploy.sh ${1:-}
=====================================================================
EOF
