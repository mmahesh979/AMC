#!/usr/bin/env python3
import csv
import datetime as dt
import time
from urllib.parse import quote
import requests

# -------- Config --------
SYMBOL = "M&M"          # change to your symbol (e.g., RELIANCE, TCS, HDFCBANK, etc.)
SERIES = '["EQ"]'       # common delivery series for equities
YEARS = 1              # how many years back
CHUNK_DAYS = 180        # query window; reduce if you hit 413/429/5xx
OUT_CSV = f"{SYMBOL.replace('/', '_').replace('&','and')}_NSE_10y.csv"
BASE = "https://www.nseindia.com"
HIST_URL = BASE + "/api/historical/cm/equity"

# -------- Helpers --------
def ddmmyyyy(d: dt.date) -> str:
    return d.strftime("%d-%m-%Y")

def fetch_chunk(sess: requests.Session, symbol: str, d1: dt.date, d2: dt.date):
    """
    Returns list of dict rows for [d1, d2] inclusive.
    """
    params = {
        "symbol": symbol,
        "series": SERIES,
        "from": ddmmyyyy(d1),
        "to": ddmmyyyy(d2),
    }
    # NSE blocks “non-browsery” requests; set UA + Referer and keep cookies.
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:123.0) Gecko/20100101 Firefox/123.0",
        "Referer": f"{BASE}/get-quotes/equity?symbol={quote(symbol, safe='')}",
        "Accept": "application/json,text/plain,*/*",
    }
    r = sess.get(HIST_URL, params=params, headers=headers, timeout=30)
    r.raise_for_status()
    data = r.json()
    # The payload usually has a 'data' list with day rows.
    return data.get("data", []) if isinstance(data, dict) else data

def ensure_session() -> requests.Session:
    sess = requests.Session()
    # Hit homepage once to obtain cookies/route — improves odds of 200 vs 403.
    sess.headers.update({"User-Agent": "Mozilla/5.0"})
    sess.get(BASE, timeout=30)
    return sess

# -------- Main --------
def main():
    today = dt.date.today()
    start = today.replace(year=today.year - YEARS)
    sess = ensure_session()

    all_rows = []
    d1 = start
    while d1 <= today:
        d2 = min(d1 + dt.timedelta(days=CHUNK_DAYS - 1), today)
        try:
            rows = fetch_chunk(sess, SYMBOL, d1, d2)
            # Append in chronological order; API may return newest-first
            for row in rows:
                all_rows.append(row)
            # polite pause
            time.sleep(0.6)
        except requests.HTTPError as e:
            print(f"[WARN] {d1}..{d2}: HTTP error: {e}")
        except Exception as e:
            print(f"[WARN] {d1}..{d2}: {e}")
        d1 = d2 + dt.timedelta(days=1)

    if not all_rows:
        print("No data returned. Try reducing CHUNK_DAYS or check symbol/series.")
        return

    # Normalize columns commonly present in this endpoint
    # Typical keys: 'CH_TIMESTAMP','CH_OPENING_PRICE','CH_TRADE_HIGH_PRICE','CH_TRADE_LOW_PRICE',
    # 'CH_CLOSING_PRICE','CH_PREVIOUS_CLS_PRICE','CH_TOT_TRADED_QTY','CH_TOT_TRADED_VAL','CH_52WEEK_HIGH_PRICE','CH_52WEEK_LOW_PRICE'
    # (Exact fields can vary; we write what we see across rows.)
    # Build a unified header
    header = set()
    for r in all_rows:
        header.update(r.keys())
    header = sorted(header)

    # Sort by date if timestamp column exists
    def parse_date(x):
        v = x.get("CH_TIMESTAMP") or x.get("timestamp") or ""
        try:
            # CH_TIMESTAMP usually DD-MMM-YYYY (e.g., 08-Oct-2025); fall back if needed
            return dt.datetime.strptime(v, "%d-%b-%Y")
        except Exception:
            try:
                return dt.datetime.strptime(v, "%d-%m-%Y")
            except Exception:
                return dt.datetime.min

    all_rows.sort(key=parse_date)

    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=header)
        w.writeheader()
        w.writerows(all_rows)

    print(f"Wrote {len(all_rows)} rows to {OUT_CSV}")

if __name__ == "__main__":
    main()
