# #!/usr/bin/env python3
# """Shaw Wealth Partners — Flask Dashboard Application (Snowflake backend)."""

# import os
# import math
# import time
# import logging

# import pandas as pd
# import numpy as np
# import snowflake.connector
# from dotenv import load_dotenv
# from flask import Flask, render_template, request

# load_dotenv()

# app = Flask(__name__)
# logging.basicConfig(level=logging.INFO)
# logger = logging.getLogger(__name__)

# # ── Snowflake connection ─────────────────────────────────────────────────────

# SF_CONFIG = {
#     "account": os.getenv("SNOWFLAKE_ACCOUNT", ""),
#     "user": os.getenv("SNOWFLAKE_USER", ""),
#     "password": os.getenv("SNOWFLAKE_PASSWORD", ""),
#     "warehouse": os.getenv("SNOWFLAKE_WAREHOUSE", ""),
#     "database": os.getenv("SNOWFLAKE_DATABASE", "WEALTH_MANAGEMENT"),
#     "schema": os.getenv("SNOWFLAKE_SCHEMA", "SHAW_PARTNERS"),
#     "role": os.getenv("SNOWFLAKE_ROLE", ""),
# }

# CACHE_TTL = 300  # 5 minutes
# _cache = {"data": None, "ts": 0}


# def get_sf_connection():
#     """Create a new Snowflake connection."""
#     cfg = {k: v for k, v in SF_CONFIG.items() if v}
#     return snowflake.connector.connect(**cfg)


# def sf_query(sql: str) -> pd.DataFrame:
#     """Execute a SQL query against Snowflake and return a DataFrame."""
#     conn = get_sf_connection()
#     try:
#         cur = conn.cursor()
#         cur.execute(sql)
#         cols = [desc[0] for desc in cur.description]
#         rows = cur.fetchall()
#         return pd.DataFrame(rows, columns=cols)
#     finally:
#         conn.close()


# # ── Load data from Snowflake ────────────────────────────────────────────────

# def load_data():
#     """Fetch all required data from Snowflake views into DataFrames."""
#     logger.info("Loading data from Snowflake...")

#     d = {}

#     # Account master
#     d["accounts"] = sf_query("SELECT * FROM VW_ACCOUNT_MASTER")

#     # Monthly performance & risk
#     d["perf_risk"] = sf_query("SELECT * FROM VW_PORTFOLIO_MONTHLY_PERF_RISK")
#     d["perf_risk"]["MONTH_END_DATE"] = pd.to_datetime(d["perf_risk"]["MONTH_END_DATE"])

#     # Holdings (latest date only for allocation)
#     d["holdings"] = sf_query("""
#         SELECT * FROM VW_PORTFOLIO_HOLDINGS
#         WHERE HOLDING_DATE = (SELECT MAX(HOLDING_DATE) FROM VW_PORTFOLIO_HOLDINGS)
#     """)

#     # Monthly metrics (for gains & dividends)
#     d["metrics"] = sf_query("SELECT * FROM VW_PORTFOLIO_MONTHLY_METRICS")
#     d["metrics"]["MONTH_END_DATE"] = pd.to_datetime(d["metrics"]["MONTH_END_DATE"])

#     # Attribution (latest month, sector level)
#     d["attribution"] = sf_query("""
#         SELECT * FROM VW_PORTFOLIO_MONTHLY_PERF_ATTRIBUTION
#         WHERE MONTH_END_DATE = (SELECT MAX(MONTH_END_DATE) FROM VW_PORTFOLIO_MONTHLY_PERF_ATTRIBUTION)
#           AND ATTRIBUTION_LEVEL = 'SECTOR'
#     """)

#     logger.info("Data loaded successfully.")
#     return d


# def get_data():
#     """Return cached data, refreshing if stale."""
#     now = time.time()
#     if _cache["data"] is None or (now - _cache["ts"]) > CACHE_TTL:
#         _cache["data"] = load_data()
#         _cache["ts"] = now
#     return _cache["data"]


# # ── Filtering ────────────────────────────────────────────────────────────────

# def filter_account_ids(data, advisor=None, risk_profile=None):
#     """Return filtered ACCOUNT_IDENTIFIER set."""
#     accts = data["accounts"].copy()
#     if advisor and advisor != "All":
#         accts = accts[accts["ADVISOR_NAME"] == advisor]
#     if risk_profile and risk_profile != "All":
#         accts = accts[accts["RISK_PROFILE"] == risk_profile]
#     return set(accts["ACCOUNT_IDENTIFIER"])


# # ── Dashboard computation ────────────────────────────────────────────────────

# def compute_dashboard(data, account_ids):
#     """Compute all dashboard metrics for a given account subset."""

#     accounts = data["accounts"][data["accounts"]["ACCOUNT_IDENTIFIER"].isin(account_ids)]
#     pr = data["perf_risk"][data["perf_risk"]["ACCOUNT_ID"].isin(account_ids)].copy()
#     holdings = data["holdings"][data["holdings"]["ACCOUNT_ID"].isin(account_ids)]
#     metrics = data["metrics"][data["metrics"]["ACCOUNT_ID"].isin(account_ids)]
#     attribution = data["attribution"][data["attribution"]["ACCOUNT_ID"].isin(account_ids)]

#     latest_date = pr["MONTH_END_DATE"].max()
#     latest_pr = pr[pr["MONTH_END_DATE"] == latest_date]

#     # Latest metrics
#     metrics_latest_date = metrics["MONTH_END_DATE"].max()
#     latest_metrics = metrics[metrics["MONTH_END_DATE"] == metrics_latest_date]

#     # ── KPIs ──────────────────────────────────────────────────────────────

#     total_aum = float(latest_pr["ENDING_MARKET_VALUE_USD"].sum())

