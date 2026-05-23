# CB Monitor

**Convertible Bond Redemption Calendar & Market Data Tool**

A lightweight, single-person-operable SaaS for tracking China A-share convertible bond (可转债) forced redemption events, with market-wide ranking and data exploration.

Built with [Akshare](https://github.com/akfamily/akshare) (wraps Jisilu, East Money, and exchange public APIs) — no paid data sources required.

> **Disclaimer:** For reference only. Not financial advice.

## Features

### Implemented
- **Redemption Calendar** — Track forced redemption (强赎), put option (回售), and maturity (到期) events with countdown timers. Color-coded urgency (≤3d red, ≤10d yellow).
- **Market Ranking** — Full convertible-bond market snapshot with sortable columns: premium rate, YTM, remaining size, rating, redemption progress.
- **Bond Detail Page** — Individual bond view with key metrics and redemption status.
- **Multi-language** — English default; auto-switches to Chinese for mainland China IPs. Bond codes shown instead of Chinese names in English mode. Manual toggle via cookie.
- **Dark Theme** — Bloomberg Terminal-inspired dark theme (`#0a0a0a` background, emerald accents). Cookie-based persistence, default dark.

### Data Sources
| Source | Data | Frequency |
|--------|------|-----------|
| Akshare (Jisilu) | Premium rate, YTM, rating, redemption tracking | 4× daily |
| Akshare (East Money) | Full-market spot pricing (~347 bonds) | 4× daily |
| Exchange Announcements | Redemption event details | On detection |

### Tech Stack
| Layer | Technology |
|-------|-----------|
| Backend | Python FastAPI + APScheduler |
| Database | SQLite (dev) / PostgreSQL (prod) via SQLAlchemy |
| Frontend | Jinja2 templates + Tailwind CSS (CDN) |
| i18n | Cookie > Accept-Language > IP geo (ip-api.com) |
| Deployment | Docker / AWS EC2 |

## Quick Start

```bash
# 1. Install dependencies
# On Windows, use --only-binary to avoid C++ compiler issues:
pip install -r backend/requirements.txt --only-binary :all: -i https://pypi.tuna.tsinghua.edu.cn/simple

# 2. Seed data (fetches live market data)
python scripts/seed_data.py

# 3. Run
cd backend && uvicorn main:app --reload --port 8000

# 4. Open
open http://localhost:8000
```

## API Endpoints

| Route | Description |
|-------|-------------|
| `GET /` | Homepage with upcoming redemptions |
| `GET /calendar` | Full redemption calendar |
| `GET /ranking` | Market-wide bond ranking table |
| `GET /bond/{code}` | Single bond detail page |
| `GET /api/redemptions` | JSON: active redemption events |
| `GET /api/bonds` | JSON: bond market snapshot |
| `POST /api/set-lang` | Set language cookie |
| `GET /health` | Health check |

## Deployment (AWS EC2)

1. Launch `t4g.nano` (free-tier eligible) with Ubuntu 24.04.
2. Install Docker:
   ```bash
   sudo apt update && sudo apt install docker.io docker-compose-v2 -y
   ```
3. Deploy:
   ```bash
   git clone <your-repo> cb-monitor
   cd cb-monitor/deploy
   sudo docker compose up -d
   ```

## Project Structure

```
cb-monitor/
├── backend/
│   ├── main.py              # FastAPI entry point
│   ├── config.py            # Environment configuration
│   ├── database.py          # SQLAlchemy models + async engine
│   ├── i18n.py              # Internationalization (EN/ZH)
│   ├── routers/
│   │   ├── pages.py         # HTML page routes
│   │   └── api.py           # JSON API routes
│   ├── services/
│   │   ├── collector.py     # Akshare data collection
│   │   └── detector.py      # Redemption event detection
│   ├── locales/             # Translation JSON files
│   └── templates/           # Jinja2 HTML templates
├── scripts/
│   ├── init_db.py           # Create tables
│   └── seed_data.py         # Fetch and store live data
├── deploy/
│   ├── Dockerfile
│   └── docker-compose.yml
└── README.md
```

## Roadmap

### Phase 1 — Core Infrastructure (MVP delivered ✓)
- [x] Redemption calendar + countdown
- [x] Market ranking with sorting
- [x] Multi-language (EN/ZH)
- [x] Bloomberg dark theme

### Phase 2 — Scheduled Collection & Alerts (current)
- [ ] **Scheduled data collection** — APScheduler for 4× daily market refresh
- [ ] **Watchlist + email alerts** — Users pin bonds, get notified on redemption triggers
- [ ] **Premium rate alerts** — Notify when premium rate drops below 0% (arbitrage opportunity)
- [ ] **Ranking filters** — Filter by rating, premium rate range, remaining size

### Phase 3 — Value-Add (future)
- [ ] Daily email digest — morning summary of today's last-trade dates
- [ ] User accounts (email-based, no signup friction)
- [ ] Historical price / premium-rate charts
- [ ] Mobile-responsive optimization
