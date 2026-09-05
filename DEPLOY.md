# Deploying QRIP

## Why Netlify alone will not work

Netlify is a static host. It serves files and runs short serverless functions;
it does not run a persistent process. QRIP needs one for four reasons:

| What QRIP does | Why Netlify can't |
|---|---|
| Runs a Python HTTP server | Netlify Functions support JavaScript, TypeScript and Go — not Python |
| Keeps state in SQLite (`data/qrip.db`) | Serverless filesystems are ephemeral and per-invocation; the database would vanish between requests |
| Runs analysis on a background thread and polls for progress | A function ends when it returns; nothing survives to finish the job |
| Streams generated PDF/XLSX from memory | Possible in a function, but pointless without the rest |

The frontend, on the other hand, is *ideal* for Netlify: it is plain HTML, CSS
and ES modules with no build step. So you have two sensible options.

---

## Which free hosts actually work

QRIP needs a **process that stays alive**: analysis runs on a background thread
while the browser polls for progress, and state lives in a SQLite file. Anything
serverless (Netlify, Vercel, Cloudflare Workers, Deno Deploy, AWS Lambda) fails
on both counts — the function ends when it returns, and the filesystem is
per-invocation.

That leaves these. Free-tier terms change constantly, so check current pricing
before committing to one.

