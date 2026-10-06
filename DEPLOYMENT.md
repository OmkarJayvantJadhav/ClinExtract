# Free Deployment (Oracle Cloud Always Free)

This gets you a permanent public HTTPS link such as `https://129-146-12-34.sslip.io`, at no cost.
Oracle's Always Free tier includes an ARM VM (up to 4 CPUs / 24 GB RAM) that runs the whole
production stack (`docker-compose.prod.yml`) unchanged.

> **Demo data only.** A public deployment like this is fine for a portfolio or demo with
> synthetic documents. Do not upload real patient data (see "Data Protection" in the README).

## 1. Create the server (about 10 minutes, in your browser)

1. Sign up at <https://www.oracle.com/cloud/free/>. A card is required for identity
   verification; Always Free resources are not charged.
2. In the console, open **Compute → Instances → Create instance**:
   - **Image:** Canonical Ubuntu 24.04 (or 22.04)
   - **Shape:** *Change shape* → **Ampere** → `VM.Standard.A1.Flex` with **2 OCPU / 12 GB**
     (Always Free eligible). If you see "out of capacity", try another availability domain or
     retry later. `VM.Standard.E2.1.Micro` is also free, but 1 GB RAM is too small for OCR.
   - **Networking:** keep "Assign a public IPv4 address" enabled.
   - **SSH keys:** "Generate a key pair for me" and **download the private key**.
3. Click **Create**, then copy the instance's **Public IP address**.
4. Open ports 80 and 443: on the instance page click the **Subnet** → **Security Lists** →
   the default list → **Add Ingress Rules**:
   - Source CIDR `0.0.0.0/0`, IP protocol TCP, destination port range `80,443`.

## 2. Deploy (one command)

From your computer (PowerShell, macOS or Linux terminal):

```bash
ssh -i path/to/ssh-key.key ubuntu@<PUBLIC_IP>
```

Then on the server:

```bash
git clone https://github.com/OmkarJayvantJadhav/ClinExtract.git
cd ClinExtract
sudo ./scripts/deploy.sh
```

The script installs Docker, opens the host firewall, generates all secrets into
`.env.production`, builds and starts the stack, and creates the admin account. The first build
takes about 10 minutes on the ARM VM. At the end it prints:

```
 ClinExtract is live:  https://<ip-with-dashes>.sslip.io
 Admin login:          admin / <generated password>
```

Save that password (it is shown once) and change it in **Settings** after signing in.
Also copy `DOCUMENT_ENCRYPTION_KEY` from `~/ClinExtract/.env.production` somewhere safe;
without it, stored documents and backups cannot be read.

## Using your own domain instead

Point a DNS **A record** at the server's IP, then run `sudo ./scripts/deploy.sh your.domain.org`.
Free option: create a subdomain at <https://www.duckdns.org> (for example `clinextract.duckdns.org`).

## Updating

```bash
cd ~/ClinExtract && git pull && sudo ./scripts/deploy.sh
```
Secrets are kept and migrations run automatically.

## Troubleshooting

| Symptom | Fix |
|---|---|
| Browser can't connect | Check the ingress rule for 80/443 (step 1.4); then `sudo iptables -L INPUT -n \| head` |
| Certificate error | Wait a minute after first start; check `docker compose -f docker-compose.prod.yml --env-file .env.production logs web` |
| Services not healthy | `docker compose -f docker-compose.prod.yml --env-file .env.production ps` and `... logs backend worker` |
| Forgot admin password | `docker compose -f docker-compose.prod.yml --env-file .env.production exec -e ADMIN_SEED_PASSWORD='New-Strong-Pass1!' backend python scripts/seed_users.py --reset --user admin` |

`sslip.io` is a free public DNS service that maps `1-2-3-4.sslip.io` to `1.2.3.4`. If
certificate issuance for it is ever rate-limited, use a DuckDNS subdomain as described above.
