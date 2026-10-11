import json
import math
from pathlib import Path
from typing import List

from fastapi import FastAPI, Request, Response
from pydantic import BaseModel

app = FastAPI()

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "*",
}


@app.middleware("http")
async def add_cors(request: Request, call_next):
    # Answer browser "preflight" checks directly
    if request.method == "OPTIONS":
        return Response(status_code=204, headers=CORS_HEADERS)
    response = await call_next(request)
    for k, v in CORS_HEADERS.items():
        response.headers[k] = v
    return response


# Load the telemetry file that sits next to this script
DATA_FILE = Path(__file__).parent / "q-vercel-latency.json"
with open(DATA_FILE) as f:
    DATA = json.load(f)

# Some bundles are a plain list, others wrap it in a key. Handle both.
if isinstance(DATA, dict):
    for v in DATA.values():
        if isinstance(v, list):
            DATA = v
            break


class Query(BaseModel):
    regions: List[str]
    threshold_ms: float


def percentile(values, p):
    """Linear-interpolation percentile (same as numpy's default)."""
    s = sorted(values)
    k = (len(s) - 1) * p / 100
    lo, hi = math.floor(k), math.ceil(k)
    if lo == hi:
        return s[int(k)]
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


@app.post("/")
def analyze(q: Query):
    result = {}
    for region in q.regions:
        rows = [r for r in DATA if r["region"] == region]
        if not rows:
            continue
        lat = [r["latency_ms"] for r in rows]
        up = [r["uptime_pct"] for r in rows]
        result[region] = {
            "avg_latency": sum(lat) / len(lat),
            "p95_latency": percentile(lat, 95),
            "avg_uptime": sum(up) / len(up),
            "breaches": sum(1 for x in lat if x > q.threshold_ms),
        }
    return result
