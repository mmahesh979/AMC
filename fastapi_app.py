from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

import holdings_reader
import frontend_parser


app = FastAPI(title="Holdings Viewer")
templates = Jinja2Templates(directory="templates")


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse(url="/holdings", status_code=302)


@app.get("/api/holdings")
def api_holdings() -> Dict[str, Any]:
    try:
        df = holdings_reader.load_holdings_df()
        df = frontend_parser.compute_frontend_table(df)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    data: List[Dict[str, Any]] = df.to_dict(orient="records")  # pyright: ignore[reportAssignmentType, reportReturnType]
    return JSONResponse(content={"columns": list(df.columns), "rows": data}) # pyright: ignore[reportReturnType]


@app.get("/holdings", response_class=HTMLResponse)
def html_holdings(request: Request):
    source = "N/A"
    try:
        df = holdings_reader.load_holdings_df()
        df = frontend_parser.compute_frontend_table(df)
        # Best-effort: show the specific file used
        try:
            reports_dir = Path(holdings_reader.os.getenv("REPORTS_DIR") or "Reports")
            latest = holdings_reader.find_latest_excel(reports_dir)
            source = str(latest)
        except Exception:  # noqa: BLE001
            pass

        return templates.TemplateResponse(
            "holdings.html",
            {
                "request": request,
                "columns": list(df.columns),
                "rows": df.to_dict(orient="records"),
                "source": source,
                "error": None,
            },
        )
    except Exception as exc:  # noqa: BLE001
        # Render a friendly error page
        return templates.TemplateResponse(
            "holdings.html",
            {
                "request": request,
                "columns": [],
                "rows": [],
                "source": source,
                "error": str(exc),
            },
            status_code=404,
        )