#     # Weighted avg YTD return from latest month
#     if total_aum > 0:
#         weighted_ytd = float(
#             (latest_pr["NET_RETURN_YTD"].astype(float) * latest_pr["ENDING_MARKET_VALUE_USD"].astype(float)).sum()
#             / total_aum
#         )
#     else:
#         weighted_ytd = 0.0

#     total_accounts = len(account_ids)

#     unrealized_gains = float(latest_metrics["UNREALIZED_GAIN_USD"].sum())

#     cumulative_dividends = float(metrics["DIVIDEND_INCOME_USD"].sum())

#     # ── AUM growth (monthly total) ────────────────────────────────────────

#     aum_by_month = pr.groupby("MONTH_END_DATE")["ENDING_MARKET_VALUE_USD"].sum().sort_index()
#     aum_dates = [d.strftime("%b %Y") for d in aum_by_month.index]
#     aum_values = [round(float(v) / 1e6, 2) for v in aum_by_month.values]

#     # ── Monthly net returns (AUM-weighted) ────────────────────────────────

#     monthly_ret = []
#     for dt, grp in pr.groupby("MONTH_END_DATE"):
#         emv = grp["ENDING_MARKET_VALUE_USD"].astype(float)
#         nr = grp["NET_RETURN_MONTHLY"].astype(float)
#         tot = emv.sum()
#         w_ret = (nr * emv).sum() / tot if tot > 0 else 0
#         monthly_ret.append({"date": dt, "ret": w_ret})
#     monthly_ret_df = pd.DataFrame(monthly_ret).sort_values("date")
#     ret_dates = [d.strftime("%b %Y") for d in monthly_ret_df["date"]]
#     ret_values = [round(float(r) * 100, 2) for r in monthly_ret_df["ret"]]

#     # ── Asset allocation donut ────────────────────────────────────────────

#     if len(holdings) > 0:
#         alloc_agg = holdings.groupby("ASSET_CLASS").agg(
#             total_mv=("MARKET_VALUE_USD", "sum"),
#             avg_target=("TARGET_PCT", "mean"),
#         ).reset_index()
#         total_mv = alloc_agg["total_mv"].sum()
#         alloc_agg["actual_pct"] = alloc_agg["total_mv"] / total_mv if total_mv > 0 else 0
#         alloc_labels = alloc_agg["ASSET_CLASS"].tolist()
#         alloc_values = [round(float(v) * 100, 1) for v in alloc_agg["actual_pct"]]
#         alloc_targets = [round(float(v) * 100, 1) for v in alloc_agg["avg_target"]]
#     else:
#         alloc_labels, alloc_values, alloc_targets = [], [], []
#         alloc_agg = pd.DataFrame(columns=["ASSET_CLASS", "actual_pct", "avg_target"])

#     # Drift alerts (aggregate)
#     drift_alerts = []
#     if len(alloc_agg) > 0:
#         for _, row in alloc_agg.iterrows():
#             actual = float(row.get("actual_pct", 0)) * 100
#             target = float(row.get("avg_target", 0)) * 100
#             drift = actual - target
#             if abs(drift) > 1.0:
#                 drift_alerts.append({
#                     "asset_class": row["ASSET_CLASS"],
#                     "actual": round(actual, 1),
#                     "target": round(target, 1),
#                     "drift": round(drift, 1),
#                 })

#     # ── Advisor data ──────────────────────────────────────────────────────

#     advisors_list = []
#     for adv_name, grp in accounts.groupby("ADVISOR_NAME"):
#         adv_ids = set(grp["ACCOUNT_IDENTIFIER"])
#         adv_latest = latest_pr[latest_pr["ACCOUNT_ID"].isin(adv_ids)]
#         adv_aum = float(adv_latest["ENDING_MARKET_VALUE_USD"].sum())
#         adv_accounts = len(adv_ids)

#         adv_ytd_vals = adv_latest["NET_RETURN_YTD"].astype(float)
#         adv_avg_ytd = float(adv_ytd_vals.mean()) if len(adv_ytd_vals) > 0 else 0

#         adv_sharpe_vals = adv_latest["SHARPE_RATIO"].astype(float)
#         adv_avg_sharpe = float(adv_sharpe_vals.mean()) if len(adv_sharpe_vals) > 0 else 0

#         accts = []
#         for _, acc_row in grp.iterrows():
#             aid = acc_row["ACCOUNT_IDENTIFIER"]
#             acc_perf = latest_pr[latest_pr["ACCOUNT_ID"] == aid]
#             cl_aum = float(acc_perf["ENDING_MARKET_VALUE_USD"].sum()) if len(acc_perf) > 0 else 0
#             cl_ytd = float(acc_perf["NET_RETURN_YTD"].iloc[0]) if len(acc_perf) > 0 else 0
#             cl_sharpe = float(acc_perf["SHARPE_RATIO"].iloc[0]) if len(acc_perf) > 0 else 0
#             accts.append({
#                 "client_name": acc_row["PRIMARY_OWNER_NAME"],
#                 "risk_profile": acc_row.get("RISK_PROFILE", ""),
#                 "aum": cl_aum,
#                 "ytd": cl_ytd,
#                 "sharpe": cl_sharpe,
#             })

#         advisors_list.append({
#             "name": adv_name,
#             "aum": adv_aum,
#             "accounts": adv_accounts,
#             "avg_ytd": adv_avg_ytd,
#             "avg_sharpe": adv_avg_sharpe,
#             "accts": accts,
#         })

#     # ── Sector contribution ───────────────────────────────────────────────

#     if len(attribution) > 0:
#         sector_agg = attribution.groupby("SECTOR_CODE")["TOTAL_CONTRIBUTION"].sum().reset_index()
#         sector_labels = sector_agg["SECTOR_CODE"].tolist()
#         sector_values = [round(float(v), 3) for v in sector_agg["TOTAL_CONTRIBUTION"]]
#     else:
#         sector_labels, sector_values = [], []

