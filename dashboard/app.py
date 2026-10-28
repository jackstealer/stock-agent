import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)                       # all paths in the project are relative to the repo root

import numpy as np
import pandas as pd
import streamlit as st
import yaml

from src.gate.check import MIN_DAYS, VAR_FLOOR_DAILY
from src.gate.registry import compare, load_trials, mlflow_run_names
from src.gate.stats import expected_max_sharpe
from src.monitor.quality import check_ticker
from src.monitor.report import account_summary, drawdown, equity_curve, recent_orders
from src.risk import killswitch

ACCOUNTS = ["buy_hold", "momentum_top5"]

st.set_page_config(page_title="stock-agent", layout="wide")
st.title("stock-agent")
st.caption("Research project. Paper trading only: no real orders are ever sent. "
           "Short-term paper results are noise.")


@st.cache_data(ttl=600)
def health() -> pd.DataFrame:
    cfg = yaml.safe_load(Path("configs/config.yaml").read_text(encoding="utf-8"))
    reviewed = [str(d) for d in cfg.get("reviewed_jumps", [])]
    rows = []
    for t in cfg["tickers"]:
        r = check_ticker(t)
        problems = [p for p in r["problems"]
                    if not (p.startswith("jump") and any(d in p for d in reviewed))]
        rows.append({"ticker": t, "rows": r["rows"], "first": str(r["first"]),
                     "last": str(r["last"]),
                     "status": "OK" if not problems else "CHECK",
                     "problems": "; ".join(problems)})
    return pd.DataFrame(rows)


glob = killswitch.status()
c1, c2 = st.columns(2)
c1.metric("Global kill switch", "ENGAGED" if glob else "not engaged")
if glob:
    c2.error(f"{glob['reason']} (since {glob['engaged_at']})")

tab1, tab2, tab3 = st.tabs(["Paper trading", "Data health", "Experiments and gate"])

with tab1:
    curves = {n: equity_curve(n) for n in ACCOUNTS}
    cols = st.columns(len(ACCOUNTS))
    for col, n in zip(cols, ACCOUNTS):
        s = account_summary(n)
        if not s:
            col.info(f"{n}: no state yet (run src.paper.run_daily)")
            continue
        ret = s["equity"] / s["initial"] - 1 if s["initial"] else 0.0
        col.metric(n, f"Rs {s['equity']:,.0f}", f"{ret:+.2%}")
        col.caption(f"{s['holdings']} holdings | last run {s['last_run_day']} | "
                    f"orders today {s['orders_today']}, rejected {s['rejected_today']}"
                    + (" | KILLED" if s["killed"] else ""))

    df = pd.concat({k: v for k, v in curves.items() if len(v)}, axis=1)
    if len(df):
        st.subheader("Equity (rebased to 100)")
        st.line_chart(df / df.bfill().iloc[0] * 100)
        st.subheader("Drawdown")
        st.line_chart(pd.concat({k: drawdown(v) for k, v in curves.items() if len(v)},
                                axis=1))
        st.caption(f"{len(df)} days of paper data so far "
                   f"(the gate needs {MIN_DAYS} before any promotion).")
        pick = st.selectbox("Recent orders for", ACCOUNTS)
        st.dataframe(recent_orders(pick), hide_index=True)
    else:
        st.info("No paper-trading data yet.")

with tab2:
    h = health()
    st.metric("Stocks passing quality checks", f"{(h['status'] == 'OK').sum()} / {len(h)}")
    st.dataframe(h, hide_index=True)
    st.caption("Checks: staleness, gaps, jumps over 20% (reviewed dates excluded), "
               "zero-volume days.")

with tab3:
    n = len(load_trials())
    st.metric("Trials registered", n)
    st.metric("Luck hurdle (annualised Sharpe)",
              f"{expected_max_sharpe(n, VAR_FLOOR_DAILY) * np.sqrt(252):.2f}")
    try:
        problems = compare([t["mlflow_run"] for t in load_trials()], mlflow_run_names())
        if problems:
            st.error("; ".join(problems))
        else:
            st.success("Registry matches MLflow")
    except Exception as e:
        st.warning(f"Could not read MLflow: {e}")
    st.subheader("Experiment log")
    st.markdown(Path("docs/experiments.md").read_text(encoding="utf-8"))