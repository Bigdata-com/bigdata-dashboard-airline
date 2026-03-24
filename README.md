# Global Airlines — Iran Conflict Exposure Dashboard

Live interactive dashboard tracking 50 global airline carriers' energy cost
resilience during the Iran conflict, powered by Bigdata.com.

## 🔴 Live Dashboard

👉 **https://Bigdata-com.github.io/bigdata-dashboard-airline/**

## How It Works

1. **Claude Cowork** runs a scheduled task every x hours
2. Calls **Bigdata.com MCP** to search 180 days of SEC filings, earnings
   transcripts, and financial news for all 50 airlines
3. Extracts fuel cost/ASM, revenue/ASM, hedging positions, Iran impact data
4. Generates a self-contained React dashboard (all data baked in, no backend)
5. Pushes to this repo → GitHub Actions deploys to GitHub Pages

## Coverage

50 airlines across 6 regions: US, Europe, MENA, Asia, Oceania, LATAM.
Includes both public and private carriers.

## Configuration

Edit `config/tickers.json` to change airlines, scenarios, or parameters.

## Data Sources

- SEC 10-K / 6-K filings (Edgar)
- Earnings call transcripts (Quartr, FactSet)
- Financial news (Reuters, Bloomberg, FT, CNBC, etc.)
- All sourced via Bigdata.com MCP tools