#     # ── Per-client drift flags ────────────────────────────────────────────

#     drift_flags = []
#     if len(holdings) > 0:
#         for aid, h_grp in holdings.groupby("ACCOUNT_ID"):
#             for _, hrow in h_grp.iterrows():
#                 actual_w = float(hrow.get("WEIGHT", 0)) * 100
#                 target_w = float(hrow.get("TARGET_PCT", 0)) * 100
#                 drift_val = actual_w - target_w
#                 if abs(drift_val) > 2.0:
#                     drift_flags.append({
#                         "client": hrow.get("PRIMARY_OWNER_NAME", str(aid)),
#                         "asset_class": hrow.get("ASSET_CLASS", ""),
#                         "actual": round(actual_w, 1),
#                         "target": round(target_w, 1),
#                         "drift": round(drift_val, 1),
#                     })

#     # ── Cumulative returns line chart ─────────────────────────────────────

#     cum_ret = []
#     all_dates = sorted(pr["MONTH_END_DATE"].unique())
#     port_cum = 1.0
#     bench_cum = 1.0
#     for dt in all_dates:
#         grp = pr[pr["MONTH_END_DATE"] == dt]
#         emv = grp["ENDING_MARKET_VALUE_USD"].astype(float)
#         tot = emv.sum()
#         if tot > 0:
#             w_ret = (grp["NET_RETURN_MONTHLY"].astype(float) * emv).sum() / tot
#             w_bench = (grp["BENCHMARK_RETURN_MONTHLY"].astype(float) * emv).sum() / tot
#         else:
#             w_ret, w_bench = 0, 0
#         port_cum *= (1 + w_ret)
#         bench_cum *= (1 + w_bench)
#         cum_ret.append({
#             "date": pd.Timestamp(dt).strftime("%b %Y"),
#             "portfolio": round((port_cum - 1) * 100, 2),
#             "benchmark": round((bench_cum - 1) * 100, 2),
#         })

#     # ── 6-month return heatmap ────────────────────────────────────────────

#     last_6 = sorted(pr["MONTH_END_DATE"].unique())[-6:]
#     heatmap = []
#     for _, acc_row in accounts.iterrows():
#         aid = acc_row["ACCOUNT_IDENTIFIER"]
#         cp = pr[pr["ACCOUNT_ID"] == aid]
#         vals = []
#         for dt in last_6:
#             r = cp[cp["MONTH_END_DATE"] == dt]["NET_RETURN_MONTHLY"]
#             v = round(float(r.iloc[0]) * 100, 2) if len(r) > 0 else 0
#             vals.append(v)
#         heatmap.append({"client": acc_row["PRIMARY_OWNER_NAME"], "months": vals})
#     heatmap_months = [pd.Timestamp(d).strftime("%b %y") for d in last_6]

#     # ── Performance comparison table ──────────────────────────────────────

#     perf_table = []
#     for _, acc_row in accounts.iterrows():
#         aid = acc_row["ACCOUNT_IDENTIFIER"]
#         ap = latest_pr[latest_pr["ACCOUNT_ID"] == aid]
#         if len(ap) == 0:
#             continue
#         r = ap.iloc[0]
#         mo_ret = float(r["NET_RETURN_MONTHLY"])
#         ytd_ret = float(r["NET_RETURN_YTD"])
#         one_y = float(r["NET_RETURN_1Y"]) if pd.notna(r.get("NET_RETURN_1Y")) else ytd_ret
#         itd = float(r["NET_RETURN_ITD"]) if pd.notna(r.get("NET_RETURN_ITD")) else 0
#         bench_itd = float(r["BENCHMARK_RETURN_MONTHLY"])  # placeholder — use gross ITD - benchmark spread
#         # Compute excess: use ITD portfolio minus a rough benchmark ITD
#         # The view has GROSS_RETURN_ITD; for excess we approximate via
#         # compounding benchmark monthly over the same window — but the
#         # simplest approach: portfolio ITD minus benchmark ITD (unavailable
#         # directly, so we use TRACKING_ERROR or just set excess = itd - bench_itd_computed)
#         # We'll compute benchmark ITD by compounding BENCHMARK_RETURN_MONTHLY
#         cp = pr[pr["ACCOUNT_ID"] == aid].sort_values("MONTH_END_DATE")
#         if len(cp) > 0:
#             bench_itd_val = float((1 + cp["BENCHMARK_RETURN_MONTHLY"].astype(float)).prod() - 1)
#         else:
#             bench_itd_val = 0
#         excess = itd - bench_itd_val

#         perf_table.append({
#             "client": acc_row["PRIMARY_OWNER_NAME"],
#             "mo": mo_ret,
#             "ytd": ytd_ret,
#             "one_y": one_y,
#             "itd": itd,
#             "excess": excess,
#         })

#     # ── Risk metrics table ────────────────────────────────────────────────

#     risk_table = []
#     for _, acc_row in accounts.iterrows():
#         aid = acc_row["ACCOUNT_IDENTIFIER"]
#         ap = latest_pr[latest_pr["ACCOUNT_ID"] == aid]
#         if len(ap) == 0:
#             continue
#         r = ap.iloc[0]
#         risk_table.append({
#             "client": acc_row["PRIMARY_OWNER_NAME"],
#             "sharpe": float(r["SHARPE_RATIO"]) if pd.notna(r.get("SHARPE_RATIO")) else 0,
#             "sortino": float(r["SORTINO_RATIO"]) if pd.notna(r.get("SORTINO_RATIO")) else 0,
#             "max_dd": float(r["MAX_DRAWDOWN"]) if pd.notna(r.get("MAX_DRAWDOWN")) else 0,
#             "beta": float(r["BETA_36M"]) if pd.notna(r.get("BETA_36M")) else 0,
#             "alpha": float(r["ALPHA_ANNUAL_36M"]) if pd.notna(r.get("ALPHA_ANNUAL_36M")) else 0,
#         })

