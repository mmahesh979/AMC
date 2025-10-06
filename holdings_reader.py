"""Holdings Excel reader.

Reads the latest holdings Excel file from a reports directory and returns
the present holdings as a pandas DataFrame. It expects the data to be in
the sheet named 'Equity' and will locate the header row by searching for
columns like 'Symbol' and 'ISIN/ISISN'. All columns and rows starting
from that header row and starting column are returned.

Also includes a helper to print the DataFrame to the terminal.

Dependencies (minimal):
- pandas
- openpyxl (Excel engine used by pandas for .xlsx)

Usage examples:
- python holdings_reader.py                # reads from ./Reports latest .xlsx and prints
- python holdings_reader.py --dir Reports  # explicit directory
- python holdings_reader.py --file Reports/holdings-XG9018.xlsx
"""

from __future__ import annotations

import argparse
from pathlib import Path
import os


def _load_dotenv(path: Path | str = ".env") -> None:
    """Lightweight .env loader to avoid extra dependencies.

    Parses KEY=VALUE lines, ignoring comments and blank lines, and inserts
    them into os.environ if the key is not already set. Quotes around values
    are stripped.
    """
    try:
        env_path = Path(path)
        if not env_path.exists():
            return
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val
    except Exception:
        # Silently ignore .env parsing issues to avoid blocking execution
        return
from typing import Optional, Tuple

import pandas as pd


def find_latest_excel(directory: Path) -> Path:
    """Return the most recently modified .xlsx file in the directory.

    Raises FileNotFoundError if no matching file is found.
    """
    if not directory.exists() or not directory.is_dir():
        raise FileNotFoundError(f"Directory not found: {directory}")

    candidates = sorted(
        directory.glob("*.xlsx"), key=lambda p: p.stat().st_mtime, reverse=True
    )
    if not candidates:
        raise FileNotFoundError(f"No .xlsx files found in {directory}")
    return candidates[0]


