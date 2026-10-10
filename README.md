# Sale Performance Dashboard

Sales analysis of 1,200 e-commerce orders (Jan 2023 - Jun 2025), built on the Project 1 dataset and cleaning decisions.

## Contents
| Path | Purpose |
|---|---|
| `Sales_Performance_Analysis.ipynb` | Analysis notebook. Generates and **saves all charts** to `images/` and summary tables to `outputs/` |
| `app.py` | Streamlit dashboard (interactive filters, 8 tabs) |
| `sales_utils.py` | Shared loading, validation and KPI logic used by both the notebook and the app |
| `data/ecommerce_orders.csv` | Source data |
| `images/` | 15 PNG charts saved by the notebook |
| `outputs/` | `summary_metrics.json` and summary CSVs |

## Run it
```bash
pip install -r requirements.txt

# 1. (Optional) regenerate the charts and summaries
jupyter nbconvert --to notebook --execute --inplace Sales_Performance_Analysis.ipynb
#    or open the notebook in Jupyter and Run All

# 2. Launch the dashboard
streamlit run app.py
```
Run both commands from this folder.

## Metric definitions
* **Gross Sales** - `TotalPrice` of all orders
* **Lost Revenue** - `TotalPrice` of Cancelled + Returned orders
* **Net Revenue** - Gross - Lost (Pending + Shipped + Delivered)
* **Loss Rate** - share of orders Cancelled or Returned

## Methodology notes
* Blank `CouponCode` = no coupon used, labelled "No Coupon" (not imputed), as in Project 1.
* Outliers are **not** capped here (unlike Project 1): the 8 large orders are genuine and capping them would understate revenue.
* Data ends 30 Jun 2025, so year-over-year comparisons use Jan-Jun vs Jan-Jun.
* Segment differences in loss rate are tested with chi-square; none is significant at 5%, so they are reported as leads, not conclusions.
* Pending orders count towards net revenue and may still be cancelled.
