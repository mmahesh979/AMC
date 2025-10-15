#!/usr/bin/env python3
"""
Simple Playwright script to open NSE equity quote page for a symbol
and click the "Historical Data" tab.

Usage:
  python nse_playwright.py --symbol HCLTECH            # headed (default)
  python nse_playwright.py --symbol TCS --headless     # headless

Notes:
  - Requires: pip install playwright
  - First time: python -m playwright install
  - On some systems, you may need OS libs (see pw_deps.txt).
"""

from typing import Optional
import time
from datetime import date
import pandas as pd
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError


BASE = "https://www.nseindia.com"


def main(symbol: str, headless_mode: bool = False, page_timeout_ms: int = 60_000) -> None:
    """Open NSE quote page for the given symbol and click "Historical Data".

    Args:
        symbol: NSE equity symbol, e.g., "HCLTECH", "TCS", "RELIANCE".
        headless: If True, runs without a visible window. Defaults to False.
        page_timeout_ms: Navigation and selector timeout in ms. Defaults to 60000.
    """

    url = f"{BASE}/get-quotes/equity?symbol={symbol.upper()}"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless_mode)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1400, "height": 900},
            locale="en-US",
            extra_http_headers={
                "Accept-Language": "en-US,en;q=0.9",
            },
        )

        page = context.new_page()
        page.set_default_timeout(page_timeout_ms)
        
        #Navigate to the scrip
        print(f"Navigating to: {url}")
        page.goto(url, wait_until="domcontentloaded")
        time.sleep(3)
        print("Opening 'Historical Data' tab...")
        try:
            page.get_by_role("tab", name="Historical Data").click()
            time.sleep(.5)

            # Set custom date range via page JS (readonly-safe), then click Filter.
            # Example: start = 01-04-2018, end = today (DD-MM-YYYY)
            start_str = "01-04-2018"
            end_str = date.today().strftime("%d-%m-%Y")

            page.evaluate(
                """
                ({s, e}) => {
                  const $ = window.$ || window.jQuery;

                  const setViaPicker = (id, val) => {
                    try {
                      if ($ && $.fn && $.fn.datepicker && typeof $(('#'+id)).datepicker === 'function') {
                        $(('#'+id)).datepicker('setDate', val);
                        return true;
                      }
                    } catch (_){}
                    try {
                      const inst = $ ? ($(('#'+id)).data('datepicker') || $(('#'+id)).data('gj-datepicker')) : null;
                      if (inst && typeof inst.value === 'function') { inst.value(val); return true; }
                      if ($ && typeof $(('#'+id)).datepicker === 'function') {
                        const maybe = $(('#'+id)).datepicker();
                        if (maybe && typeof maybe.value === 'function') { maybe.value(val); return true; }
                      }
                    } catch (_){}
                    return false;
                  };

                  const setDirect = (id, val) => {
                    const el = document.getElementById(id);
                    if (!el) return;
                    el.value = val;
                    el.dispatchEvent(new Event('input', { bubbles: true }));
                    el.dispatchEvent(new Event('change', { bubbles: true }));
                  };

                  if (!setViaPicker('startDate1', s)) setDirect('startDate1', s);
                  if (!setViaPicker('endDate1', e)) setDirect('endDate1', e);

                  // Clear any active preset chip so it won't override custom range
                  try { document.querySelectorAll('.dayslisting .active').forEach(n => n.classList.remove('active')); } catch (_){}
                }
                """,
                {"s": start_str, "e": end_str},
            )
            time.sleep(5)

            page.get_by_role("button", name="Filter").click()
            page.wait_for_load_state("networkidle")
        except:
            pass
            # Scope table and use relative XPath (scoped with .//)
        #     table = page.locator("id=equityHistoricalTable").first

        #     # Extract headers row-wise via XPath scoped to table
        #     headers_nodes = table.locator("xpath=.//thead//th").all()
        #     headers = [h.inner_text().replace("\n", " ").strip() for h in headers_nodes]
        #     if not headers:
        #         raise RuntimeError("No headers found in equityHistoricalTable")

        #     # Validate first column is DATE (ignore case)
        #     if headers[0].strip().lower() != "date":
        #         raise RuntimeError("date_column_missing")

        #     # Collect rows for performant DataFrame creation and diagnostics
        #     rows_buffer = []  # list[list[str|NA]]
        #     data_errors = []  # {scrip, date, missing_values}
        #     corp_events = []  # {scrip, date, title, href}

        #     # Iterate rows and extract cells row-wise
        #     row_nodes = table.locator("xpath=.//tbody//tr")
        #     row_count = row_nodes.count()
        #     for i in range(row_count):
        #         row = row_nodes.nth(i)
        #         cell_nodes = row.locator("xpath=.//td").all()

        #         # Check for corporate event link in first cell
        #         try:
        #             first_td = row.locator("xpath=.//td[1]")
        #             anchor = first_td.locator("xpath=.//a")
        #             if anchor.count() > 0:
        #                 href = anchor.first.get_attribute("href") or ""
        #                 title = anchor.first.get_attribute("title") or ""
        #                 date_text = first_td.inner_text().replace("\n", " ").strip()
        #                 corp_events.append({
        #                     "scrip": symbol.upper(),
        #                     "date": date_text,
        #                     "title": title,
        #                     "href": BASE+href,
        #                 })
        #         except Exception:
        #             raise RuntimeError("Error extracting special events")

        #         # Extract cell texts with formatting
        #         cells = [c.inner_text().replace("\n", " ").strip() for c in cell_nodes]

        #         # Ensure row length matches headers by padding NA and record data error
        #         if len(cells) != len(headers):
        #             if len(cells) < len(headers):
        #                 missing = len(headers) - len(cells)
        #                 data_errors.append({
        #                     "scrip": symbol.upper(),
        #                     "date": cells[0] if cells else "",
        #                     "missing_values": missing,
        #                 })
        #                 cells = cells + [pd.NA] * missing
        #             else:
        #                 cells = cells[: len(headers)]

        #         # Buffer the row for later DataFrame construction
        #         rows_buffer.append(cells)

        #     # Build DataFrame once for performance
        #     df = pd.DataFrame(rows_buffer, columns=headers)
        #     # Convert first column (Date) to datetime, drop invalid, set index
        #     df.rename(columns={df.columns[0]: 'Date'}, inplace=True)
        #     df['Date'] = pd.to_datetime(df['Date'], dayfirst=True, errors='coerce')
        #     before = len(df)
        #     df = df.dropna(subset=['Date'])
        #     if len(df) != before:
        #         print(f"[INFO] Dropped {before - len(df)} rows with invalid Date")
        #     df = df.set_index('Date').sort_index()

        #     # Output
        #     print("===== equityHistoricalTable (head) =====")
        #     print(df.head())
        #     print(df.shape)
        #     print("===== end head =====")
        #     if data_errors:
        #         print(f"[DATA ERRORS] {len(data_errors)} row(s) had missing values\n{data_errors}")
        #     if corp_events:
        #         print(f"[CORP EVENTS] {len(corp_events)} event link(s) captured\n{corp_events}")
        # except PWTimeoutError:
        #     print("Timeout Error")
        # except Exception as e:
        #     print(f"exception: {e}")
        
        page.wait_for_timeout(1_000)

        context.close()
        browser.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Open NSE page and click Historical Data tab")
    parser.add_argument("--symbol", "-s", default="HCLTECH", help="NSE symbol, e.g., HCLTECH")
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run without visible browser window (default: False)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=60_000,
        help="Navigation/selector timeout in ms (default: 60000)",
    )
    args = parser.parse_args()

    main(symbol=args.symbol, headless_mode=args.headless, page_timeout_ms=args.timeout)
    
