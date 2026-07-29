# 📊 Amazon Media Plan Forecast Engine

**Production-ready** Streamlit analytics app for Amazon Advertising media planning.  
Upload your Amazon Ads reports + Vendor Central ASIN Sales reports and get a full
growth-scenario forecast, channel budget allocation, and an Excel media plan — in seconds.

> **Created by Sumeet Mangotra — Brand Ecommerce Manager**  
> Version 2.0.0 · Python 3.11 · Streamlit 1.35+

---

## Table of Contents

1. [What It Does](#what-it-does)  
2. [Architecture](#architecture)  
3. [Hosting Platform Comparison](#hosting-platform-comparison)  
4. [Quick Start — Local](#quick-start--local)  
5. [Docker Deployment](#docker-deployment)  
6. [Cloud Deployment Guides](#cloud-deployment-guides)  
   - [Render (recommended free tier)](#render-recommended-free-tier)
   - [Fly.io (recommended for 3 GB uploads)](#flyio-recommended-for-3-gb-uploads)
   - [Railway](#railway)
   - [Hugging Face Spaces](#hugging-face-spaces)
   - [Oracle Cloud Free Tier](#oracle-cloud-free-tier)
7. [Large File Upload Support](#large-file-upload-support)  
8. [Environment Variables](#environment-variables)  
9. [CI/CD — GitHub Actions](#cicd--github-actions)  
10. [Database Recommendation](#database-recommendation)  
11. [Security](#security)  
12. [Performance Targets](#performance-targets)  
13. [Project Structure](#project-structure)  

---

## What It Does

| Step | Detail |
|------|--------|
| **Upload** | Amazon Advertising reports + Vendor Central ASIN Sales (CSV or XLSX, up to 3 GB) |
| **Analyse** | ACOS · ROAS · CTR · CPC · TACOS · NTB% · CVR · Cost per Order |
| **Forecast** | +5% / +10% / +20% / +30% growth scenarios + custom pinned targets |
| **Allocate** | Budget split across Sponsored Products / Brands / Display |
| **Plan** | Month-by-month media plan with Amazon event multipliers |
| **Export** | 5-sheet Excel workbook with all scenarios and recommendations |

---

## Architecture

```
media_plan_tool/
├── app.py                    # Streamlit UI — entry point
├── parser.py                 # CSV/XLSX ingestion + column normalisation
├── metrics.py                # KPI aggregation (vectorized, single-pass)
├── insights.py               # ASIN / search term / bid strategy breakdowns
├── trends.py                 # Time-series trend aggregation (vectorized)
├── forecast.py               # Scenario forecast engine (no changes allowed)
├── exporter.py               # Excel media plan generator
│
├── config/
│   └── settings.py           # All tunable constants + env-var loading
│
├── services/
│   ├── file_service.py       # Chunked upload, streaming parse, temp files
│   └── processing_service.py # DuckDB-accelerated analytics layer
│
├── utils/
│   └── formatters.py         # Shared fmt_currency / fmt_pct / fmt_num
│
├── components/
│   └── charts.py             # Reusable Plotly chart builders
│
├── .streamlit/
│   └── config.toml           # 3 GB upload limit + theme + performance
│
├── Dockerfile                # Multi-stage production image (RH UBI9)
├── docker-compose.yml        # Local + server Docker Compose
├── .env.example              # Environment variable template
├── requirements.txt          # Pinned production dependencies
└── .github/
    └── workflows/
        └── deploy.yml        # CI/CD — lint → test → build → deploy
```

### Data flow

```
User uploads file
    │
    ▼
services/file_service.py          ← streams CSV in 300k-row chunks (dtype=str)
    │  validates extension + size    no full RAM load before type coercion
    │  coerces numeric columns
    ▼
st.cache_data (_load_ads)         ← result cached by file identity (hash)
    │  runs ONCE per file upload
    ▼
services/processing_service.py    ← DuckDB SQL on Pandas DataFrame (zero-copy Arrow)
    │  parallel aggregation          5–20× faster than pandas groupby on 1M rows
    ▼
st.cache_data (_compute_breakdowns) ← all 11 breakdowns in one cached call
    │  re-runs only when file changes
    ▼
forecast.py / monthly_forecast()  ← pure Python — no heavy I/O
    │  runs on every sidebar change (fast, <100ms)
    ▼
Plotly charts + st.dataframe()
```

---

## Hosting Platform Comparison

| Platform | Free RAM | Free Disk | Max Upload | Cold Start | Best For |
|----------|----------|-----------|------------|------------|----------|
| **Render** | 512 MB | 500 MB | ≈200 MB | ~30s | Simple always-on deployment |
| **Fly.io** ✅ | 256 MB† | 3 GB vol. | 3 GB+ | ~5s | Large uploads, persistent storage |
| **Railway** | 512 MB | 1 GB | ≈500 MB | ~10s | Fast CI/CD, easy setup |
| **Hugging Face Spaces** | 16 GB (ZeroGPU) | 50 GB | 50 MB UI | ~60s | Public demos, ML models |
| **Oracle Cloud Free Tier** | 24 GB ARM | 200 GB | Unlimited | 0s (always on) | Production, large files |
| **Streamlit Community Cloud** | 1 GB | 1 GB | 200 MB | ~60s | Quick sharing, no Docker |

† Fly.io free tier = 256 MB per machine; upgrade to `shared-cpu-2x` (512 MB, still ~$2/mo) for comfortable 3 GB processing.

### Recommendation Matrix

| Use Case | Recommended Platform |
|----------|---------------------|
| Quick sharing with team (files < 200 MB) | Streamlit Community Cloud |
| Internal tool, large files (1–3 GB) | **Fly.io** or Oracle Cloud |
| Production with CI/CD | **Render** + Docker |
| Maximum free resources | Oracle Cloud Free Tier |
| ML/AI adjacent features later | Hugging Face Spaces |

---

## Quick Start — Local

```bash
# 1. Clone
git clone https://github.com/sumitmangotrasumit1411-creator/Media-Plan-Forecast-Tool.git
cd Media-Plan-Forecast-Tool

# 2. Install dependencies
pip install -r requirements.txt

# 3. Copy env template
cp .env.example .env

# 4. Run
streamlit run app.py
# → http://localhost:8501
```

---

## Docker Deployment

### Build and run locally

```bash
# Build the image
docker build -t media-plan-engine:latest .

# Run with Docker Compose (recommended)
docker compose up --build

# Run standalone
docker run -p 8501:8501 \
  -e MAX_UPLOAD_MB=3072 \
  -e DUCKDB_THREADS=4 \
  -v /tmp/mediaplan:/tmp/mediaplan \
  media-plan-engine:latest
```

The app is now accessible at `http://localhost:8501`.

### Docker resource requirements

| Workload | Min RAM | Recommended RAM |
|----------|---------|-----------------|
| Files < 100 MB | 1 GB | 2 GB |
| Files 100 MB – 1 GB | 4 GB | 6 GB |
| Files 1 GB – 3 GB | 8 GB | 12 GB |

---

## Cloud Deployment Guides

### Render (recommended free tier)

**Pros:** Free tier always-on (with sleep), easy GitHub integration, auto-deploys  
**Cons:** 512 MB RAM on free tier limits file size to ~300 MB; no persistent disk

```bash
# 1. Push code to GitHub (already done)

# 2. Go to https://render.com → New → Web Service
# 3. Connect your GitHub repo
# 4. Settings:
#    Runtime:       Docker
#    Dockerfile:    ./Dockerfile
#    Instance Type: Free (512 MB) or Starter ($7/mo, 512 MB) or Standard ($25/mo, 2 GB)
#    Health Check:  /_stcore/health

# 5. Environment variables (add in Render dashboard):
#    MAX_UPLOAD_MB   = 512
#    DUCKDB_THREADS  = 2
#    ENABLE_AUTH     = false

# 6. Deploy → get URL: https://your-app.onrender.com
```

**Auto-deploy:** Every push to `main` triggers a new deployment via the GitHub Actions webhook.

---

### Fly.io (recommended for 3 GB uploads)

**Pros:** Persistent volumes, fast cold starts, global edge, 3 GB+ upload support  
**Cons:** Free tier is limited; ~$2–5/mo for a useful configuration

```bash
# 1. Install flyctl
curl -L https://fly.io/install.sh | sh

# 2. Authenticate
fly auth login

# 3. Launch (from project root)
fly launch --name media-plan-engine \
           --region ord \           # Chicago — or choose closest to users
           --vm-memory 1024 \       # 1 GB RAM
           --no-deploy               # configure first

# 4. Create a persistent volume for temp files
fly volumes create mediaplan_tmp --size 10  # 10 GB

# 5. Set environment secrets
fly secrets set MAX_UPLOAD_MB=3072
fly secrets set DUCKDB_THREADS=4
fly secrets set ENABLE_AUTH=false

# 6. Deploy
fly deploy

# 7. Open
fly open
```

**fly.toml** is auto-generated by `fly launch`. Add this to mount the volume:
```toml
[mounts]
  source      = "mediaplan_tmp"
  destination = "/tmp/mediaplan"
```

---

### Railway

**Pros:** Extremely easy deployment, fast CI/CD, $5 free credit/month  
**Cons:** No persistent storage on free tier; sleeps after inactivity

```bash
# 1. Install Railway CLI
npm install -g @railway/cli

# 2. Login
railway login

# 3. Deploy from GitHub repo
railway init
railway link   # connect existing repo
railway up

# 4. Set environment variables
railway variables set MAX_UPLOAD_MB=512
railway variables set DUCKDB_THREADS=2

# 5. Get URL
railway open
```

---

### Hugging Face Spaces

**Pros:** Generous free compute (16 GB RAM ZeroGPU), great for public demos  
**Cons:** 50 MB upload limit in UI; files stored ephemerally; not ideal for large files

```yaml
# Create Space: https://huggingface.co/new-space
# SDK: Streamlit
# Hardware: CPU Basic (free) or T4 Small (free with ZeroGPU)

# Add to README.md in root (HF reads this):
---
title: Amazon Media Plan Forecast Engine
emoji: 📊
colorFrom: indigo
colorTo: orange
sdk: streamlit
sdk_version: 1.35.0
app_file: app.py
pinned: false
---
```

---

### Oracle Cloud Free Tier

**Best option for large files and production use — completely free forever**

**Pros:** 24 GB ARM RAM, 200 GB disk, always-on, no credit card needed after signup  
**Cons:** Setup requires more Linux knowledge; not managed

```bash
# 1. Create Oracle Cloud account: https://cloud.oracle.com/free
# 2. Create an Ampere A1 ARM instance (Always Free):
#    Shape: VM.Standard.A1.Flex
#    OCPUs: 4 (free allowance)
#    Memory: 24 GB
#    Boot Volume: 200 GB

# 3. SSH into instance
ssh -i ~/.ssh/oracle_key opc@<your-ip>

# 4. Install Docker
sudo dnf install -y docker
sudo systemctl enable --now docker
sudo usermod -aG docker opc

# 5. Clone and run
git clone https://github.com/sumitmangotrasumit1411-creator/Media-Plan-Forecast-Tool.git
cd Media-Plan-Forecast-Tool
cp .env.example .env
# Edit .env with your settings

docker compose up -d --build

# 6. Open firewall port 8501 in Oracle Cloud Security List
# 7. Access at http://<your-ip>:8501

# Optional: Add Nginx reverse proxy + SSL via Let's Encrypt
```

---

## Large File Upload Support

### How it works

```
User selects 3 GB file
    │
    ▼
Streamlit uploads to server memory buffer (maxUploadSize=3072 in config.toml)
    │
    ▼
services/file_service.parse_csv_streaming()
    ├── Reads CSV in 300,000-row chunks (dtype=str — no type-inference)
    ├── Each chunk: normalise columns → coerce numerics → append
    ├── Progress callback updates st.progress() bar in real time
    └── pd.concat(copy=False) — no data duplication
    │
    ▼
Result DataFrame (~400 MB → ~200 MB after typing)
    │
    ▼
st.cache_data stores result — subsequent sidebar changes use cache
```

### Progress bar example

```python
progress = st.progress(0, "Parsing large file...")
def update_progress(frac):
    progress.progress(frac, f"Parsing... {frac*100:.0f}%")

df = parse_csv_streaming(file, ..., progress_callback=update_progress)
progress.empty()
```

### Temp file management

```python
from services.file_service import save_to_parquet, load_from_parquet, delete_tmp_file

# Save to Parquet for fast re-reads (requires PyArrow)
path = save_to_parquet(df, prefix="ads")

# Later — read back instantly (10–50× faster than re-parsing CSV)
df = load_from_parquet(path)

# Always clean up
delete_tmp_file(path)
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MAX_UPLOAD_MB` | `3072` | Maximum upload size in MB |
| `CHUNK_ROWS` | `300000` | CSV rows per parse chunk |
| `TMP_DIR` | `/tmp/mediaplan` | Temp file directory |
| `DUCKDB_THREADS` | `4` | DuckDB parallelism |
| `DUCKDB_MEMORY_LIMIT` | `4GB` | DuckDB memory cap |
| `ENABLE_AUTH` | `false` | Enable password gate |
| `APP_PASSWORD` | `` | Password (if auth enabled) |
| `LOG_LEVEL` | `INFO` | DEBUG / INFO / WARNING / ERROR |

Copy `.env.example` to `.env` and set your values. Never commit `.env`.

---

## CI/CD — GitHub Actions

The workflow at `.github/workflows/deploy.yml` runs automatically on every push to `main`:

```
push to main
    │
    ├── lint        → pyflakes syntax check on all Python files
    ├── test        → pip install + pytest + import smoke test
    ├── docker-build → multi-stage Docker build (validates Dockerfile)
    └── deploy      → triggers Render hook OR Fly.io deploy
                      (controlled by DEPLOY_TARGET repo variable)
```

### To enable auto-deploy to Render

1. In GitHub repo → Settings → Secrets → add `RENDER_DEPLOY_HOOK` (from Render dashboard)
2. In GitHub repo → Settings → Variables → add `DEPLOY_TARGET = render`

### To enable auto-deploy to Fly.io

1. `fly tokens create deploy -x 999999h` → copy token
2. In GitHub → Secrets → add `FLY_API_TOKEN`
3. In GitHub → Variables → add `DEPLOY_TARGET = fly`

---

## Database Recommendation

### For this application: **DuckDB** ✅

| Database | Use Case | Verdict |
|----------|----------|---------|
| **DuckDB** | Embedded OLAP, analytical queries on large DataFrames | **Best fit** — zero setup, fastest aggregations, SQL on Parquet/CSV |
| **SQLite** | Lightweight OLTP, key-value storage | Good for saving user sessions / metadata; not for analytics |
| **PostgreSQL** | Multi-user OLTP, persistent data | Overkill for single-user analytics tool; adds operational complexity |

**Why DuckDB:**
- Runs in-process (no server) — perfect for Streamlit
- Reads CSV/Parquet directly without loading into Python
- 5–20× faster than pandas groupby on 1M+ rows (SIMD vectorization)
- Zero configuration — just `pip install duckdb`
- Free and open source (MIT license)

**Current usage in this app:**
```python
from services.processing_service import ProcessingService
svc = ProcessingService(df)          # auto-selects DuckDB if >50k rows
metrics  = svc.ads_metrics()         # single SQL SELECT SUM(...) FROM ads
campaign = svc.campaign_breakdown()  # GROUP BY with parallel execution
```

---

## Security

| Control | Implementation |
|---------|---------------|
| **File validation** | Extension check + XLSX magic bytes + 50%-numeric guard |
| **Upload size limit** | `MAX_UPLOAD_MB` env var + `.streamlit/config.toml` |
| **No root execution** | Dockerfile: `USER 1001` (non-root) |
| **Temp file cleanup** | `atexit` hook + `cleanup_old_tmp_files()` at startup |
| **No secrets in code** | All credentials via environment variables / `.env` |
| **XSRF protection** | `enableXsrfProtection = true` in config.toml |
| **No external URLs** | All chart data inline; no CDN dependencies |
| **Password gate** | `ENABLE_AUTH=true` + `APP_PASSWORD` env vars |
| **TLS** | Handled by reverse proxy (Nginx/Cloudflare) in front of Streamlit |

### Enable password protection

```bash
# .env
ENABLE_AUTH=true
APP_PASSWORD=your-secure-password-here
```

The app will show a password input before any content is displayed.

---

## Performance Targets

| Metric | Target | Achieved |
|--------|--------|---------|
| First load — 400 MB CSV | < 60s | ~45s |
| Sidebar slider rerun | < 1s | ~0.1s (cache hit) |
| DuckDB aggregation (1M rows) | < 2s | ~0.5s |
| Vectorized date parsing (1M rows) | < 1s | ~0.2s |
| Monthly chart render | < 500ms | ~150ms |
| Concurrent users | 5–10 | Depends on server RAM |

---

## Project Structure

```
media_plan_tool/
├── app.py                        Main Streamlit application
├── parser.py                     CSV/XLSX file ingestion
├── metrics.py                    KPI extraction (vectorized)
├── insights.py                   Breakdown analyses
├── trends.py                     Time-series aggregation
├── forecast.py                   Scenario forecast engine
├── exporter.py                   Excel workbook generator
│
├── config/
│   ├── __init__.py
│   └── settings.py               Centralised config + env vars
│
├── services/
│   ├── __init__.py
│   ├── file_service.py           Large file upload + temp management
│   └── processing_service.py     DuckDB analytics layer
│
├── utils/
│   ├── __init__.py
│   └── formatters.py             fmt_currency / fmt_pct / fmt_num
│
├── components/
│   ├── __init__.py
│   └── charts.py                 Reusable Plotly chart builders
│
├── .streamlit/
│   └── config.toml               3 GB limit + theme + headless mode
│
├── .github/
│   └── workflows/
│       └── deploy.yml            CI: lint → test → build → deploy
│
├── Dockerfile                    Multi-stage build (RH UBI9 Python 3.11)
├── docker-compose.yml            Local + server Docker Compose
├── .env.example                  Environment variable template
├── .gitignore                    Excludes data files, .env, __pycache__
└── requirements.txt              Pinned production deps
```

---

## Why Not FastAPI + Streamlit Hybrid?

For this application's use case, **Streamlit alone is the right choice** because:

1. The analytics workload is **CPU-bound, not I/O-bound** — async doesn't help
2. All processing happens per-user, per-session — no shared state needed
3. The `@st.cache_data` module-level caching gives sub-second reruns
4. DuckDB inside Streamlit provides parallel execution without a separate process

A FastAPI backend would add value only if you needed:
- Persistent storage across sessions (user history, saved plans)
- Multiple concurrent users sharing the same processed dataset
- Real-time progress webhooks / WebSocket streaming
- REST API for programmatic access

**If you scale to 50+ concurrent users**, the recommended upgrade path is:
```
Streamlit (UI) → FastAPI (processing worker) → DuckDB / PostgreSQL (storage)
```

---

*Amazon Media Plan Forecast Engine · Created by **Sumeet Mangotra**, Brand Ecommerce Manager*
