"""FII / DII Flow Dashboard (Streamlit). Reads the live CSV from GitHub."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# CHANGE THIS if your repo name or branch differs (use the "Raw" link of the CSV)
CSV_URL = ("https://raw.githubusercontent.com/Nagesh0091/FII_DII_DATA_COLLECTION/"
           "main/fii_dii_cash_history.csv")
FII_C, DII_C = "#1f5fbf", "#e8832a"

st.set_page_config(page_title="FII / DII Flow Dashboard", layout="wide")


@st.cache_data(ttl=3600)
def load(url):
    df = pd.read_csv(url, parse_dates=["Date"]).sort_values("Date").reset_index(drop=True)
    df.columns = [c.replace("_Cr", "") for c in df.columns]
    return df


@st.cache_data(ttl=3600)
def load_nifty(start, end):
    import yfinance as yf
    d = yf.download("^NSEI", start=start, end=end + pd.Timedelta(days=5), progress=False, auto_adjust=False)
    if isinstance(d.columns, pd.MultiIndex):
        d.columns = d.columns.get_level_values(0)
    d.index = pd.to_datetime(d.index).tz_localize(None)
    m = pd.DataFrame({"Date": d.index, "Ret": d["Close"].pct_change() * 100,
                      "Range": (d["High"] - d["Low"]) / d["Close"] * 100}).reset_index(drop=True)
    m["NextRet"], m["NextRange"] = m["Ret"].shift(-1), m["Range"].shift(-1)
    return m


def streak(s):
    """Signed run length of consecutive same-sign values (+3 = 3 buy days, -3 = 3 sell days)."""
    out, run = [], 0
    for v in np.sign(s):
        run = (run + 1 if run > 0 else 1) if v > 0 else (run - 1 if run < 0 else -1)
        out.append(run)
    return pd.Series(out, index=s.index)


def regime(r):
    if r.FII_Net >= 0 and r.DII_Net >= 0: return "Both buying"
    if r.FII_Net < 0 and r.DII_Net >= 0: return "DII absorbs FII selling"
    if r.FII_Net < 0 and r.DII_Net < 0: return "Both selling"
    return "FII buys, DII sells"


try:
    raw = load(CSV_URL)
except Exception as e:
    st.error(f"Could not load data from GitHub: {e}")
    st.stop()

# ---------------- Sidebar ----------------
st.sidebar.header("Filters")
dmin, dmax = raw.Date.min().date(), raw.Date.max().date()
start, end = st.sidebar.date_input("Date range", (dmin, dmax), min_value=dmin, max_value=dmax)
win = st.sidebar.selectbox("Rolling window (days)", [5, 10, 20], index=0)
skip_special = st.sidebar.checkbox("Exclude weekend (Muhurat) sessions", True,
                                   help="e.g. 2026-11-08, a tiny Diwali session")
df = raw[(raw.Date.dt.date >= start) & (raw.Date.dt.date <= end)].copy()
if skip_special:
    df = df[df.Date.dt.weekday < 5]
if df.empty:
    st.warning("No data in this range."); st.stop()

df["Total_Net"] = df.FII_Net + df.DII_Net
df["FII_Cum"], df["DII_Cum"] = df.FII_Net.cumsum(), df.DII_Net.cumsum()
df["FII_Roll"], df["DII_Roll"] = df.FII_Net.rolling(win).sum(), df.DII_Net.rolling(win).sum()
df["FII_Streak"], df["DII_Streak"] = streak(df.FII_Net), streak(df.DII_Net)
df["Regime"] = df.apply(regime, axis=1)
last = df.iloc[-1]

st.title("FII / DII Flow Dashboard")
st.caption(f"Cash market, Rs. Cr. Latest data: {last.Date:%d %b %Y}  |  {len(df)} trading days shown. "
           "End-of-day data: context for the next session, not a live signal. Not investment advice.")

mtd = df[df.Date.dt.to_period("M") == last.Date.to_period("M")]
c = st.columns(5)
c[0].metric("FII net (latest day)", f"{last.FII_Net:,.0f}")
c[1].metric("DII net (latest day)", f"{last.DII_Net:,.0f}")
c[2].metric("FII net (month to date)", f"{mtd.FII_Net.sum():,.0f}")
c[3].metric("DII net (month to date)", f"{mtd.DII_Net.sum():,.0f}")
c[4].metric("Net sell days: FII / DII", f"{(df.FII_Net < 0).sum()} / {(df.DII_Net < 0).sum()}")

t1, t2, t3, t4 = st.tabs(["Trends", "FII vs DII", "Intraday context", "Data"])

# ---------------- Trends ----------------
with t1:
    f = go.Figure([go.Bar(x=df.Date, y=df.FII_Net, name="FII net", marker_color=FII_C),
                   go.Bar(x=df.Date, y=df.DII_Net, name="DII net", marker_color=DII_C)])
    f.update_layout(barmode="group", title="Daily net flow (Rs. Cr)", height=380, legend_orientation="h")
    st.plotly_chart(f, width="stretch")
    a, b = st.columns(2)
    f = go.Figure([go.Scatter(x=df.Date, y=df.FII_Cum, name="FII", line_color=FII_C),
                   go.Scatter(x=df.Date, y=df.DII_Cum, name="DII", line_color=DII_C)])
    f.update_layout(title="Cumulative net flow (Rs. Cr)", height=340, legend_orientation="h")
    a.plotly_chart(f, width="stretch")
    f = go.Figure([go.Scatter(x=df.Date, y=df.FII_Roll, name="FII", line_color=FII_C),
                   go.Scatter(x=df.Date, y=df.DII_Roll, name="DII", line_color=DII_C)])
    f.update_layout(title=f"Rolling {win}-day net flow (Rs. Cr)", height=340, legend_orientation="h")
    b.plotly_chart(f, width="stretch")
    mo = df.groupby(df.Date.dt.to_period("M").astype(str))[["FII_Net", "DII_Net", "Total_Net"]].sum().round(0)
    st.subheader("Monthly net flow (Rs. Cr)")
    st.dataframe(mo, width="stretch")

# ---------------- FII vs DII ----------------
with t2:
    corr = df.FII_Net.corr(df.DII_Net)
    sell = df[df.FII_Net < 0]
    absorb = sell.DII_Net.sum() / abs(sell.FII_Net.sum()) * 100 if len(sell) else np.nan
    k = st.columns(3)
    k[0].metric("Correlation FII vs DII net", f"{corr:.2f}")
    k[1].metric("FII net-sell days", f"{len(sell)} of {len(df)}")
    k[2].metric("DII absorption on FII sell days", f"{absorb:.0f}%",
                help="DII net buying as % of FII net selling, on days FII was a net seller")
    m, bb = np.polyfit(df.FII_Net, df.DII_Net, 1)
    xs = np.array([df.FII_Net.min(), df.FII_Net.max()])
    f = go.Figure([go.Scatter(x=df.FII_Net, y=df.DII_Net, mode="markers", text=df.Date.dt.strftime("%d %b"),
                              marker=dict(color=FII_C, size=8), name="Days"),
                   go.Scatter(x=xs, y=m * xs + bb, mode="lines", line=dict(color="grey", dash="dash"), name="Trend")])
    f.update_layout(title="FII net vs DII net (each dot = one day)", xaxis_title="FII net (Rs. Cr)",
                    yaxis_title="DII net (Rs. Cr)", height=450)
    st.plotly_chart(f, width="stretch")
    st.caption(f"Sample size: {len(df)} days. A short sample can change a lot as data grows.")
    st.subheader("Largest days")
    big = df.assign(AbsFII=df.FII_Net.abs()).nlargest(8, "AbsFII")[["Date", "FII_Net", "DII_Net", "Regime"]]
    st.dataframe(big.assign(Date=big.Date.dt.date), width="stretch", hide_index=True)

# ---------------- Intraday context ----------------
with t3:
    st.subheader("Where are we now?")
    k = st.columns(4)
    k[0].metric("Current regime", last.Regime)
    k[1].metric("FII streak", f"{abs(int(last.FII_Streak))} {'buy' if last.FII_Streak > 0 else 'sell'} days")
    k[2].metric("DII streak", f"{abs(int(last.DII_Streak))} {'buy' if last.DII_Streak > 0 else 'sell'} days")
    k[3].metric("Last 5 / 10 day FII net", f"{df.FII_Net.tail(5).sum():,.0f} / {df.FII_Net.tail(10).sum():,.0f}")
    rg = df.Regime.value_counts().rename_axis("Regime").reset_index(name="Days")
    rg["% of days"] = (rg.Days / len(df) * 100).round(0)
    st.dataframe(rg, width="stretch", hide_index=True)

    st.subheader("What happened the next day? (Nifty 50)")
    st.caption("Next-day return and range (High-Low as % of Close) after large-flow days and flow streaks. "
               "Small samples: treat as indicative only.")
    try:
        mk = load_nifty(df.Date.min(), df.Date.max())
        x = df.merge(mk, on="Date", how="inner")
        big_thr = x.FII_Net.abs().quantile(0.9)
        groups = {"After large-flow day (top 10% |FII net|)": x.FII_Net.abs() >= big_thr,
                  "After 3+ FII net-sell days in a row": x.FII_Streak <= -3,
                  "After 3+ FII net-buy days in a row": x.FII_Streak >= 3,
                  "All days": pd.Series(True, index=x.index)}
        rows = []
        for name, mask in groups.items():
            g = x[mask & x.NextRet.notna()]
            rows.append({"Situation": name, "Sample (days)": len(g),
                         "Avg next-day return %": round(g.NextRet.mean(), 2) if len(g) else None,
                         "% next days up": round((g.NextRet > 0).mean() * 100) if len(g) else None,
                         "Avg next-day range %": round(g.NextRange.mean(), 2) if len(g) else None})
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
    except Exception as e:
        st.info(f"Nifty data could not be loaded right now ({e}). The flow views above still work.")

# ---------------- Data ----------------
with t4:
    show = df[["Date", "FII_Gross_Purchase", "FII_Gross_Sales", "FII_Net",
               "DII_Gross_Purchase", "DII_Gross_Sales", "DII_Net", "Regime"]]
    st.dataframe(show.assign(Date=show.Date.dt.date), width="stretch", hide_index=True)
    st.download_button("Download CSV", show.to_csv(index=False), "fii_dii_filtered.csv", "text/csv")
    st.caption("Source: 5paisa FII/DII page, collected daily by GitHub Actions. Net = Purchase - Sales (+/-0.1 rounding).")
