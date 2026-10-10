"""Sale Performance Dashboard - Streamlit app.

Run with:  streamlit run app.py
All numbers come from sales_utils.py, the same module used by the analysis notebook.
"""
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

from sales_utils import (DOW_LABELS, STATUS_ORDER, chi_square_loss, group_summary, h1_comparison,
                         kpis, load_orders, monthly_summary, validate_orders)

NET, LOST, GROSS, ACCENT, SOFT, GREEN = "#0072B2", "#D55E00", "#8C8C8C", "#E69F00", "#56B4E9", "#009E73"
STATUS_COLORS = {"Pending": SOFT, "Shipped": NET, "Delivered": GREEN, "Returned": ACCENT, "Cancelled": LOST}
IMG_DIR = Path(__file__).resolve().parent / "images"

st.set_page_config(page_title="Sale Performance Dashboard", page_icon="📊", layout="wide")

st.markdown(
    """
    <style>
    .block-container {padding-top: 1.6rem; padding-bottom: 2rem;}
    div[data-testid="stMetric"] {background:#F6F8FA; border:1px solid #D0D7DE; border-radius:10px; padding:12px 16px;}
    div[data-testid="stMetricLabel"] p {font-size:0.85rem; color:#57606a;}
    h1, h2, h3 {letter-spacing:-0.01em;}
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(show_spinner=False)
def get_data() -> pd.DataFrame:
    d = load_orders()
    validate_orders(d)
    return d


def money(x: float) -> str:
    return f"${x:,.0f}"


def style(fig: go.Figure, height: int = 380, legend: bool = True) -> go.Figure:
    fig.update_layout(
        height=height, margin=dict(l=10, r=10, t=50, b=10), template="plotly_white",
        title=dict(font=dict(size=16)), showlegend=legend,
        legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="right", x=1),
    )
    return fig


df_all = get_data()

# ----------------------------------------------------------------------------- sidebar filters
st.sidebar.title("Filters")
dmin, dmax = df_all["Date"].min().date(), df_all["Date"].max().date()
date_sel = st.sidebar.date_input("Order date range", value=(dmin, dmax), min_value=dmin, max_value=dmax)
if isinstance(date_sel, (tuple, list)) and len(date_sel) == 2:
    d0, d1 = date_sel
else:
    d0 = d1 = date_sel[0] if isinstance(date_sel, (tuple, list)) else date_sel


def multi(label: str, col: str):
    opts = sorted(df_all[col].unique())
    return st.sidebar.multiselect(label, opts, default=opts)


products = multi("Product", "Product")
statuses = st.sidebar.multiselect("Order status", STATUS_ORDER, default=STATUS_ORDER)
payments = multi("Payment method", "PaymentMethod")
referrals = multi("Referral source", "ReferralSource")
coupons = multi("Coupon", "CouponCode")

df = df_all[
    (df_all["Date"].dt.date >= d0) & (df_all["Date"].dt.date <= d1)
    & df_all["Product"].isin(products) & df_all["OrderStatus"].isin(statuses)
    & df_all["PaymentMethod"].isin(payments) & df_all["ReferralSource"].isin(referrals)
    & df_all["CouponCode"].isin(coupons)
].copy()

st.sidebar.markdown("---")
st.sidebar.caption(f"Showing **{len(df):,}** of {len(df_all):,} orders")
with st.sidebar.expander("Metric definitions"):
    st.markdown(
        "- **Gross Sales**: all orders placed\n"
        "- **Lost Revenue**: Cancelled + Returned orders\n"
        "- **Net Revenue**: Gross - Lost (Pending, Shipped, Delivered)\n"
        "- **Loss Rate**: share of orders Cancelled or Returned\n"
        "- **AOV**: average order value"
    )

# ----------------------------------------------------------------------------- header
st.title("📊 Sale Performance Dashboard")
st.caption(f"E-commerce orders · {df_all['Date'].min():%d %b %Y} – {df_all['Date'].max():%d %b %Y} · "
           "Author: Tawananyasha Nigel Chinembiri")

if df.empty:
    st.warning("No orders match the current filters. Widen the filters in the sidebar.")
    st.stop()

K = kpis(df)
c = st.columns(4)
c[0].metric("Gross Sales", money(K["gross"]))
c[1].metric("Net Revenue", money(K["net"]), help="Gross sales minus cancelled and returned orders")
c[2].metric("Lost Revenue", money(K["lost"]), help="Value of cancelled and returned orders")
c[3].metric("Loss Rate", f"{K['loss_rate']:.1%}", help="Share of orders cancelled or returned")
c = st.columns(4)
c[0].metric("Orders", f"{K['orders']:,}")
c[1].metric("Avg Order Value", money(K["aov_gross"]))
c[2].metric("Units Sold (net)", f"{K['units']:,}")
c[3].metric("Orders using a coupon", f"{K['coupon_share']:.1%}")

tabs = st.tabs(["Overview", "Products", "Marketing & Payments", "Order Status & Risk",
                "Timing & Heatmaps", "Key Findings", "Notebook Charts", "Data"])

# ============================================================================= Overview
with tabs[0]:
    monthly = monthly_summary(df)
    fig = go.Figure()
    fig.add_bar(x=monthly["YearMonth"], y=monthly["NetRevenue"], name="Net revenue", marker_color=NET, opacity=0.9)
    fig.add_scatter(x=monthly["YearMonth"], y=monthly["GrossSales"], name="Gross sales", mode="lines+markers",
                    line=dict(color=GROSS, width=2))
    fig.add_scatter(x=monthly["YearMonth"], y=monthly["NetRevenue_MA3"], name="Net, 3-month avg",
                    mode="lines", line=dict(color=ACCENT, width=3.5))
    fig.update_yaxes(tickprefix="$", tickformat=",.0f")
    fig.update_layout(title="Monthly revenue: net vs gross")
    st.plotly_chart(style(fig, 400), width="stretch")

    left, right = st.columns(2)
    with left:
        h1 = h1_comparison(df)
        if len(h1) >= 2:
            f = go.Figure()
            for col, color, name in [("GrossSales", GROSS, "Gross"), ("NetRevenue", NET, "Net"), ("LostRevenue", LOST, "Lost")]:
                f.add_bar(x=[f"H1 {y}" for y in h1["Year"]], y=h1[col], name=name, marker_color=color,
                          text=[f"${v/1000:,.0f}k" for v in h1[col]], textposition="outside")
            f.update_layout(title="Like-for-like: Jan–Jun by year", barmode="group")
            f.update_yaxes(tickprefix="$", tickformat=",.0f", range=[0, h1["GrossSales"].max() * 1.2])
            st.plotly_chart(style(f), width="stretch")
            st.caption("The data ends on 30 Jun 2025, so full-year 2025 is not comparable with 2023/2024. "
                       "Jan–Jun is compared across all three years.")
        else:
            st.info("Select a date range covering Jan–Jun of at least two years to see the H1 comparison.")
    with right:
        q = df.groupby("YearQuarter").agg(Net=("NetRevenue", "sum"), Lost=("LostRevenue", "sum")).reset_index()
        f = go.Figure()
        f.add_bar(x=q["YearQuarter"], y=q["Net"], name="Net revenue", marker_color=NET)
        f.add_bar(x=q["YearQuarter"], y=q["Lost"], name="Lost", marker_color=LOST)
        f.update_layout(title="Quarterly gross sales: kept vs lost", barmode="stack")
        f.update_yaxes(tickprefix="$", tickformat=",.0f")
        st.plotly_chart(style(f), width="stretch")
        st.caption("A quarter with fewer than three months of data (for example partial first/last quarters "
                   "under a custom date range) will look lower than it really is.")

# ============================================================================= Products
with tabs[1]:
    prod = group_summary(df, "Product").sort_values("NetRevenue")
    left, right = st.columns([1.3, 1])
    with left:
        f = go.Figure()
        f.add_bar(y=prod["Product"], x=prod["NetRevenue"], name="Net revenue", orientation="h", marker_color=NET,
                  text=[f"${v/1000:,.0f}k" for v in prod["NetRevenue"]], textposition="inside")
        f.add_bar(y=prod["Product"], x=prod["LostRevenue"], name="Lost", orientation="h", marker_color=LOST)
        f.update_layout(title="Revenue by product", barmode="stack")
        f.update_xaxes(tickprefix="$", tickformat=",.0f")
        st.plotly_chart(style(f, 420), width="stretch")
    with right:
        f = px.bar(prod, y="Product", x="UnitsSold", orientation="h", color_discrete_sequence=[SOFT],
                   text="UnitsSold", title="Units sold (net of cancelled/returned)")
        f.update_traces(textposition="outside")
        st.plotly_chart(style(f, 420, legend=False), width="stretch")

    left, right = st.columns(2)
    with left:
        p2 = group_summary(df, "Product").sort_values("AvgOrderValue", ascending=False)
        f = px.bar(p2, x="Product", y="AvgOrderValue", color_discrete_sequence=[NET], title="Average order value by product",
                   text=[f"${v:,.0f}" for v in p2["AvgOrderValue"]])
        f.add_hline(y=df["TotalPrice"].mean(), line_dash="dash", line_color=ACCENT,
                    annotation_text=f"Overall {money(df['TotalPrice'].mean())}")
        f.update_yaxes(tickprefix="$", tickformat=",.0f")
        st.plotly_chart(style(f, legend=False), width="stretch")
    with right:
        pr = group_summary(df, "Product")
        f = px.scatter(pr, x="AvgOrderValue", y="LossRate", size="Orders", text="Product", title="AOV vs loss rate (bubble = orders)",
                       color_discrete_sequence=[NET])
        f.update_traces(textposition="top center")
        f.update_yaxes(tickformat=".0%")
        f.update_xaxes(tickprefix="$", tickformat=",.0f")
        st.plotly_chart(style(f, legend=False), width="stretch")

    show = group_summary(df, "Product").sort_values("NetRevenue", ascending=False)
    st.dataframe(show.style.format({"GrossSales": "${:,.0f}", "NetRevenue": "${:,.0f}", "LostRevenue": "${:,.0f}",
                                    "LossRate": "{:.1%}", "AvgOrderValue": "${:,.0f}", "NetShare": "{:.1%}"}),
                 width="stretch", hide_index=True)

# ============================================================================= Marketing & Payments
with tabs[2]:
    ref = group_summary(df, "ReferralSource").sort_values("NetRevenue", ascending=False)
    cols = st.columns(3)
    for col, (metric, title, color, fmt) in zip(cols, [("NetRevenue", "Net revenue by referral source", NET, "$"),
                                                       ("Orders", "Orders by referral source", SOFT, ""),
                                                       ("AvgOrderValue", "AOV by referral source", ACCENT, "$")]):
        f = px.bar(ref, x="ReferralSource", y=metric, title=title, color_discrete_sequence=[color])
        if fmt:
            f.update_yaxes(tickprefix="$", tickformat=",.0f")
        col.plotly_chart(style(f, 340, legend=False), width="stretch")

    cp = group_summary(df, "CouponCode").sort_values("NetRevenue", ascending=False)
    cmap = {k: (GROSS if k == "No Coupon" else NET) for k in cp["CouponCode"]}
    cols = st.columns(3)
    for col, (metric, title, tick) in zip(cols, [("Orders", "Orders by coupon", None),
                                                 ("AvgOrderValue", "AOV by coupon", "$"),
                                                 ("LossRate", "Loss rate by coupon", "%")]):
        f = px.bar(cp, x="CouponCode", y=metric, color="CouponCode", color_discrete_map=cmap, title=title)
        if tick == "$":
            f.update_yaxes(tickprefix="$", tickformat=",.0f")
        if tick == "%":
            f.update_yaxes(tickformat=".0%")
        col.plotly_chart(style(f, 340, legend=False), width="stretch")

    pay = group_summary(df, "PaymentMethod").sort_values("NetRevenue", ascending=False)
    f = go.Figure()
    f.add_bar(x=pay["PaymentMethod"], y=pay["NetRevenue"], name="Net revenue", marker_color=NET)
    f.add_bar(x=pay["PaymentMethod"], y=pay["LostRevenue"], name="Lost revenue", marker_color=LOST)
    f.update_layout(title="Net vs lost revenue by payment method", barmode="group")
    f.update_yaxes(tickprefix="$", tickformat=",.0f")
    st.plotly_chart(style(f, 360), width="stretch")

# ============================================================================= Order status & risk
with tabs[3]:
    st_df = df.groupby("OrderStatus").agg(Orders=("OrderID", "count"), Value=("TotalPrice", "sum")).reindex(STATUS_ORDER).dropna().reset_index()
    left, right = st.columns(2)
    with left:
        f = px.bar(st_df, x="OrderStatus", y="Orders", color="OrderStatus", color_discrete_map=STATUS_COLORS,
                   title="Orders by status", text="Orders")
        st.plotly_chart(style(f, legend=False), width="stretch")
    with right:
        f = px.bar(st_df, x="OrderStatus", y="Value", color="OrderStatus", color_discrete_map=STATUS_COLORS,
                   title="Order value by status")
        f.update_yaxes(tickprefix="$", tickformat=",.0f")
        st.plotly_chart(style(f, legend=False), width="stretch")

    st.subheader("Where do cancellations and returns concentrate?")
    st.caption("Bars show the loss rate with 95% confidence intervals; the dashed line is the overall rate for the "
               "current filter. The chi-square p-value tests whether differences between segments are larger than "
               "random variation (p < 0.05 would be significant).")
    overall = df["IsLost"].mean()
    dims = {"Product": "Product", "PaymentMethod": "Payment method", "ReferralSource": "Referral source", "CouponCode": "Coupon"}
    cols = st.columns(2)
    for i, (dim, label) in enumerate(dims.items()):
        g = df.groupby(dim)["IsLost"].agg(["mean", "count"]).sort_values("mean").reset_index()
        g["ci"] = 1.96 * np.sqrt(g["mean"] * (1 - g["mean"]) / g["count"])
        try:
            _, p = chi_square_loss(df, dim)
            ptxt = f"chi-square p = {p:.2f}"
        except ValueError:
            ptxt = "test needs 2+ segments"
        f = go.Figure(go.Bar(y=g[dim], x=g["mean"], orientation="h",
                             marker_color=[LOST if v > overall else NET for v in g["mean"]],
                             error_x=dict(type="data", array=g["ci"], color="#444"),
                             text=[f"{v:.1%}" for v in g["mean"]], textposition="inside"))
        f.add_vline(x=overall, line_dash="dash", line_color="#333")
        f.update_layout(title=f"Loss rate by {label.lower()} · {ptxt}")
        f.update_xaxes(tickformat=".0%", range=[0, 0.65])
        cols[i % 2].plotly_chart(style(f, 330, legend=False), width="stretch")

# ============================================================================= Timing & heatmaps
with tabs[4]:
    dow = group_summary(df, "DayName").set_index("DayName").reindex(DOW_LABELS).dropna(how="all").reset_index()
    left, right = st.columns(2)
    wk = {d: (ACCENT if d in ("Sat", "Sun") else NET) for d in DOW_LABELS}
    with left:
        f = px.bar(dow, x="DayName", y="Orders", color="DayName", color_discrete_map=wk, title="Orders by weekday (orange = weekend)", text="Orders")
        st.plotly_chart(style(f, legend=False), width="stretch")
    with right:
        f = px.bar(dow, x="DayName", y="NetRevenue", color="DayName", color_discrete_map=wk, title="Net revenue by weekday")
        f.update_yaxes(tickprefix="$", tickformat=",.0f")
        st.plotly_chart(style(f, legend=False), width="stretch")

    left, right = st.columns(2)
    with left:
        pv = df.pivot_table(index="Month", columns="Year", values="NetRevenue", aggfunc="sum")
        pv = pv.reindex(range(1, 13))
        if 2025 in pv.columns:
            pv.loc[pv.index > 6, 2025] = np.nan
        pv.index = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        f = px.imshow(pv / 1000, text_auto=".0f", color_continuous_scale="Blues", aspect="auto",
                      title="Net revenue ($k) by month and year", labels=dict(color="$k"))
        f.update_xaxes(type="category")
        st.plotly_chart(style(f, 480, legend=False), width="stretch")
        st.caption("Blank cells = no data yet (the dataset ends 30 Jun 2025) or filtered out.")
    with right:
        pp = df.pivot_table(index="Product", columns="ReferralSource", values="NetRevenue", aggfunc="sum")
        f = px.imshow(pp / 1000, text_auto=".0f", color_continuous_scale="Blues", aspect="auto",
                      title="Net revenue ($k): product × referral source", labels=dict(color="$k"))
        st.plotly_chart(style(f, 480, legend=False), width="stretch")

    left, right = st.columns(2)
    with left:
        f = px.histogram(df, x="TotalPrice", nbins=30, color_discrete_sequence=[NET], title="Distribution of order value")
        f.add_vline(x=df["TotalPrice"].mean(), line_color=ACCENT, line_width=3, annotation_text="mean")
        f.add_vline(x=df["TotalPrice"].median(), line_color=LOST, line_dash="dash", annotation_text="median", annotation_position="bottom right")
        f.update_xaxes(tickprefix="$", tickformat=",.0f")
        st.plotly_chart(style(f, legend=False), width="stretch")
    with right:
        band = group_summary(df, "OrderSizeBand")
        f = go.Figure()
        f.add_bar(x=band["OrderSizeBand"].astype(str), y=band["NetRevenue"], name="Net revenue", marker_color=NET)
        f.add_bar(x=band["OrderSizeBand"].astype(str), y=band["LostRevenue"], name="Lost", marker_color=LOST)
        f.update_layout(title="Revenue by order-size band", barmode="stack")
        f.update_yaxes(tickprefix="$", tickformat=",.0f")
        st.plotly_chart(style(f), width="stretch")

# ============================================================================= Key findings
with tabs[5]:
    st.subheader("Key findings for the current filter")
    prod_s = group_summary(df, "Product").sort_values("NetRevenue", ascending=False)
    ref_s = group_summary(df, "ReferralSource").sort_values("NetRevenue", ascending=False)
    pay_s = group_summary(df, "PaymentMethod").sort_values("NetRevenue", ascending=False)
    lines = [
        f"**Revenue.** Gross sales of {money(K['gross'])} produced {money(K['net'])} of net revenue; "
        f"{money(K['lost'])} ({K['lost'] / K['gross']:.0%} of gross) was lost to cancellations and returns.",
        f"**Order loss.** {K['loss_rate']:.1%} of orders were cancelled or returned "
        f"({K['cancel_rate']:.1%} cancelled, {K['return_rate']:.1%} returned).",
        f"**Products.** {prod_s.iloc[0]['Product']} leads on net revenue ({money(prod_s.iloc[0]['NetRevenue'])}, "
        f"{prod_s.iloc[0]['NetShare']:.0%} of total) and {prod_s.iloc[-1]['Product']} is lowest "
        f"({money(prod_s.iloc[-1]['NetRevenue'])}, {prod_s.iloc[-1]['NetShare']:.0%}).",
        f"**Marketing.** {ref_s.iloc[0]['ReferralSource']} is the top referral source for net revenue "
        f"({money(ref_s.iloc[0]['NetRevenue'])}); {pay_s.iloc[0]['PaymentMethod']} is the top payment method "
        f"({money(pay_s.iloc[0]['NetRevenue'])}).",
    ]
    big = df["TotalPrice"] >= 1000
    if big.any() and df["NetRevenue"].sum() > 0:
        lines.append(f"**Large orders.** Orders of $1,000+ are {big.mean():.0%} of orders but bring in "
                     f"{df.loc[big, 'NetRevenue'].sum() / df['NetRevenue'].sum():.0%} of net revenue.")
    h1 = h1_comparison(df).set_index("Year")
    if {2023, 2024, 2025}.issubset(h1.index):
        lines.append(
            f"**Trend (Jan–Jun, like for like).** Gross sales: {money(h1.loc[2023, 'GrossSales'])} → "
            f"{money(h1.loc[2024, 'GrossSales'])} ({h1.loc[2024, 'GrossSales'] / h1.loc[2023, 'GrossSales'] - 1:+.1%}) → "
            f"{money(h1.loc[2025, 'GrossSales'])} ({h1.loc[2025, 'GrossSales'] / h1.loc[2024, 'GrossSales'] - 1:+.1%}). "
            f"Orders: {int(h1.loc[2023, 'Orders'])} → {int(h1.loc[2024, 'Orders'])} → {int(h1.loc[2025, 'Orders'])}."
        )
    for ln in lines:
        st.markdown("- " + ln)

    st.subheader("Are segment differences real?")
    rows = []
    for dim, label in [("Product", "Product"), ("PaymentMethod", "Payment method"), ("ReferralSource", "Referral source"),
                       ("CouponCode", "Coupon"), ("DayName", "Weekday"), ("Year", "Year")]:
        try:
            chi2, p = chi_square_loss(df, dim)
            rows.append({"Dimension": label, "Chi-square": round(chi2, 2), "p-value": round(p, 3),
                         "Significant at 5%?": "Yes" if p < 0.05 else "No"})
        except ValueError:
            rows.append({"Dimension": label, "Chi-square": None, "p-value": None, "Significant at 5%?": "n/a"})
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    st.info("Loss rates differ a little between segments, but unless a row above says **Yes**, the gap is within "
            "normal random variation. Treat such gaps as leads to monitor rather than proven problems.")

    st.subheader("Caveats")
    st.markdown(
        "- **Pending orders** (about a fifth of orders) are counted in net revenue and could still be cancelled.\n"
        "- **2025 is a half year** (data ends 30 Jun 2025), so use the Jan–Jun comparison, not full-year totals.\n"
        "- **Repeat customers are almost absent** (1,189 unique customers across 1,200 orders), so customer-lifetime analysis is not meaningful.\n"
        "- **No outlier capping**: the 8 unusually large orders are genuine (Quantity × UnitPrice) and kept in all totals."
    )

# ============================================================================= Notebook charts
with tabs[6]:
    st.subheader("Charts saved by the analysis notebook")
    st.caption("Static PNGs generated by `Sales_Performance_Analysis.ipynb` on the full dataset (no filters).")
    images = sorted(IMG_DIR.glob("*.png"))
    if not images:
        st.info("No images found. Run the notebook first to generate them into the `images/` folder.")
    for i in range(0, len(images), 2):
        cols = st.columns(2)
        for col, path in zip(cols, images[i:i + 2]):
            col.image(str(path), caption=path.stem.replace("_", " "), width="stretch")

# ============================================================================= Data
with tabs[7]:
    st.subheader("Filtered orders")
    show_cols = ["OrderID", "Date", "CustomerID", "Product", "Quantity", "UnitPrice", "TotalPrice", "OrderStatus",
                 "PaymentMethod", "CouponCode", "ReferralSource", "NetRevenue", "LostRevenue"]
    st.dataframe(df[show_cols].sort_values("Date"), width="stretch", hide_index=True)
    st.download_button("Download filtered data (CSV)", df[show_cols].to_csv(index=False).encode("utf-8"),
                       file_name="filtered_orders.csv", mime="text/csv")
