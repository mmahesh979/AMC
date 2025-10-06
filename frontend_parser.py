from __future__ import annotations

import pandas as pd


def _coerce_numeric(series: pd.Series) -> pd.Series:
    if series is None:
        return series
    return (
        pd.to_numeric(
            series.astype(str)
            .str.replace(",", "", regex=False)
            .str.replace("%", "", regex=False)
            .str.replace("₹", "", regex=False)
            .str.replace("$", "", regex=False)
            .str.strip(),
            errors="coerce",
        )
        .fillna(0.0)
    )


def compute_frontend_table(df: pd.DataFrame) -> pd.DataFrame:
    """Return a DataFrame with columns needed by the frontend table.

    Output columns (in order):
    - Symbol
    - ISIN
    - Sector
    - Qty
    - Average Price
    - Investment Value
    - Previous Closing Price
    - Present Value
    - Net Pnl
    - PNL % (from original df)
    """

    # Validate required columns as they are expected to be system-generated and stable
    required = [
        "Symbol",
        "ISIN",
        "Quantity Available",
        "Average Price",
        "Previous Closing Price",
        "Unrealized P&L Pct.",
    ]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns in holdings DataFrame: {missing}")

    # Build the output frame with safe defaults
    out = pd.DataFrame()
    out["Symbol"] = df["Symbol"]
    out["ISIN"] = df["ISIN"]
    out["Sector"] = df["Sector"] if "Sector" in df.columns else ""

    qty = _coerce_numeric(df["Quantity Available"])
    avgp = _coerce_numeric(df["Average Price"])
    prev = _coerce_numeric(df["Previous Closing Price"])

    out["Qty"] = qty.round(2)
    out["Average Price"] = avgp.round(2)
    out["Investment Value"] = (qty * avgp).round(2)
    out["Previous Closing Price"] = prev.round(2)
    out["Present Value"] = (prev * qty).round(2)
    out["Net Pnl"] = (out["Present Value"] - out["Investment Value"]).round(2)

    # Append PNL% as provided in the source (rename from 'Unrealized P&L Pct.')
    pnlpct = _coerce_numeric(df["Unrealized P&L Pct."])
    # Format as whole-percent text with a trailing '%'
    out["PNL%"] = pnlpct.round(0).astype(int).astype(str) + "%"

    return out
