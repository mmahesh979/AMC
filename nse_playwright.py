import argparse
from typing import List

import pandas as pd
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError, sync_playwright

DATE_FORMAT = "%Y-%m-%d"
DISPLAY_FORMAT = "%d-%m-%Y"


def open_historical_tab(
    symbol: str,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
    headless: bool = True,
) -> None:
    url = f"https://www.nseindia.com/get-quotes/equity?symbol={symbol}"
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        )
        try:
            tab = page.get_by_role("tab", name="Historical Data")
            table = page.locator("#equityHistoricalTable")

            for attempt in range(3):
                if attempt:
                    page.reload(wait_until="domcontentloaded")
                else:
                    page.goto(url, wait_until="domcontentloaded")
                tab.click()
                try:
                    table.wait_for(state="visible", timeout=2000)
                    break
                except PlaywrightTimeoutError:
                    page.wait_for_timeout(2000)
            else:
                raise RuntimeError("Response NA")

            all_frames: List[pd.DataFrame] = []
            corporate_events: List[List[str]] = []
            current_end = end_date

            while current_end >= start_date:
                window_start = current_end - pd.DateOffset(years=1)
                if window_start < start_date:
                    window_start = start_date

                page.evaluate(
                    """({ start, end }) => {
                        if (window.$) {
                            window.$('#startDate1').datepicker().value(start);
                            window.$('#endDate1').datepicker().value(end);
                        }
                    }""",
                    {
                        "start": window_start.strftime(DISPLAY_FORMAT),
                        "end": current_end.strftime(DISPLAY_FORMAT),
                    },
                )
                page.get_by_role("button", name="Filter").click()
                try:
                    page.wait_for_load_state("networkidle", timeout=5000)
                except PlaywrightTimeoutError:
                    pass
                page.wait_for_timeout(1000)
                tab.click()
                try:
                    table.wait_for(state="visible", timeout=2000)
                except PlaywrightTimeoutError:
                    break

                headers = [h.strip() for h in table.locator("thead tr").first.locator("th").all_inner_texts()]
                rows_locator = table.locator("tbody tr")
                rows = []
                events_chunk: List[List[str]] = []
                for i in range(rows_locator.count()):
                    row_locator = rows_locator.nth(i)
                    cell_locators = row_locator.locator("td")
                    row = []
                    for j in range(cell_locators.count()):
                        cell = cell_locators.nth(j)
                        text = cell.inner_text().strip()
                        if j == 0:
                            anchor_locator = cell.locator("a")
                            if anchor_locator.count():
                                anchor = anchor_locator.first
                                href = anchor.get_attribute("href") or ""
                                title = anchor.get_attribute("title") or ""
                                events_chunk.append([text, title, href])
                        row.append(text)
                    rows.append(row)

                if not rows:
                    break

                df_chunk = pd.DataFrame(rows, columns=headers)
                if "DATE" in df_chunk.columns:
                    df_chunk["DATE"] = pd.to_datetime(df_chunk["DATE"], errors="coerce")
                    valid_dates = df_chunk["DATE"].dropna()
                else:
                    valid_dates = pd.Series([], dtype="datetime64[ns]")

                if "DATE" in df_chunk.columns:
                    mask = (df_chunk["DATE"] >= start_date) & (df_chunk["DATE"] <= end_date)
                    df_filtered = df_chunk.loc[mask].copy()
                else:
                    df_filtered = df_chunk

                if not df_filtered.empty:
                    all_frames.append(df_filtered)
                corporate_events.extend(events_chunk)

                if valid_dates.empty:
                    break

                actual_start = valid_dates.min()
                actual_end = valid_dates.max()
                print(f"Fetched chunk: {len(df_filtered)} rows, range {actual_start} -> {actual_end}")

                if actual_start <= start_date:
                    break

                current_end = (actual_start - pd.Timedelta(days=1)).normalize()

            if all_frames:
                final_df = pd.concat(all_frames, ignore_index=True)
                final_df.drop_duplicates(inplace=True)
                final_df.sort_values(by="DATE", ascending=False, inplace=True, na_position="last")
                print(f"Accumulated table shape: {final_df.shape}")
                print(final_df.head(10))
                start_span = final_df["DATE"].min()
                end_span = final_df["DATE"].max()
                if pd.notna(start_span) and pd.notna(end_span):
                    print(f"date range: {start_span} -> {end_span}")
            else:
                print("No data collected for requested range.")

            print(f"corporate events: {corporate_events}")
        finally:
            browser.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch NSE historical equity data over a date range.")
    parser.add_argument("symbol")
    parser.add_argument("--start-date", required=True, help=f"Start date ({DATE_FORMAT})")
    parser.add_argument("--end-date", help=f"End date ({DATE_FORMAT}), defaults to today")
    parser.add_argument("--no-headless", action="store_true")
    args = parser.parse_args()

    overall_start = pd.to_datetime(args.start_date).normalize()
    overall_end = (
        pd.to_datetime(args.end_date).normalize()
        if args.end_date
        else pd.Timestamp.today().normalize()
    )
    if overall_end < overall_start:
        raise ValueError("End date must be on or after start date.")

    open_historical_tab(args.symbol, overall_start, overall_end, headless=not args.no_headless)
