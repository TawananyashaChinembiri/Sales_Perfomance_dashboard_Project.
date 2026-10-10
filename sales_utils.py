"""Shared data preparation and KPI logic for the Sale Performance Dashboard.

Both the analysis notebook and the Streamlit app import from this module so that
every number shown anywhere in the project comes from one single source of truth.

Business definitions
--------------------
* Gross Sales        : sum of TotalPrice over ALL orders placed.
* Lost Revenue       : TotalPrice of orders with status Cancelled or Returned.
* Net Revenue        : Gross Sales - Lost Revenue (i.e. Pending + Shipped + Delivered).
* Order Loss Rate    : share of orders that were Cancelled or Returned.
* AOV                : average order value = TotalPrice / orders (net basis unless stated).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

LOST_STATUSES = ["Cancelled", "Returned"]
STATUS_ORDER = ["Pending", "Shipped", "Delivered", "Returned", "Cancelled"]
DOW_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

PROJECT_DIR = Path(__file__).resolve().parent
DEFAULT_DATA_PATH = PROJECT_DIR / "data" / "ecommerce_orders.csv"


def load_orders(path: str | Path = DEFAULT_DATA_PATH) -> pd.DataFrame:
    """Load the raw CSV and add all analysis columns.

    Cleaning decisions (carried over from Project 1 and adapted for sales analysis):
    * Missing CouponCode means "no coupon used" -> label 'No Coupon' (not imputed).
    * Outliers are NOT winsorized: the 8 high TotalPrice orders are genuine large
      orders (Quantity x UnitPrice), and clipping them would understate revenue.
    """
    df = pd.read_csv(path, parse_dates=["Date"])

    df["HasCoupon"] = df["CouponCode"].notna()
    df["CouponCode"] = df["CouponCode"].fillna("No Coupon")

    df["Year"] = df["Date"].dt.year
    df["Month"] = df["Date"].dt.month
    df["Quarter"] = df["Date"].dt.quarter
    df["YearMonth"] = df["Date"].dt.to_period("M").dt.to_timestamp()
    df["YearQuarter"] = df["Date"].dt.year.astype(str) + "-Q" + df["Date"].dt.quarter.astype(str)
    df["DayOfWeek"] = df["Date"].dt.dayofweek
    df["DayName"] = df["DayOfWeek"].map(dict(enumerate(DOW_LABELS)))
    df["IsWeekend"] = df["DayOfWeek"] >= 5

    df["IsLost"] = df["OrderStatus"].isin(LOST_STATUSES)
    df["NetRevenue"] = np.where(df["IsLost"], 0.0, df["TotalPrice"])
    df["LostRevenue"] = np.where(df["IsLost"], df["TotalPrice"], 0.0)

    df["CartFillRatio"] = df["Quantity"] / df["ItemsInCart"]
    df["OrderSizeBand"] = pd.cut(
        df["TotalPrice"],
        bins=[0, 500, 1000, 2000, np.inf],
        labels=["< 500", "500 - 1,000", "1,000 - 2,000", "2,000+"],
        right=False,
    )
    return df


def validate_orders(df: pd.DataFrame) -> dict:
    """Integrity checks. Raises AssertionError if the data breaks a basic contract."""
    checks = {
        "rows": int(len(df)),
        "duplicate_order_ids": int(df["OrderID"].duplicated().sum()),
        "null_cells_excl_coupon": int(df.drop(columns=["CouponCode"]).isna().sum().sum()),
        "max_abs_total_price_error": float((df["TotalPrice"] - df["Quantity"] * df["UnitPrice"]).abs().max()),
        "non_positive_prices_or_qty": int(((df["UnitPrice"] <= 0) | (df["Quantity"] <= 0)).sum()),
        "date_min": str(df["Date"].min().date()),
        "date_max": str(df["Date"].max().date()),
    }
    assert checks["duplicate_order_ids"] == 0, "Duplicate OrderIDs found"
    assert checks["null_cells_excl_coupon"] == 0, "Unexpected nulls"
    assert checks["max_abs_total_price_error"] < 0.01, "TotalPrice != Quantity x UnitPrice"
    assert checks["non_positive_prices_or_qty"] == 0, "Non-positive price or quantity"
    return checks


def kpis(df: pd.DataFrame) -> dict:
    """Headline KPIs for any (possibly filtered) slice of orders."""
    n = len(df)
    if n == 0:
        return dict(orders=0, gross=0.0, net=0.0, lost=0.0, units=0, aov_gross=0.0,
                    aov_net=0.0, loss_rate=0.0, cancel_rate=0.0, return_rate=0.0,
                    customers=0, coupon_share=0.0)
    net_orders = int((~df["IsLost"]).sum())
    return dict(
        orders=n,
        gross=float(df["TotalPrice"].sum()),
        net=float(df["NetRevenue"].sum()),
        lost=float(df["LostRevenue"].sum()),
        units=int(df.loc[~df["IsLost"], "Quantity"].sum()),
        aov_gross=float(df["TotalPrice"].mean()),
        aov_net=float(df["NetRevenue"].sum() / net_orders) if net_orders else 0.0,
        loss_rate=float(df["IsLost"].mean()),
        cancel_rate=float((df["OrderStatus"] == "Cancelled").mean()),
        return_rate=float((df["OrderStatus"] == "Returned").mean()),
        customers=int(df["CustomerID"].nunique()),
        coupon_share=float(df["HasCoupon"].mean()),
    )


def group_summary(df: pd.DataFrame, by: str) -> pd.DataFrame:
    """Orders / revenue / loss-rate table for one categorical dimension."""
    g = df.groupby(by, observed=True)
    out = pd.DataFrame({
        "Orders": g.size(),
        "GrossSales": g["TotalPrice"].sum(),
        "NetRevenue": g["NetRevenue"].sum(),
        "LostRevenue": g["LostRevenue"].sum(),
        "UnitsSold": g.apply(lambda x: x.loc[~x["IsLost"], "Quantity"].sum(), include_groups=False),
        "LossRate": g["IsLost"].mean(),
        "AvgOrderValue": g["TotalPrice"].mean(),
    })
    out["NetShare"] = out["NetRevenue"] / out["NetRevenue"].sum()
    return out.reset_index()


def monthly_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Continuous month index (zero-filled) so trend lines never skip a month."""
    m = df.groupby("YearMonth").agg(
        Orders=("OrderID", "count"),
        GrossSales=("TotalPrice", "sum"),
        NetRevenue=("NetRevenue", "sum"),
        LostRevenue=("LostRevenue", "sum"),
    )
    if m.empty:
        return m.reset_index()
    full = pd.date_range(m.index.min(), m.index.max(), freq="MS")
    m = m.reindex(full, fill_value=0.0)
    m.index.name = "YearMonth"
    m["Orders"] = m["Orders"].astype(int)
    m["NetRevenue_MA3"] = m["NetRevenue"].rolling(3, min_periods=1).mean()
    return m.reset_index()


def h1_comparison(df: pd.DataFrame) -> pd.DataFrame:
    """Like-for-like Jan-Jun comparison. The data ends 30 Jun 2025, so full-year
    totals for 2025 are NOT comparable with 2023/2024; H1 vs H1 is."""
    h1 = df[df["Month"] <= 6]
    return (
        h1.groupby("Year")
        .agg(Orders=("OrderID", "count"), GrossSales=("TotalPrice", "sum"),
             NetRevenue=("NetRevenue", "sum"), LostRevenue=("LostRevenue", "sum"))
        .reset_index()
    )


def chi_square_loss(df: pd.DataFrame, by: str) -> tuple[float, float]:
    """Chi-square test of independence: is order loss (cancel/return) related to `by`?
    Returns (chi2, p_value)."""
    from scipy.stats import chi2_contingency

    table = pd.crosstab(df[by], df["IsLost"])
    chi2, p, _, _ = chi2_contingency(table)
    return float(chi2), float(p)


def fmt_money(x: float) -> str:
    return f"${x:,.0f}"
