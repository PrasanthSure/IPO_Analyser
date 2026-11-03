# IPO Automation & Analysis Platform

## Run
    docker compose up -d
    cd backend && python -m venv .venv && source .venv/bin/activate
    pip install -r requirements.txt && playwright install chromium
    cp ../.env.example .env   # fill in values
    uvicorn app.main:app --reload
Docs: http://localhost:8000/docs  ·  trigger jobs manually: POST /admin/run/{list|snap|score|watch}

## Build order
1. Pick sources, fill IPO_LIST_URL / GMP_URL, fix column mappings in scrapers/ipo_sources.py
2. Add a fundamentals scraper (revenue growth, D/E, PE) -> fills IPO fields
3. Tune screener.CONFIG; backtest against past listings (listing gain %)
4. React dashboard (Vite): table, compare view, GMP/subscription charts (Recharts), watchlist form
5. Telegram bot token + SMTP creds, test alerts
6. Dockerise backend, deploy (Railway/Render), add tests + README screenshots