| Host | Free? | Data survives redeploy? | Notes |
|---|---|---|---|
| **Render** | Yes | **No** (disks are paid) | Easiest. Sleeps after ~15 min, ~50 s cold start. `render.yaml` included. |
| **Fly.io** | Small always-free allowance, card required | **Yes** — free 3 GB volume | Best free option that keeps data. Scales to zero, wakes in seconds. `fly.toml` included. |
| **Hugging Face Spaces** | Yes, genuinely | No (ephemeral unless you pay for storage) | Docker Space, uses this repo's `Dockerfile`. Sleeps when idle. Odd home for a business tool but it works. |
| **Koyeb** | One free web service | No | Deploys from the Dockerfile. |
| **Oracle Cloud Always Free** | Yes, permanently | **Yes** — a real disk | A real VM (generous ARM allowance). Nothing sleeps, nothing resets. You manage the box: systemd unit + Caddy for TLS. Most work, best result. |
| **Your own machine + Cloudflare Tunnel** | Yes | Yes (it's your disk) | `cloudflared tunnel --url http://localhost:8000` gives a public HTTPS URL in seconds. Only up while your PC is on — good for showing someone today. |

### Fly.io, step by step

Install [flyctl](https://fly.io/docs/flyctl/install/), then from this folder:

```bash
fly launch --no-deploy --copy-config
```

```bash
fly volumes create qrip_data --size 1
```

```bash
fly secrets set QRIP_SECRET=$(python -c "import secrets;print(secrets.token_hex(32))")
```

```bash
fly deploy
```

`fly.toml` already mounts the volume at `/data` and points `QRIP_DATA_DIR` there,
so your projects survive every deploy — which the free Render tier cannot do.

### Hugging Face Spaces, step by step

1. [huggingface.co/new-space](https://huggingface.co/new-space) → SDK **Docker**
   → blank template.
2. In the Space's **Settings → Variables and secrets**, add a secret
   `QRIP_SECRET` (any long random string).
3. Push this repo to the Space's git remote. The Space builds the `Dockerfile`
   as-is; add `app_port: 8000` to the Space README's frontmatter so it routes to
   the right port.

### Cloudflare Tunnel (fastest way to show someone)

With QRIP already running locally on port 8000:

```bash
cloudflared tunnel --url http://localhost:8000
```

It prints a public `https://*.trycloudflare.com` URL. No account, no card, no
deploy. It dies when you close the terminal.

---

## Option A — everything on one host (simplest)

One service serves both the API and the frontend, exactly as it does locally.
No CORS, no second deployment, one URL.

**Render** (you already use it for the original QRIP):

1. Push this repo to GitHub.
2. Render dashboard → **New → Blueprint** → pick the repo. It reads
   [`render.yaml`](render.yaml).
3. Deploy. That's it — there are no dependencies to install.

The blueprint already sets:

- `QRIP_SECRET` — generated for you, so tokens survive deploys
- `QRIP_DATA_DIR=/var/qrip` with a 1 GB disk mounted there, so the database
  survives deploys
- a health check on `/api/health`

The same repo runs unchanged on **Railway**, **Fly.io**, **Heroku** (via
[`Procfile`](Procfile)), or any box with Python 3.10+ — and there is a
[`Dockerfile`](Dockerfile) if you would rather ship a container:

```bash
docker build -t qrip .
docker run -p 8000:8000 -v qrip-data:/data -e QRIP_SECRET=$(openssl rand -hex 32) qrip
```

**Free-tier caveat:** Render's free web services sleep after inactivity and cold
start in ~50 s. The analysis itself takes under a second; the wait is the
container waking. A paid instance or a scheduled ping removes it.

---

## Option B — frontend on Netlify, API elsewhere

Keep Netlify if you want it for the frontend. Deploy the API using Option A
first, then pick one of these two wirings.

### B1 — proxy through Netlify (recommended: no CORS)

In [`netlify.toml`](netlify.toml), replace the placeholder host:

```toml
[[redirects]]
  from = "/api/*"
  to = "https://your-api.onrender.com/api/:splat"
  status = 200
  force = true
```

Leave `<meta name="qrip-api-base">` in `frontend/index.html` empty. The browser
only ever talks to your Netlify origin, so no CORS configuration is needed on
the backend at all.

### B2 — call the API directly (needs CORS)

1. In `frontend/index.html`:
   ```html
   <meta name="qrip-api-base" content="https://your-api.onrender.com">
   ```
   (with or without a trailing `/api` — both work)
2. On the backend, allow your Netlify origin:
   ```
   QRIP_ALLOWED_ORIGINS=https://your-site.netlify.app
   ```
   Comma-separate multiple origins. Preflight `OPTIONS` and the
   `Content-Disposition` header (so PDF/XLSX downloads keep their filenames) are
   handled for you.

Netlify build settings, if you configure it in the UI instead of the TOML:
publish directory `frontend`, build command empty.

---

## Environment variables

| Variable | Purpose |
|---|---|
| `PORT` | Set by the host. The server binds `0.0.0.0` automatically when it is present. |
| `QRIP_SECRET` | Signs auth tokens. **Set this in production** — otherwise a key file is used, and on an ephemeral disk every deploy signs all users out. |
| `QRIP_DATA_DIR` | Where `qrip.db` and uploads live. Point it at a mounted disk. |
| `QRIP_ALLOWED_ORIGINS` | Comma-separated origins allowed to call the API cross-origin. Unset = same-origin only. |
| `GOOGLE_MAPS_API_KEY` | Official Places API for review URLs (max 5 reviews per place). |
| `SERPAPI_KEY` / `OUTSCRAPER_KEY` | Full Google review history for the review tool. |
| `ANTHROPIC_API_KEY` | Optional: Claude re-reads each coded segment. Also add `pip install anthropic` to the build command. |
| `QRIP_LLM=off` | Force the offline engine even when a key is present. |

## Before you go live

- **Set `QRIP_SECRET`.** Everything else is a convenience; this one is auth.
- **Mount a disk** (or accept that data resets on each deploy).
- **Drop `--demo`** from the start command once you have real data — it is
  idempotent, so it is harmless, but it seeds a `demo@qrip.local` account with a
  known password. Delete that account in production.
- **The first account created becomes the workspace owner**, seeing every
  project and the usage ledger. Register yours immediately after deploying.
- QRIP serves over plain HTTP and expects the platform to terminate TLS in front
  of it. Render, Railway, Fly and Heroku all do. Do not expose it directly.
- SQLite with a threaded server is fine for a team; it is not built for hundreds
  of concurrent writers.
