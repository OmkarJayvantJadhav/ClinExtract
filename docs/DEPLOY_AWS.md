# Public demo on AWS (free plan)

This puts ClinExtract online at a shareable HTTPS link on one small AWS server, using the
AWS Free Plan and the T4g free trial. The whole production stack (web server with HTTPS, API,
OCR worker, scheduler, PostgreSQL, RabbitMQ, backups) runs on the one server, unchanged.

The demo uses **synthetic data only**. The sign-in page offers shared demo accounts with
one-click sign-in, and the upload page offers sample lab reports to try.

> AWS changes its free offers. Everything here was checked in October 2026; confirm the
> current terms on the [AWS Free Tier](https://aws.amazon.com/free/) page before you start.

## What it costs

- **The server (t4g.small: 2 ARM CPUs, 2 GB memory)** is free for 750 hours a month, enough
  to run it all month, under the T4g free trial, which AWS runs until **December 31, 2026**.
  After that it costs roughly $12 a month, paid from your free-plan credits.
- **New accounts** (opened after July 15, 2025) on the **Free Plan** get $100 in credits,
  up to $200 by completing onboarding tasks. These cover the disk and anything else. On the
  Free Plan AWS does not charge your card: when the credits or the plan period run out, the
  account is closed instead.
- **The Free Plan lasts 6 months** (or until the credits are used up). Before it ends, either
  upgrade the account to the Paid Plan or move the demo elsewhere. Check **Billing → Free
  Tier** in the console for your remaining credits and the plan's end date.
- A domain name is optional: the setup script uses a free `<your-ip>.sslip.io` hostname.

## 1. Create the account and a budget alert

1. Sign up at [aws.amazon.com/free](https://aws.amazon.com/free/) and choose the **Free Plan**.
2. In the console, open **Billing and Cost Management → Budgets → Create budget**, choose the
   *Zero spend* template, and enter your email. You'll be told if anything ever costs money.

## 2. Launch the server

In the console, pick a region near you (top right), then **EC2 → Launch instance**:

1. **Name:** `clinextract`.
2. **Application and OS image:** Ubuntu Server 24.04 LTS, architecture **64-bit (Arm)**.
3. **Instance type:** **t4g.small**.
4. **Key pair:** *Create new key pair* (type RSA, format `.pem`) and keep the downloaded file safe.
5. **Network settings → Edit**, *Create security group* with these inbound rules:
   - SSH (port 22), source **My IP**
   - HTTP (port 80), source **Anywhere**
   - HTTPS (port 443), source **Anywhere**
6. **Configure storage:** 20 GiB, gp3.
7. **Launch instance**, then open it and note its **Public IPv4 address**.

**Keep the same address (recommended):** the free hostname is built from the IP, and a normal
public IP changes whenever the server is stopped and started. In **EC2 → Elastic IPs →
Allocate Elastic IP address**, then **Actions → Associate** it with the instance, and use
that address from now on. It replaces the server's normal public IP and is billed the same
way (a few dollars a month at most, covered by the credits).

## 3. Install ClinExtract

Connect from your computer (on Windows, use PowerShell):

```bash
ssh -i path/to/clinextract.pem ubuntu@<public-ip>
```

(On macOS or Linux, run `chmod 400 path/to/clinextract.pem` first if SSH says the key's
permissions are too open.)

Then run:

```bash
git clone https://github.com/OmkarJayvantJadhav/ClinExtract.git
cd ClinExtract
sudo bash scripts/setup-server.sh
```

The script installs Docker, adds swap memory, generates every secret into `.env.production`,
builds and starts the stack, and creates the user accounts. On a 2 GB server it runs one API
process and one OCR worker so everything fits. The first run takes roughly 15–20 minutes, mostly
building the images. At the end it prints:

```
ClinExtract is running at:  https://3-110-45-67.sslip.io
Demo accounts (shown on the sign-in page): operator, reviewer, viewer / Demo-…
Admin (keep private):                      admin / Adm1n-…
```

Open the link (the HTTPS certificate is issued on the first visit, so give it a minute) and
share it. Visitors click **Sign in as operator** to upload a sample report, then sign in as
**reviewer** to review it.

## Using your own hostname (optional)

For a nicer link, get a free subdomain at [duckdns.org](https://www.duckdns.org), point it at
the server's (Elastic) IP, and re-run the script with it:

```bash
sudo bash scripts/setup-server.sh myclinextract.duckdns.org
```

## Everyday commands

Run these in the `ClinExtract` folder on the server:

```bash
# Update to the latest code (keeps your secrets and data)
git pull && sudo bash scripts/setup-server.sh

# Status and logs
sudo docker compose -f docker-compose.prod.yml --env-file .env.production ps
sudo docker compose -f docker-compose.prod.yml --env-file .env.production logs -f backend worker
```

**Before the Free Plan ends**, keep a copy of `.env.production` (it holds the encryption key)
and, if you want to keep the data, the latest backup:
`sudo docker compose -f docker-compose.prod.yml --env-file .env.production run --rm backup --once`.

## Troubleshooting

| Symptom | Fix |
|---|---|
| The link does not load at all | Check the security group allows HTTP and HTTPS from anywhere, and that the instance is running. `curl -I http://localhost` on the server should answer. |
| `ssh` times out | The SSH rule is limited to *My IP*; if your IP changed, edit the security group rule. |
| Build is very slow or the server freezes | Make sure swap is on (`swapon --show`). On a 2 GB server, keep `API_WORKERS=1` and `WORKER_CONCURRENCY=1` in `.env.production`. |
| Browser warns about the certificate | Wait a minute after the first visit. If it persists, check `docker compose … logs web`. With sslip.io, certificate issuance can be rate-limited; switch to a DuckDNS name. |
| Uploads stay in *Processing* | Check `docker compose … logs worker`. A document that failed can be retried from its page with **Retry processing**. |
| Forgot the passwords | They are in `.env.production` (`DEMO_PASSWORD`, `ADMIN_SEED_PASSWORD`). |
