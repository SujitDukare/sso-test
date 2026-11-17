# Shaw Wealth Partners Dashboard

A Flask-based portfolio analytics dashboard powered by Snowflake.

## Prerequisites

- Python 3.11+
- Access to a Snowflake account with the `SHAW_PARTNERS` schema views

## Setup

1. **Configure Snowflake credentials**

   ```bash
   cp .env.example .env
   # Edit .env with your Snowflake connection details
   ```

2. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

3. **Run the app**

   ```bash
   python app.py
   ```

   The dashboard will be available at `http://localhost:5000`.

## Docker

```bash
docker build -t shaw-wealth-dashboard .
docker run -p 5000:5000 --env-file .env shaw-wealth-dashboard
```

## Snowflake Views

The app reads from these views in `WEALTH_MANAGEMENT.SHAW_PARTNERS`:

| View | Purpose |
|------|---------|
| VW_ACCOUNT_MASTER | Account metadata, advisors, risk profiles, targets |
| VW_PORTFOLIO_MONTHLY_PERF_RISK | Monthly performance, returns, risk metrics |
| VW_PORTFOLIO_HOLDINGS | Current holdings and asset allocation |
| VW_PORTFOLIO_MONTHLY_METRICS | Gains, dividends, fees, cash flows |
| VW_PORTFOLIO_MONTHLY_PERF_ATTRIBUTION | Sector/security performance attribution |
| VW_SECURITY_MASTER | Security reference data |

## Configuration

All configuration is via environment variables (`.env` file):

| Variable | Description |
|----------|-------------|
| SNOWFLAKE_ACCOUNT | Snowflake account identifier |
| SNOWFLAKE_USER | Login username |
| SNOWFLAKE_PASSWORD | Login password |
| SNOWFLAKE_WAREHOUSE | Compute warehouse |
| SNOWFLAKE_DATABASE | Database name (default: WEALTH_MANAGEMENT) |
| SNOWFLAKE_SCHEMA | Schema name (default: SHAW_PARTNERS) |
| SNOWFLAKE_ROLE | Snowflake role |

Data is cached for 5 minutes to minimize Snowflake queries.
