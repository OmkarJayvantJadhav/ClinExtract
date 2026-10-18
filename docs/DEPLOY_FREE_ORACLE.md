# Free public demo on Oracle Cloud

This puts ClinExtract online at a shareable HTTPS link for $0, using an Oracle Cloud
"Always Free" virtual machine. The whole production stack (web server with HTTPS, API, OCR
worker, scheduler, PostgreSQL, RabbitMQ, backups) runs on the one VM, unchanged.

The demo uses **synthetic data only**. The sign-in page offers shared demo accounts with
one-click sign-in, and the upload page offers sample lab reports to try.

> Oracle's free-tier terms change. Everything here was checked in October 2026; confirm the
> current limits on Oracle's [Always Free resources](https://docs.oracle.com/en-us/iaas/Content/FreeTier/resourceref.htm) page.

## What it costs

- **Nothing**, as long as you stay inside the Always Free limits. Oracle asks for a card to
  verify your identity (a temporary authorization hold, not a charge).
- Always Free includes Ampere A1 (ARM) capacity of about 2 CPUs and 12 GB of memory in total,
  plus up to 200 GB of disk. ClinExtract fits comfortably in that.
- A domain name is optional: the setup script uses a free `<your-ip>.sslip.io` hostname.

## 1. Create the account

Sign up at [oracle.com/cloud/free](https://www.oracle.com/cloud/free/). Pick your **home
region** carefully: Always Free VMs can only run there, and it cannot be changed later. A region
near you, or a large one with more ARM capacity, works best.

## 2. Create the VM

In the Oracle Cloud console: **Compute → Instances → Create instance**.

1. **Name:** `clinextract`.
2. **Image:** Canonical Ubuntu 24.04 (or 22.04).
3. **Shape:** *Change shape → Ampere → VM.Standard.A1.Flex*, with **2 OCPUs and 12 GB memory**.
   It should be labelled *Always Free-eligible*.
4. **Networking:** create a new virtual cloud network with a **public subnet**, and keep
   *Assign a public IPv4 address* switched on.
5. **SSH keys:** choose *Generate a key pair* and download the private key, or paste your
   own public key.
6. **Boot volume:** the default (about 47 GB) is enough.
7. Click **Create** and wait until the instance is *Running*. Note its **public IP address**.

If you get **"Out of capacity"**, try another availability domain in the same form, try
1 OCPU / 6 GB (also works for a demo), or try again later. ARM capacity frees up during the day.

## 3. Open ports 80 and 443

Oracle blocks web traffic by default at the network level.

1. On the instance page, click the **subnet** link, then the **Default Security List**.
2. **Add Ingress Rules**: Source CIDR `0.0.0.0/0`, IP protocol TCP, destination port `80`.
3. Add a second rule the same way for port `443`.

(The host firewall inside the VM is opened by the setup script.)

## 4. Install ClinExtract

Connect to the VM (on Windows, use PowerShell; the key file is the one you downloaded):

```bash
ssh -i path/to/private.key ubuntu@<public-ip>
```

Then run:

```bash
git clone https://github.com/OmkarJayvantJadhav/ClinExtract.git
cd ClinExtract
sudo bash scripts/oracle-setup.sh
```

The script installs Docker, opens the firewall, generates every secret into
`.env.production`, builds and starts the stack, and creates the user accounts. The first run
takes roughly 10–15 minutes, mostly building the images. At the end it prints:

```
ClinExtract is running at:  https://129-146-12-34.sslip.io
Demo accounts (shown on the sign-in page): operator, reviewer, viewer / Demo-…
Admin (keep private):                      admin / Adm1n-…
```

Open the link (the HTTPS certificate is issued on the first visit, so give it a minute) and
share it. Visitors click **Sign in as operator** to upload a sample report, then sign in as
**reviewer** to review it.

## Using your own hostname (optional)

For a nicer link, get a free subdomain at [duckdns.org](https://www.duckdns.org), point it at
the VM's public IP, and re-run the script with it:

```bash
sudo bash scripts/oracle-setup.sh myclinextract.duckdns.org
```

## Keeping the demo up

- **Idle reclamation:** Oracle may reclaim Always Free VMs that stay mostly idle for 7 days
  (CPU, network and memory use all under 20%). Community reports say upgrading the account to
  *Pay As You Go* (Billing → Upgrade) stops this while usage still stays inside the free
  limits, so it still costs nothing. Set a budget alert at $1 if you do.
- **Housekeeping:** finished documents are purged after 3 days (`DOCUMENT_RETENTION_DAYS` in
  `.env.production`), and a daily database backup is kept for 7 days.
- **Shared accounts are protected:** the demo accounts cannot change their password, sign
  out other visitors, or be locked by failed logins. The admin account is never offered on
  the sign-in page; keep its password to yourself.

## Everyday commands

Run these in the `ClinExtract` folder on the VM:

```bash
# Update to the latest code (keeps your secrets and data)
git pull && sudo bash scripts/oracle-setup.sh

# Status and logs
sudo docker compose -f docker-compose.prod.yml --env-file .env.production ps
sudo docker compose -f docker-compose.prod.yml --env-file .env.production logs -f backend worker

# Restart everything
sudo docker compose -f docker-compose.prod.yml --env-file .env.production restart
```

## Troubleshooting

| Symptom | Fix |
|---|---|
| The link does not load at all | Check the two ingress rules (step 3) and that the instance is running. `curl -I http://localhost` on the VM should answer. |
| Browser warns about the certificate | Wait a minute after the first visit. If it persists, check `docker compose … logs web`. With sslip.io, certificate issuance can be rate-limited; switch to a DuckDNS name. |
| Uploads stay in *Processing* | Check `docker compose … logs worker`. A document that failed can be retried from its page with **Retry processing**. |
| Forgot the passwords | They are in `.env.production` (`DEMO_PASSWORD`, `ADMIN_SEED_PASSWORD`). |