#     # ── Risk-return scatter ───────────────────────────────────────────────

#     scatter = []
#     for _, acc_row in accounts.iterrows():
#         aid = acc_row["ACCOUNT_IDENTIFIER"]
#         ap = latest_pr[latest_pr["ACCOUNT_ID"] == aid]
#         if len(ap) == 0:
#             continue
#         r = ap.iloc[0]
#         vol = float(r["VOLATILITY_ANNUAL"]) if pd.notna(r.get("VOLATILITY_ANNUAL")) else 0
#         # Annualized return: compound monthly returns
#         cp = pr[pr["ACCOUNT_ID"] == aid].sort_values("MONTH_END_DATE")
#         n_months = max(len(cp), 1)
#         ann_ret = float(((1 + cp["NET_RETURN_MONTHLY"].astype(float)).prod()) ** (12 / n_months) - 1)
#         scatter.append({
#             "client": acc_row["PRIMARY_OWNER_NAME"],
#             "risk": round(vol * 100, 2),
#             "return": round(ann_ret * 100, 2),
#         })

#     # ── Client accounts master table ──────────────────────────────────────

#     accounts_table = []
#     for _, acc_row in accounts.iterrows():
#         aid = acc_row["ACCOUNT_IDENTIFIER"]
#         ap = latest_pr[latest_pr["ACCOUNT_ID"] == aid]
#         if len(ap) == 0:
#             continue
#         r = ap.iloc[0]
#         aum_val = float(r["ENDING_MARKET_VALUE_USD"])
#         mo_ret = float(r["NET_RETURN_MONTHLY"])
#         ytd_ret = float(r["NET_RETURN_YTD"])
#         one_y = float(r["NET_RETURN_1Y"]) if pd.notna(r.get("NET_RETURN_1Y")) else ytd_ret
#         itd = float(r["NET_RETURN_ITD"]) if pd.notna(r.get("NET_RETURN_ITD")) else 0

#         cp = pr[pr["ACCOUNT_ID"] == aid].sort_values("MONTH_END_DATE")
#         bench_itd_val = float((1 + cp["BENCHMARK_RETURN_MONTHLY"].astype(float)).prod() - 1) if len(cp) > 0 else 0
#         excess = itd - bench_itd_val

#         sharpe_v = float(r["SHARPE_RATIO"]) if pd.notna(r.get("SHARPE_RATIO")) else 0
#         max_dd_v = float(r["MAX_DRAWDOWN"]) if pd.notna(r.get("MAX_DRAWDOWN")) else 0

#         # Sparkline: last 12 monthly returns
#         spark = [round(float(x) * 100, 2) for x in cp.tail(12)["NET_RETURN_MONTHLY"].astype(float)]

#         accounts_table.append({
#             "client_id": aid,
#             "client_name": acc_row["PRIMARY_OWNER_NAME"],
#             "household": acc_row.get("HOUSEHOLD_NAME", ""),
#             "advisor": acc_row.get("ADVISOR_NAME", ""),
#             "risk_profile": acc_row.get("RISK_PROFILE", ""),
#             "aum": aum_val,
#             "mo": mo_ret,
#             "ytd": float(ytd_ret),
#             "one_y": one_y,
#             "itd": itd,
#             "excess": excess,
#             "sharpe": sharpe_v,
#             "max_dd": max_dd_v,
#             "spark": spark,
#         })

#     return {
#         "total_aum": total_aum,
#         "weighted_ytd": weighted_ytd,
#         "total_accounts": total_accounts,
#         "unrealized_gains": unrealized_gains,
#         "cumulative_dividends": cumulative_dividends,
#         "aum_dates": aum_dates,
#         "aum_values": aum_values,
#         "ret_dates": ret_dates,
#         "ret_values": ret_values,
#         "alloc_labels": alloc_labels,
#         "alloc_values": alloc_values,
#         "alloc_targets": alloc_targets,
#         "drift_alerts": drift_alerts,
#         "advisors": advisors_list,
#         "sector_labels": sector_labels,
#         "sector_values": sector_values,
#         "drift_flags": drift_flags,
#         "cum_ret": cum_ret,
#         "heatmap": heatmap,
#         "heatmap_months": heatmap_months,
#         "perf_table": perf_table,
#         "risk_table": risk_table,
#         "scatter": scatter,
#         "accounts_table": accounts_table,
#     }


# # ── Routes ───────────────────────────────────────────────────────────────────

# @app.route("/")
# def dashboard():
#     try:
#         data = get_data()
#     except Exception as e:
#         logger.error("Failed to connect to Snowflake: %s", e)
#         return render_template("error.html", message=str(e)), 500

#     advisor_filter = request.args.get("advisor", "All")
#     risk_filter = request.args.get("risk_profile", "All")

#     account_ids = filter_account_ids(data, advisor_filter, risk_filter)
#     if not account_ids:
#         account_ids = set(data["accounts"]["ACCOUNT_IDENTIFIER"])

#     ctx = compute_dashboard(data, account_ids)

#     ctx["advisors_list"] = sorted(data["accounts"]["ADVISOR_NAME"].dropna().unique().tolist())
#     ctx["risk_profiles_list"] = sorted(data["accounts"]["RISK_PROFILE"].dropna().unique().tolist())
#     ctx["selected_advisor"] = advisor_filter
#     ctx["selected_risk"] = risk_filter

#     return render_template("dashboard.html", **ctx)


# @app.route("/health")
# def health():
#     return "ok", 200


# if __name__ == "__main__":
#     app.run(host="0.0.0.0", debug=False, port=5000)


