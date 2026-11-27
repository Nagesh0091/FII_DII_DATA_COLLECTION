"""FII / DII Data Science Lab (Streamlit): leak-free walk-forward tests vs baselines."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from sklearn.cluster import KMeans
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import balanced_accuracy_score, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

# CHANGE if your repo/branch differs (use the "Raw" link of the CSV)
CSV_URL = ("https://raw.githubusercontent.com/Nagesh0091/FII_DII_DATA_COLLECTION/"
           "main/fii_dii_cash_history.csv")
st.set_page_config(page_title="FII / DII Data Science Lab", layout="wide")
if "trials" not in st.session_state:
    st.session_state.trials = 0


@st.cache_data(ttl=3600)
def load(url):
    df = pd.read_csv(url, parse_dates=["Date"]).sort_values("Date").reset_index(drop=True)
    df.columns = [c.replace("_Cr", "") for c in df.columns]
    return df


@st.cache_data(ttl=3600)
def load_market(start, end):
    import yfinance as yf
    parts = {}
    for sym in ("^NSEI", "^INDIAVIX"):
        d = yf.download(sym, start=start - pd.Timedelta(days=10), end=end + pd.Timedelta(days=5),
                        progress=False, auto_adjust=False)
        if isinstance(d.columns, pd.MultiIndex):
            d.columns = d.columns.get_level_values(0)
        d.index = pd.to_datetime(d.index).tz_localize(None)
        parts[sym] = d
    n, v = parts["^NSEI"], parts["^INDIAVIX"]
    if n.empty:
        raise RuntimeError("no Nifty data returned")
    mk = pd.DataFrame({"Ret": n.Close.pct_change() * 100, "Range": (n.High - n.Low) / n.Close * 100})
    if not v.empty:
        mk["VIX"], mk["VIXchg"] = v.Close.reindex(mk.index), v.Close.pct_change().reindex(mk.index) * 100
    return mk.rename_axis("Date").reset_index()


def streak(s):
    out, run = [], 0
    for v in np.sign(s):
        run = (run + 1 if run > 0 else 1) if v > 0 else (run - 1 if run < 0 else -1)
        out.append(run)
    return pd.Series(out, index=s.index)


def build(df, mk):
    d = df[df.Date.dt.weekday < 5].copy().reset_index(drop=True)      # drop Muhurat/weekend rows
    d["Total"] = d.FII_Net + d.DII_Net
    d["FII_share"] = (d.FII_Gross_Purchase + d.FII_Gross_Sales) / (
        d.FII_Gross_Purchase + d.FII_Gross_Sales + d.DII_Gross_Purchase + d.DII_Gross_Sales)
    for n in (3, 5, 10):
        d[f"FII_roll{n}"], d[f"DII_roll{n}"] = d.FII_Net.rolling(n).sum(), d.DII_Net.rolling(n).sum()
    r = d.FII_Net.rolling(20, min_periods=5)
    d["FII_z"] = (d.FII_Net - r.mean()) / r.std()
    d["FII_streak"], d["DII_streak"] = streak(d.FII_Net), streak(d.DII_Net)
    d["Weekday"] = d.Date.dt.weekday
    if mk is not None:
        d = d.merge(mk, on="Date", how="inner").reset_index(drop=True)  # trading-day aligned
        d["NextRet"], d["NextRange"] = d.Ret.shift(-1), d.Range.shift(-1)
        d["Range5"] = d.Range.rolling(5).mean()
    d["NextFII"] = d.FII_Net.shift(-1)                                   # target uses NEXT day only
    return d


# ---------------- modelling ----------------
def make_model(task, name):
    if task == "reg":
        return (make_pipeline(StandardScaler(), Ridge(alpha=10)) if name.startswith("Ridge")
                else RandomForestRegressor(n_estimators=150, max_depth=3, min_samples_leaf=5, random_state=0))
    return (make_pipeline(StandardScaler(), LogisticRegression(C=0.3, max_iter=1000)) if name.startswith("Logistic")
            else RandomForestClassifier(n_estimators=150, max_depth=3, min_samples_leaf=5, random_state=0))


def lab(task, y, i):
    """Training labels from rows < i only (thresholds never see the test day)."""
    if task == "reg": return y[:i], y[i], None
    if task == "vol":
        thr = np.quantile(y[:i], .75)
        return (y[:i] >= thr).astype(int), int(y[i] >= thr), thr
    return (y[:i] > 0).astype(int), int(y[i] > 0), None


def walk(X, y, pers, task, name, lo, hi):
    rows = []
    for i in range(lo, hi):
        yt, yi, thr = lab(task, y, i)
        if task == "reg":
            p = float(make_model(task, name).fit(X[:i], yt).predict(X[i:i + 1])[0])
            rows.append((i, yi, p, pers[i], np.nan, np.nan))
            continue
        prob = float(yt.mean()) if len(set(yt)) < 2 else float(
            make_model(task, name).fit(X[:i], yt).predict_proba(X[i:i + 1])[0, 1])
        pp = int(pers[i] >= thr) if task == "vol" else int(pers[i] > 0)
        rows.append((i, yi, int(prob >= .5), pp, int(yt.mean() >= .5), prob))
    return pd.DataFrame(rows, columns=["i", "y", "pred", "pers", "maj", "prob"])


def boot_ci(a, block=5, B=800):
    rng, n = np.random.default_rng(0), len(a)
    k = int(np.ceil(n / block))
    out = []
    for _ in range(B):
        s = rng.integers(0, max(n - block + 1, 1), k)
        out.append(a[np.concatenate([np.arange(j, min(j + block, n)) for j in s])[:n]].mean())
    return np.percentile(out, [2.5, 97.5])


def summarise(r, task):
    n = len(r)
    if task == "reg":
        em, eb = (r.pred - r.y).abs().values, (r.pers - r.y).abs().values
        diff = eb - em
        lo, hi = boot_ci(diff)
        tab = pd.DataFrame({"Method": ["Model", "Baseline (5-day avg range)"], "MAE": [em.mean(), eb.mean()]}).round(3)
        return tab, diff, (lo, hi), f"MAE improvement vs baseline {diff.mean():+.3f} (95% CI {lo:+.3f} to {hi:+.3f})"
    cm, cp, cj = (r.pred == r.y).values, (r.pers == r.y).values, (r.maj == r.y).values
    best = cp if cp.mean() >= cj.mean() else cj
    diff = cm.astype(float) - best.astype(float)
    lo, hi = boot_ci(diff)
    ci = lambda a: "%.0f%% to %.0f%%" % tuple(boot_ci(a.astype(float)) * 100)
    auc = roc_auc_score(r.y, r.prob) if r.y.nunique() > 1 else np.nan
    tab = pd.DataFrame({"Method": ["Model", "Persistence baseline", "Majority baseline"],
                        "Accuracy %": [cm.mean() * 100, cp.mean() * 100, cj.mean() * 100],
                        "95% CI": [ci(cm), ci(cp), ci(cj)],
                        "Balanced acc %": [balanced_accuracy_score(r.y, r.pred) * 100,
                                           balanced_accuracy_score(r.y, r.pers) * 100,
                                           balanced_accuracy_score(r.y, r.maj) * 100],
                        "ROC-AUC": [auc, np.nan, np.nan]}).round(2)
    return tab, diff, (lo, hi), f"Accuracy gain vs best baseline {diff.mean() * 100:+.1f} pts (95% CI {lo * 100:+.1f} to {hi * 100:+.1f})"


# ---------------- load ----------------
try:
    raw = load(CSV_URL)
except Exception as e:
    st.error(f"Could not load data from GitHub: {e}"); st.stop()
try:
    mk = load_market(raw.Date.min(), raw.Date.max())
except Exception as e:
    mk = None
    st.info(f"Market data unavailable ({e}). Only flow-based problems (P4, P5, P6) will work.")
D = build(raw, mk)

st.title("FII / DII Data Science Lab")
st.caption(f"{len(D)} trading days, up to {D.Date.max():%d %b %Y}. Research only, not investment advice. "
           "Flows are published after the close, so day-t features predict day t+1 only.")
st.sidebar.header("Validation settings")
min_train = st.sidebar.slider("Minimum training days", 20, 60, 40)
holdout = st.sidebar.slider("Final hold-out days (use once)", 5, 25, 15)
st.sidebar.metric("Model runs this session", st.session_state.trials,
                  help="Many trials on a small sample create false discoveries. Count them.")
if len(D) < 70:
    st.warning(f"Only {len(D)} rows. Results are very uncertain. Treat as a learning tool until about 250 rows.")

t1, t2, t3, t4 = st.tabs(["Walk-forward models (P1-P4)", "Regimes (P5)", "Unusual days (P6)", "Method"])

# ---------------- P1-P4 ----------------
with t1:
    tasks = {"P1 Next-day Nifty direction": ("dir", "NextRet", "Ret"),
             "P2 Next-day Nifty range %": ("reg", "NextRange", "Range5"),
             "P3 High-volatility next day (top 25%)": ("vol", "NextRange", "Range"),
             "P4 Next-day FII net is positive": ("fii", "NextFII", "FII_Net")}
    pick = st.selectbox("Problem", list(tasks))
    task, ycol, pcol = tasks[pick]
    if task != "fii" and mk is None:
        st.warning("This problem needs Nifty data, which could not be loaded."); st.stop()
    cand = ["FII_Net", "DII_Net", "Total", "FII_share", "FII_roll3", "FII_roll5", "FII_roll10", "DII_roll5",
            "FII_z", "FII_streak", "DII_streak", "Weekday"] + (["Ret", "Range", "VIX", "VIXchg"] if mk is not None else [])
    cand = [c for c in cand if c in D]
    feats = st.multiselect("Features (keep it small)", cand,
                           [c for c in ["FII_Net", "DII_Net", "FII_roll5", "FII_streak", "FII_z", "Ret", "Range", "VIX"] if c in cand])
    if len(feats) > 15: st.warning("More than 15 features on ~80 rows invites overfitting.")
    mname = st.radio("Model", ["Ridge regression" if task == "reg" else "Logistic regression (L2)",
                               "Random forest (shallow)"], horizontal=True)
    cols = list(dict.fromkeys(feats + [ycol, pcol]))
    M = D.dropna(subset=cols).reset_index(drop=True)
    lab_rows = M[M[ycol].notna()].reset_index(drop=True)
    X, y, pers = lab_rows[feats].values, lab_rows[ycol].values, lab_rows[pcol].values
    n = len(lab_rows); dev_end = n - holdout
    st.write(f"Usable labelled rows: **{n}**  |  development tests: **{max(dev_end - min_train, 0)}**  |  hold-out: **{holdout}**")
    ok = bool(feats) and dev_end - min_train >= 8
    if not ok: st.warning("Pick features and make sure at least 8 development test days remain (lower the minimum training days or hold-out).")
    c1, c2 = st.columns(2)
    if c1.button("Run walk-forward test (development period)", disabled=not ok):
        st.session_state.trials += 1
        st.session_state.dev = (pick, mname, walk(X, y, pers, task, mname, min_train, dev_end))
    if c2.button("Run FINAL hold-out (use once, then stop tuning)", disabled=not ok):
        st.session_state.trials += 1
        st.session_state.hold = (pick, mname, walk(X, y, pers, task, mname, dev_end, n))
    for key, title in (("dev", "Development results"), ("hold", "Final hold-out results")):
        if key in st.session_state and st.session_state[key][0] == pick:
            _, nm, r = st.session_state[key]
            tab, diff, (lo, hi), verdict = summarise(r, task)
            st.subheader(f"{title}: {nm}  (n = {len(r)} test days)")
            st.dataframe(tab, hide_index=True, width="stretch")
            (st.success if lo > 0 else st.info)(
                verdict + (".  Clearly better than baseline." if lo > 0 else ".  Not clearly better than the baseline."))
            f = go.Figure(go.Scatter(y=np.cumsum(diff), mode="lines", line_color="#1f5fbf"))
            f.update_layout(title="Cumulative advantage over baseline (above 0 = model ahead)",
                            height=280, xaxis_title="Test day #")
            st.plotly_chart(f, width="stretch")
    if task != "reg" and "dev" in st.session_state and st.session_state.dev[0] == pick:
        yfull = (y >= np.quantile(y, .75)).astype(int) if task == "vol" else (y > 0).astype(int)
        latest = D.dropna(subset=feats).iloc[-1:]
        if len(set(yfull)) > 1 and len(latest):
            pr = make_model(task, mname).fit(X, yfull).predict_proba(latest[feats].values)[0, 1]
            st.caption(f"Experimental output for the next session, from the latest row ({latest.Date.iloc[0]:%d %b}): "
                       f"probability {pr:.0%}. Only meaningful if the model clearly beats its baseline above.")

# ---------------- P5 ----------------
with t2:
    st.caption("Descriptive grouping of days by flow behaviour. Fitted on the whole sample, so it describes the past "
               "and is not a tested forecast.")
    k = st.slider("Number of regimes", 2, 5, 3)
    Z = StandardScaler().fit_transform(D[["FII_Net", "DII_Net", "Total"]])
    D["Regime"] = KMeans(k, n_init=10, random_state=0).fit_predict(Z)
    run_len = D.groupby((D.Regime != D.Regime.shift()).cumsum()).size()
    prof = D.groupby("Regime").agg(Days=("Date", "size"), FII_net_avg=("FII_Net", "mean"),
                                   DII_net_avg=("DII_Net", "mean"), Total_avg=("Total", "mean"))
    if mk is not None:
        prof["Next_day_ret_%"], prof["Next_day_range_%"] = D.groupby("Regime").NextRet.mean(), D.groupby("Regime").NextRange.mean()
    prof["Avg_run_days"] = D.groupby("Regime").apply(
        lambda g: run_len.loc[(D.Regime != D.Regime.shift()).cumsum()[g.index].unique()].mean())
    st.dataframe(prof.round(1), width="stretch")
    f = go.Figure(go.Scatter(x=D.Date, y=D.Regime, mode="markers", marker=dict(color=D.Regime, size=9, colorscale="Viridis")))
    f.update_layout(title="Regime by day", yaxis_title="Regime", height=300)
    st.plotly_chart(f, width="stretch")

# ---------------- P6 ----------------
with t3:
    st.caption("Robust z-score (median and MAD). Days with |z| of 3 or more on FII or DII net are flagged.")
    for c in ("FII_Net", "DII_Net"):
        med = D[c].median(); mad = (D[c] - med).abs().median() * 1.4826
        D[f"z_{c}"] = (D[c] - med) / mad
    flag = D[(D.z_FII_Net.abs() >= 3) | (D.z_DII_Net.abs() >= 3)][["Date", "FII_Net", "DII_Net", "z_FII_Net", "z_DII_Net"]]
    st.write(f"Flagged days: **{len(flag)}** of {len(D)}. Compare each with market news to explain it.")
    st.dataframe(flag.assign(Date=flag.Date.dt.date).round(1), hide_index=True, width="stretch")

# ---------------- Method ----------------
with t4:
    st.markdown("""
- **No leakage:** features use day-t information only; targets are the next trading day. Muhurat/weekend rows are removed.
- **Walk-forward:** the model is re-fitted on all earlier days and predicts one new day, over and over. No shuffling.
- **Thresholds** (for example the top-25% range) are recomputed from training days only.
- **Baselines:** persistence ("same as today"), majority class, and a 5-day average range. A model only counts if its 95% block-bootstrap interval for the gain over the best baseline stays above zero.
- **Hold-out:** the last days are kept for one final test. Tuning after seeing it makes it meaningless.
- **Trial counter:** every run adds to a count; many runs on about 80 rows will find "winners" by chance.
- **Limits:** about 80 rows, one 4-month period. "No edge found" is a normal and valid result. Not investment advice.
""")
