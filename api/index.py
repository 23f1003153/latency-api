import json
import math
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List

app = FastAPI()

# Allow any website to call this API with POST (this is the CORS part)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

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