#!/usr/bin/env python3
"""Shaw Wealth Partners — Flask Dashboard Application (Snowflake backend)."""

import os
import math
import time
import logging

import pandas as pd
import numpy as np
import snowflake.connector
from dotenv import load_dotenv
from flask import Flask, render_template, request

load_dotenv()

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Snowflake connection ─────────────────────────────────────────────────────

SF_CONFIG = {
    "account": os.getenv("SNOWFLAKE_ACCOUNT", ""),
    "user": os.getenv("SNOWFLAKE_USER", ""),
    "password": os.getenv("SNOWFLAKE_PASSWORD", ""),
    "warehouse": os.getenv("SNOWFLAKE_WAREHOUSE", ""),
    "database": os.getenv("SNOWFLAKE_DATABASE", "WEALTH_MANAGEMENT"),
    "schema": os.getenv("SNOWFLAKE_SCHEMA", "SHAW_PARTNERS"),
    "role": os.getenv("SNOWFLAKE_ROLE", ""),
}

CACHE_TTL = 300  # 5 minutes
_cache = {"data": None, "ts": 0}


def get_sf_connection():
    """Create a new Snowflake connection."""
    cfg = {k: v for k, v in SF_CONFIG.items() if v}
    return snowflake.connector.connect(**cfg)


def sf_query(sql: str) -> pd.DataFrame:
    """Execute a SQL query against Snowflake and return a DataFrame."""
    conn = get_sf_connection()
    try:
        cur = conn.cursor()
        cur.execute(sql)
        cols = [desc[0] for desc in cur.description]
        rows = cur.fetchall()
        return pd.DataFrame(rows, columns=cols)
    finally:
        conn.close()


# ── Load data from Snowflake ────────────────────────────────────────────────

def load_data():
    """Fetch all required data from Snowflake views into DataFrames.

    NOTE: All data is scoped to accounts where
    CAST(ACCOUNT_IDENTIFIER AS INT) > 8. The account master query filters
    accounts directly; every other view is later filtered (in
    compute_dashboard / filter_account_ids) down to the ACCOUNT_IDENTIFIER
    set produced here, so the restriction cascades to the whole dashboard.
    """
    logger.info("Loading data from Snowflake...")

    d = {}

    # Account master — restricted to ACCOUNT_IDENTIFIER > 8
    d["accounts"] = sf_query("""
        SELECT * FROM VW_ACCOUNT_MASTER
        WHERE TRY_CAST("ACCOUNT_IDENTIFIER" AS INT) > 8
    """)

    # Monthly performance & risk
    d["perf_risk"] = sf_query("SELECT * FROM VW_PORTFOLIO_MONTHLY_PERF_RISK")
    d["perf_risk"]["MONTH_END_DATE"] = pd.to_datetime(d["perf_risk"]["MONTH_END_DATE"])

    # Holdings (latest date only for allocation)
    d["holdings"] = sf_query("""
        SELECT * FROM VW_PORTFOLIO_HOLDINGS
        WHERE HOLDING_DATE = (SELECT MAX(HOLDING_DATE) FROM VW_PORTFOLIO_HOLDINGS)
    """)

    # Monthly metrics (for gains & dividends)
    d["metrics"] = sf_query("SELECT * FROM VW_PORTFOLIO_MONTHLY_METRICS")
    d["metrics"]["MONTH_END_DATE"] = pd.to_datetime(d["metrics"]["MONTH_END_DATE"])

    # Attribution (latest month, sector level)
    d["attribution"] = sf_query("""
        SELECT * FROM VW_PORTFOLIO_MONTHLY_PERF_ATTRIBUTION
        WHERE MONTH_END_DATE = (SELECT MAX(MONTH_END_DATE) FROM VW_PORTFOLIO_MONTHLY_PERF_ATTRIBUTION)
          AND ATTRIBUTION_LEVEL = 'SECTOR'
    """)

    # Restrict every other dataset down to the filtered account set so the
    # > 8 restriction on ACCOUNT_IDENTIFIER cascades everywhere data is used.
    allowed_ids = set(d["accounts"]["ACCOUNT_IDENTIFIER"])
    d["perf_risk"] = d["perf_risk"][d["perf_risk"]["ACCOUNT_ID"].isin(allowed_ids)]
    d["holdings"] = d["holdings"][d["holdings"]["ACCOUNT_ID"].isin(allowed_ids)]
    d["metrics"] = d["metrics"][d["metrics"]["ACCOUNT_ID"].isin(allowed_ids)]
    d["attribution"] = d["attribution"][d["attribution"]["ACCOUNT_ID"].isin(allowed_ids)]

    logger.info("Data loaded successfully.")
    return d


def get_data():
    """Return cached data, refreshing if stale."""
    now = time.time()
    if _cache["data"] is None or (now - _cache["ts"]) > CACHE_TTL:
        _cache["data"] = load_data()
        _cache["ts"] = now
    return _cache["data"]


# ── Filtering ────────────────────────────────────────────────────────────────

def filter_account_ids(data, advisor=None, risk_profile=None):
    """Return filtered ACCOUNT_IDENTIFIER set."""
    accts = data["accounts"].copy()
    if advisor and advisor != "All":
        accts = accts[accts["ADVISOR_NAME"] == advisor]
    if risk_profile and risk_profile != "All":
        accts = accts[accts["RISK_PROFILE"] == risk_profile]
    return set(accts["ACCOUNT_IDENTIFIER"])


# ── Dashboard computation ────────────────────────────────────────────────────