def _clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Basic cleaning: drop fully empty rows/cols and trim column names."""
    # Drop fully empty rows/cols
    df = df.dropna(how="all")
    df = df.loc[:, df.columns.notna()]
    # Drop entirely empty columns
    df = df.dropna(axis=1, how="all")

    # Normalize column names: strip whitespace; keep original casing
    df.columns = [str(c).strip() for c in df.columns]

    # Remove common placeholder columns like 'Unnamed: X' if they are entirely empty
    cols = pd.Index([str(c) for c in df.columns])
    unnamed_mask = cols.str.contains(r"^Unnamed", case=False, regex=True)
    drop_cols = []
    for col, is_unnamed in zip(df.columns, unnamed_mask):
        if is_unnamed and df[col].dropna().empty:
            drop_cols.append(col)
    if drop_cols:
        df = df.drop(columns=drop_cols)

    return df


def load_holdings_df(
    reports_dir: Optional[Path | str] = None,
    file_path: Optional[Path | str] = None,
    sheet_name: Optional[str] = "Equity",
) -> pd.DataFrame:
    """Load holdings from an Excel file into a pandas DataFrame.

    - If `file_path` is provided, uses that file.
    - Otherwise finds the latest `.xlsx` in `reports_dir`.
    - If `sheet_name` is provided, uses that sheet; else applies heuristics.
    - Performs light cleaning to remove empty rows/columns.

    Returns a DataFrame with the present holdings.
    """
    # Load .env for REPORTS_DIR if present and dir not supplied
    _load_dotenv()

    # Resolve reports directory with precedence: explicit arg > env > default 'Reports'
    effective_reports_dir: Path
    if reports_dir is None:
        env_dir = os.getenv("REPORTS_DIR")
        effective_reports_dir = Path(env_dir) if env_dir else Path("Reports")
    else:
        effective_reports_dir = Path(reports_dir)

    if file_path is None:
        file = find_latest_excel(effective_reports_dir)
    else:
        file = Path(file_path)
        if not file.exists():
            raise FileNotFoundError(f"File not found: {file}")

    # Always read the specified sheet (default: 'Equity') without assuming header
    chosen_name = sheet_name if sheet_name is not None else "Equity"

    try:
        raw = pd.read_excel(file, sheet_name=chosen_name, header=None, engine="openpyxl")
    except ValueError:
        raw = pd.read_excel(file, sheet_name=chosen_name, header=None)

    if raw is None or raw.empty:
        raise ValueError(f"Sheet '{chosen_name}' appears empty in file: {file}")

    header_row, c_start, c_end = _find_table_header_bounds(raw)

    # Slice rows/columns from the detected header and onward
    header_vals = [
        _normalize_cell(x) or f"col_{j-c_start}"
        for j, x in enumerate(raw.iloc[header_row, c_start:c_end + 1], start=c_start)
    ]

    df = raw.iloc[header_row + 1 :, c_start : c_end + 1].copy()
    df.columns = header_vals
    df = _clean_dataframe(df)
    return df


def _normalize_cell(val: object) -> Optional[str]:
    if pd.isna(val):    # type: ignore
        return None
    s = str(val).strip()
    return s if s != "" else None


def _find_table_header_bounds(raw: pd.DataFrame) -> Tuple[int, int, int]:
    """Find header row index and start/end column indices for the holdings table.

    Searches for a row containing at least the headers 'Symbol' and 'ISIN',
    case-insensitive. Returns (header_row_index, start_col_index, end_col_index), where the
    start column is the position of 'Symbol' and the end column is the last non-empty header
    cell in that row.
    """
    max_scan = min(len(raw), 200)
    required_any = {"isin"}

    header_row = None
    header_vals_cache = None
    for i in range(max_scan):
        row_vals = [ _normalize_cell(v) for v in raw.iloc[i].tolist() ]
        lowered = [ (v.lower() if v is not None else None) for v in row_vals ]
        has_symbol = any((v is not None and "symbol" in v) for v in lowered)
        has_isin = any((v is not None and any(key in v for key in required_any)) for v in lowered)
        if has_symbol and has_isin:
            header_row = i
            header_vals_cache = row_vals
            break
    # print(header_vals_cache)
    if header_row is None:
        raise ValueError(
            "Sheet exists, but could not extract holdings. Please check sheet format"
        )

    # Determine start at the first 'Symbol'
    c_start = next(
        idx
        for idx, v in enumerate((v.lower() if v else None) for v in header_vals_cache) # type: ignore
        if v is not None and "symbol" in v
    )

    # Determine end as the last non-empty cell in the row
    last_idx = len(header_vals_cache) - 1 # type: ignore
    c_end = c_start
    for j in range(last_idx, c_start - 1, -1):
        if _normalize_cell(header_vals_cache[j]) is not None: # type: ignore
            c_end = j
            break

    if c_end < c_start:
        c_end = c_start

    return header_row, c_start, c_end


def print_dataframe(df: pd.DataFrame, max_rows: int = 100) -> None:
    """Print the DataFrame to the terminal in a readable format."""
    with pd.option_context(
        "display.max_rows", max_rows,
        "display.max_columns", None,
        "display.width", 0,
        "display.max_colwidth", None,
    ):
        print(df.to_string(index=False))


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Load and print holdings from Excel")
    p.add_argument(
        "--dir",
        dest="directory",
        default=None,
        help="Reports directory path (overrides REPORTS_DIR from .env)",
    )
    p.add_argument("--file", dest="file", default=None, help="Explicit Excel file path")
    p.add_argument("--sheet", dest="sheet", default="Equity", help="Sheet name to read (default: Equity)")
    p.add_argument("--head", dest="head", type=int, default=None, help="Only show first N rows when printing")
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    df = load_holdings_df(args.directory, args.file, args.sheet)
    if args.head is not None and args.head >= 0:
        print_dataframe(df.head(args.head))
    else:
        print_dataframe(df)


if __name__ == "__main__":
    main()
