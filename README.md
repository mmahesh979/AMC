# Holdings Reader

Small utility to read a holdings Excel report and output the current holdings as a pandas DataFrame or print it to the terminal.

The tool expects the data to be on the `Equity` sheet and auto-detects the header row by finding columns like `Symbol` and `ISIN/ISISN`. It then extracts all columns from `Symbol` through the last non-empty header cell, and all subsequent rows.

## Requirements
- Python 3.10+
- Dependencies: see `requirements.txt`

Install locally:

```
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
```

## Run the web app

This starts a minimal FastAPI server that exposes an HTML table and a JSON API for holdings. It reuses the Excel reader from this repo and respects `.env` (`REPORTS_DIR`).

```
uvicorn fastapi_app:app --reload
```

- HTML table: http://127.0.0.1:8000/holdings
- JSON API:  http://127.0.0.1:8000/api/holdings

The root `/` redirects to `/holdings`.

## Configuration (.env)
You can specify the default reports directory via `.env`:

```
# .env
REPORTS_DIR=Reports
```

The script looks for the latest `*.xlsx` in that directory when `--file` is not provided. The `--dir` CLI flag overrides `.env`.

## Usage

CLI examples:

```
# Use REPORTS_DIR from .env (or fallback to ./Reports)
python holdings_reader.py

# Explicit directory (overrides .env)
python holdings_reader.py --dir ./Reports

# Specific file
python holdings_reader.py --file Reports/holdings-XYZ.xlsx

# Limit printed rows
python holdings_reader.py --head 20
```

Options:
- `--file` Path to a specific Excel file.
- `--dir`  Directory to search for the latest `.xlsx` (overrides `.env`).
- `--sheet` Sheet name to read (default: `Equity`).
- `--head` Print only the first N rows.

## Programmatic use

```
from holdings_reader import load_holdings_df, print_dataframe

df = load_holdings_df()            # respects REPORTS_DIR in .env
print_dataframe(df)

# Or pass a specific file
df = load_holdings_df(file_path="Reports/holdings-XYZ.xlsx")
```

## How it works
- Reads the `Equity` sheet with no header.
- Scans rows to find the header row that contains `Symbol` and `ISIN`/`ISISN` (case-insensitive, substring match).
- Uses the position of `Symbol` as the start column and the last non-empty header cell as the end column.
- Extracts rows below that header and returns a cleaned DataFrame (drops fully empty rows/columns, removes empty unnamed columns).

## Troubleshooting
- `Could not locate header row ...`: Ensure the sheet is named `Equity` and contains headers with `Symbol` and `ISIN`/`ISISN`.
- `No .xlsx files found ...`: Confirm `REPORTS_DIR` or `--dir` points to the correct folder.
- Engine errors: Ensure `openpyxl` is installed and versions are compatible (`pip install -r requirements.txt`).

## Git hygiene
The repository includes a `.gitignore` that excludes `Reports/` so uploaded reports aren’t committed. Adjust as needed.