def compute_dashboard(data, account_ids):
    """Compute all dashboard metrics for a given account subset."""

    accounts = data["accounts"][data["accounts"]["ACCOUNT_IDENTIFIER"].isin(account_ids)]
    pr = data["perf_risk"][data["perf_risk"]["ACCOUNT_ID"].isin(account_ids)].copy()
    holdings = data["holdings"][data["holdings"]["ACCOUNT_ID"].isin(account_ids)]
    metrics = data["metrics"][data["metrics"]["ACCOUNT_ID"].isin(account_ids)]
    attribution = data["attribution"][data["attribution"]["ACCOUNT_ID"].isin(account_ids)]

    latest_date = pr["MONTH_END_DATE"].max()
    latest_pr = pr[pr["MONTH_END_DATE"] == latest_date]

    # Latest metrics
    metrics_latest_date = metrics["MONTH_END_DATE"].max()
    latest_metrics = metrics[metrics["MONTH_END_DATE"] == metrics_latest_date]

    # ── KPIs ──────────────────────────────────────────────────────────────

    total_aum = float(latest_pr["ENDING_MARKET_VALUE_USD"].sum())

    # Weighted avg YTD return from latest month
    if total_aum > 0:
        weighted_ytd = float(
            (latest_pr["NET_RETURN_YTD"].astype(float) * latest_pr["ENDING_MARKET_VALUE_USD"].astype(float)).sum()
            / total_aum
        )
    else:
        weighted_ytd = 0.0

    total_accounts = len(account_ids)

    unrealized_gains = float(latest_metrics["UNREALIZED_GAIN_USD"].sum())

    cumulative_dividends = float(metrics["DIVIDEND_INCOME_USD"].sum())

    # ── AUM growth (monthly total) ────────────────────────────────────────

    aum_by_month = pr.groupby("MONTH_END_DATE")["ENDING_MARKET_VALUE_USD"].sum().sort_index()
    aum_dates = [d.strftime("%b %Y") for d in aum_by_month.index]
    aum_values = [round(float(v) / 1e6, 2) for v in aum_by_month.values]

    # ── Monthly net returns (AUM-weighted) ────────────────────────────────

    monthly_ret = []
    for dt, grp in pr.groupby("MONTH_END_DATE"):
        emv = grp["ENDING_MARKET_VALUE_USD"].astype(float)
        nr = grp["NET_RETURN_MONTHLY"].astype(float)
        tot = emv.sum()
        w_ret = (nr * emv).sum() / tot if tot > 0 else 0
        monthly_ret.append({"date": dt, "ret": w_ret})
    monthly_ret_df = pd.DataFrame(monthly_ret).sort_values("date")
    ret_dates = [d.strftime("%b %Y") for d in monthly_ret_df["date"]]
    ret_values = [round(float(r) * 100, 2) for r in monthly_ret_df["ret"]]

    # ── Asset allocation donut ────────────────────────────────────────────

    if len(holdings) > 0:
        alloc_agg = holdings.groupby("ASSET_CLASS").agg(
            total_mv=("MARKET_VALUE_USD", "sum"),
            avg_target=("TARGET_PCT", "mean"),
        ).reset_index()
        total_mv = alloc_agg["total_mv"].sum()
        alloc_agg["actual_pct"] = alloc_agg["total_mv"] / total_mv if total_mv > 0 else 0
        alloc_labels = alloc_agg["ASSET_CLASS"].tolist()
        alloc_values = [round(float(v) * 100, 1) for v in alloc_agg["actual_pct"]]
        alloc_targets = [round(float(v) * 100, 1) for v in alloc_agg["avg_target"]]
    else:
        alloc_labels, alloc_values, alloc_targets = [], [], []
        alloc_agg = pd.DataFrame(columns=["ASSET_CLASS", "actual_pct", "avg_target"])

    # Drift alerts (aggregate)
    drift_alerts = []
    if len(alloc_agg) > 0:
        for _, row in alloc_agg.iterrows():
            actual = float(row.get("actual_pct", 0)) * 100
            target = float(row.get("avg_target", 0)) * 100
            drift = actual - target
            if abs(drift) > 1.0:
                drift_alerts.append({
                    "asset_class": row["ASSET_CLASS"],
                    "actual": round(actual, 1),
                    "target": round(target, 1),
                    "drift": round(drift, 1),
                })

    # ── Advisor data ──────────────────────────────────────────────────────

    advisors_list = []
    for adv_name, grp in accounts.groupby("ADVISOR_NAME"):
        adv_ids = set(grp["ACCOUNT_IDENTIFIER"])
        adv_latest = latest_pr[latest_pr["ACCOUNT_ID"].isin(adv_ids)]
        adv_aum = float(adv_latest["ENDING_MARKET_VALUE_USD"].sum())
        adv_accounts = len(adv_ids)

        adv_ytd_vals = adv_latest["NET_RETURN_YTD"].astype(float)
        adv_avg_ytd = float(adv_ytd_vals.mean()) if len(adv_ytd_vals) > 0 else 0

        adv_sharpe_vals = adv_latest["SHARPE_RATIO"].astype(float)
        adv_avg_sharpe = float(adv_sharpe_vals.mean()) if len(adv_sharpe_vals) > 0 else 0

        accts = []
        for _, acc_row in grp.iterrows():
            aid = acc_row["ACCOUNT_IDENTIFIER"]
            acc_perf = latest_pr[latest_pr["ACCOUNT_ID"] == aid]
            cl_aum = float(acc_perf["ENDING_MARKET_VALUE_USD"].sum()) if len(acc_perf) > 0 else 0
            cl_ytd = float(acc_perf["NET_RETURN_YTD"].iloc[0]) if len(acc_perf) > 0 else 0
            cl_sharpe = float(acc_perf["SHARPE_RATIO"].iloc[0]) if len(acc_perf) > 0 else 0
            accts.append({
                "client_name": acc_row["PRIMARY_OWNER_NAME"],
                "risk_profile": acc_row.get("RISK_PROFILE", ""),
                "aum": cl_aum,
                "ytd": cl_ytd,
                "sharpe": cl_sharpe,
            })

        advisors_list.append({
            "name": adv_name,
            "aum": adv_aum,
            "accounts": adv_accounts,
            "avg_ytd": adv_avg_ytd,
            "avg_sharpe": adv_avg_sharpe,
            "accts": accts,
        })

    # ── Sector contribution ───────────────────────────────────────────────

    if len(attribution) > 0:
        sector_agg = attribution.groupby("SECTOR_CODE")["TOTAL_CONTRIBUTION"].sum().reset_index()
        sector_labels = sector_agg["SECTOR_CODE"].tolist()
        sector_values = [round(float(v), 3) for v in sector_agg["TOTAL_CONTRIBUTION"]]
    else:
        sector_labels, sector_values = [], []

    # ── Per-client drift flags ────────────────────────────────────────────

    drift_flags = []
    if len(holdings) > 0:
        for aid, h_grp in holdings.groupby("ACCOUNT_ID"):
            for _, hrow in h_grp.iterrows():
                actual_w = float(hrow.get("WEIGHT", 0)) * 100
                target_w = float(hrow.get("TARGET_PCT", 0)) * 100
                drift_val = actual_w - target_w
                if abs(drift_val) > 2.0:
                    drift_flags.append({
                        "client": hrow.get("PRIMARY_OWNER_NAME", str(aid)),
                        "asset_class": hrow.get("ASSET_CLASS", ""),
                        "actual": round(actual_w, 1),
                        "target": round(target_w, 1),
                        "drift": round(drift_val, 1),
                    })

    # ── Cumulative returns line chart ─────────────────────────────────────

    cum_ret = []
    all_dates = sorted(pr["MONTH_END_DATE"].unique())
    port_cum = 1.0
    bench_cum = 1.0
    for dt in all_dates:
        grp = pr[pr["MONTH_END_DATE"] == dt]
        emv = grp["ENDING_MARKET_VALUE_USD"].astype(float)
        tot = emv.sum()
        if tot > 0:
            w_ret = (grp["NET_RETURN_MONTHLY"].astype(float) * emv).sum() / tot
            w_bench = (grp["BENCHMARK_RETURN_MONTHLY"].astype(float) * emv).sum() / tot
        else:
            w_ret, w_bench = 0, 0
        port_cum *= (1 + w_ret)
        bench_cum *= (1 + w_bench)
        cum_ret.append({
            "date": pd.Timestamp(dt).strftime("%b %Y"),
            "portfolio": round((port_cum - 1) * 100, 2),
            "benchmark": round((bench_cum - 1) * 100, 2),
        })

    # ── 6-month return heatmap ────────────────────────────────────────────

    last_6 = sorted(pr["MONTH_END_DATE"].unique())[-6:]
    heatmap = []
    for _, acc_row in accounts.iterrows():
        aid = acc_row["ACCOUNT_IDENTIFIER"]
        cp = pr[pr["ACCOUNT_ID"] == aid]
        vals = []
        for dt in last_6:
            r = cp[cp["MONTH_END_DATE"] == dt]["NET_RETURN_MONTHLY"]
            v = round(float(r.iloc[0]) * 100, 2) if len(r) > 0 else 0
            vals.append(v)
        heatmap.append({"client": acc_row["PRIMARY_OWNER_NAME"], "months": vals})
    heatmap_months = [pd.Timestamp(d).strftime("%b %y") for d in last_6]

    # ── Performance comparison table ──────────────────────────────────────

    perf_table = []
    for _, acc_row in accounts.iterrows():
        aid = acc_row["ACCOUNT_IDENTIFIER"]
        ap = latest_pr[latest_pr["ACCOUNT_ID"] == aid]
        if len(ap) == 0:
            continue
        r = ap.iloc[0]
        mo_ret = float(r["NET_RETURN_MONTHLY"])
        ytd_ret = float(r["NET_RETURN_YTD"])
        one_y = float(r["NET_RETURN_1Y"]) if pd.notna(r.get("NET_RETURN_1Y")) else ytd_ret
        itd = float(r["NET_RETURN_ITD"]) if pd.notna(r.get("NET_RETURN_ITD")) else 0
        bench_itd = float(r["BENCHMARK_RETURN_MONTHLY"])  # placeholder — use gross ITD - benchmark spread
        # Compute excess: use ITD portfolio minus a rough benchmark ITD
        # The view has GROSS_RETURN_ITD; for excess we approximate via
        # compounding benchmark monthly over the same window — but the
        # simplest approach: portfolio ITD minus benchmark ITD (unavailable
        # directly, so we use TRACKING_ERROR or just set excess = itd - bench_itd_computed)
        # We'll compute benchmark ITD by compounding BENCHMARK_RETURN_MONTHLY
        cp = pr[pr["ACCOUNT_ID"] == aid].sort_values("MONTH_END_DATE")
        if len(cp) > 0:
            bench_itd_val = float((1 + cp["BENCHMARK_RETURN_MONTHLY"].astype(float)).prod() - 1)
        else:
            bench_itd_val = 0
        excess = itd - bench_itd_val

        perf_table.append({
            "client": acc_row["PRIMARY_OWNER_NAME"],
            "mo": mo_ret,
            "ytd": ytd_ret,
            "one_y": one_y,
            "itd": itd,
            "excess": excess,
        })

    # ── Risk metrics table ────────────────────────────────────────────────

    risk_table = []
    for _, acc_row in accounts.iterrows():
        aid = acc_row["ACCOUNT_IDENTIFIER"]
        ap = latest_pr[latest_pr["ACCOUNT_ID"] == aid]
        if len(ap) == 0:
            continue
        r = ap.iloc[0]
        risk_table.append({
            "client": acc_row["PRIMARY_OWNER_NAME"],
            "sharpe": float(r["SHARPE_RATIO"]) if pd.notna(r.get("SHARPE_RATIO")) else 0,
            "sortino": float(r["SORTINO_RATIO"]) if pd.notna(r.get("SORTINO_RATIO")) else 0,
            "max_dd": float(r["MAX_DRAWDOWN"]) if pd.notna(r.get("MAX_DRAWDOWN")) else 0,
            "beta": float(r["BETA_36M"]) if pd.notna(r.get("BETA_36M")) else 0,
            "alpha": float(r["ALPHA_ANNUAL_36M"]) if pd.notna(r.get("ALPHA_ANNUAL_36M")) else 0,
        })

    # ── Risk-return scatter ───────────────────────────────────────────────

    scatter = []
    for _, acc_row in accounts.iterrows():
        aid = acc_row["ACCOUNT_IDENTIFIER"]
        ap = latest_pr[latest_pr["ACCOUNT_ID"] == aid]
        if len(ap) == 0:
            continue
        r = ap.iloc[0]
        vol = float(r["VOLATILITY_ANNUAL"]) if pd.notna(r.get("VOLATILITY_ANNUAL")) else 0
        # Annualized return: compound monthly returns
        cp = pr[pr["ACCOUNT_ID"] == aid].sort_values("MONTH_END_DATE")
        n_months = max(len(cp), 1)
        ann_ret = float(((1 + cp["NET_RETURN_MONTHLY"].astype(float)).prod()) ** (12 / n_months) - 1)
        scatter.append({
            "client": acc_row["PRIMARY_OWNER_NAME"],
            "risk": round(vol * 100, 2),
            "return": round(ann_ret * 100, 2),
        })

    # ── Client accounts master table ──────────────────────────────────────

    accounts_table = []
    for _, acc_row in accounts.iterrows():
        aid = acc_row["ACCOUNT_IDENTIFIER"]
        ap = latest_pr[latest_pr["ACCOUNT_ID"] == aid]
        if len(ap) == 0:
            continue
        r = ap.iloc[0]
        aum_val = float(r["ENDING_MARKET_VALUE_USD"])
        mo_ret = float(r["NET_RETURN_MONTHLY"])
        ytd_ret = float(r["NET_RETURN_YTD"])
        one_y = float(r["NET_RETURN_1Y"]) if pd.notna(r.get("NET_RETURN_1Y")) else ytd_ret
        itd = float(r["NET_RETURN_ITD"]) if pd.notna(r.get("NET_RETURN_ITD")) else 0

        cp = pr[pr["ACCOUNT_ID"] == aid].sort_values("MONTH_END_DATE")
        bench_itd_val = float((1 + cp["BENCHMARK_RETURN_MONTHLY"].astype(float)).prod() - 1) if len(cp) > 0 else 0
        excess = itd - bench_itd_val

        sharpe_v = float(r["SHARPE_RATIO"]) if pd.notna(r.get("SHARPE_RATIO")) else 0
        max_dd_v = float(r["MAX_DRAWDOWN"]) if pd.notna(r.get("MAX_DRAWDOWN")) else 0

        # Sparkline: last 12 monthly returns
        spark = [round(float(x) * 100, 2) for x in cp.tail(12)["NET_RETURN_MONTHLY"].astype(float)]

        accounts_table.append({
            "client_id": aid,
            "client_name": acc_row["PRIMARY_OWNER_NAME"],
            "household": acc_row.get("HOUSEHOLD_NAME", ""),
            "advisor": acc_row.get("ADVISOR_NAME", ""),
            "risk_profile": acc_row.get("RISK_PROFILE", ""),
            "aum": aum_val,
            "mo": mo_ret,
            "ytd": float(ytd_ret),
            "one_y": one_y,
            "itd": itd,
            "excess": excess,
            "sharpe": sharpe_v,
            "max_dd": max_dd_v,
            "spark": spark,
        })

    return {
        "total_aum": total_aum,
        "weighted_ytd": weighted_ytd,
        "total_accounts": total_accounts,
        "unrealized_gains": unrealized_gains,
        "cumulative_dividends": cumulative_dividends,
        "aum_dates": aum_dates,
        "aum_values": aum_values,
        "ret_dates": ret_dates,
        "ret_values": ret_values,
        "alloc_labels": alloc_labels,
        "alloc_values": alloc_values,
        "alloc_targets": alloc_targets,
        "drift_alerts": drift_alerts,
        "advisors": advisors_list,
        "sector_labels": sector_labels,
        "sector_values": sector_values,
        "drift_flags": drift_flags,
        "cum_ret": cum_ret,
        "heatmap": heatmap,
        "heatmap_months": heatmap_months,
        "perf_table": perf_table,
        "risk_table": risk_table,
        "scatter": scatter,
        "accounts_table": accounts_table,
    }


# ── Routes ───────────────────────────────────────────────────────────────────

@app.route("/")
def dashboard():
    try:
        data = get_data()
    except Exception as e:
        logger.error("Failed to connect to Snowflake: %s", e)
        return render_template("error.html", message=str(e)), 500

    advisor_filter = request.args.get("advisor", "All")
    risk_filter = request.args.get("risk_profile", "All")

    account_ids = filter_account_ids(data, advisor_filter, risk_filter)
    if not account_ids:
        account_ids = set(data["accounts"]["ACCOUNT_IDENTIFIER"])

    ctx = compute_dashboard(data, account_ids)

    ctx["advisors_list"] = sorted(data["accounts"]["ADVISOR_NAME"].dropna().unique().tolist())
    ctx["risk_profiles_list"] = sorted(data["accounts"]["RISK_PROFILE"].dropna().unique().tolist())
    ctx["selected_advisor"] = advisor_filter
    ctx["selected_risk"] = risk_filter

    return render_template("dashboard.html", **ctx)


@app.route("/health")
def health():
    return "ok", 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=False, port=5000)