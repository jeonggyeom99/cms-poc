import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
MOCK_DATA_PATH = BASE_DIR / "data" / "dashboard.json"

app = FastAPI(
    title="CMS AI PoC",
    description="V032 설비 상세 Dashboard Mock API",
    version="0.1.0",
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def dashboard() -> str:
    return (STATIC_DIR / "index.html").read_text(encoding="utf-8")


@app.get("/api/dashboard")
async def dashboard_data() -> dict[str, Any]:
    with MOCK_DATA_PATH.open(encoding="utf-8") as mock_file:
        return json.load(mock_file)
