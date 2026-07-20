

   """
process_data.py
---------------
Downloads IDEAL_TRANSPORT_CONNECTION.csv and FACILITY_MAPPER.csv from
Google Drive, joins facility names, filters active routes, and writes
a compact data.json consumed by index.html.

Run locally:  python process_data.py
Run in CI:    called by .github/workflows/update-data.yml
"""

import json
import os
import sys
from datetime import datetime, timezone

# ── Install deps if missing ────────────────────────────────────────────────
try:
    import gdown
    import pandas as pd
except ImportError:
    print("Installing gdown and pandas…")
    os.system(f'"{sys.executable}" -m pip install gdown pandas --quiet')
    import gdown
    import pandas as pd

# ── Drive file IDs ─────────────────────────────────────────────────────────
# NOTE: both files must be shared as "Anyone with the link can view"
TRANSPORT_FILE_ID = "1tHUIyOtRx26-ifvLceE2FznnI7WkahF9"   # IDEAL_TRANSPORT_CONNECTION.csv
FACILITY_FILE_ID  = "1MkqZNksbRVvmSirJh3yQRgDZvTHu9-_k"   # FACILITY_MAPPER.csv

TRANSPORT_LOCAL = "transport.csv"
FACILITY_LOCAL  = "facility.csv"


def download(file_id: str, dest: str) -> None:
    url = f"https://drive.google.com/uc?id={file_id}"
    gdown.download(url, dest, quiet=False)
    if not os.path.exists(dest) or os.path.getsize(dest) == 0:
        raise RuntimeError(f"Download failed or empty: {dest}")


def main() -> None:
    # ── 1. Download ────────────────────────────────────────────────────────
    print("⬇  Downloading IDEAL_TRANSPORT_CONNECTION.csv…")
    download(TRANSPORT_FILE_ID, TRANSPORT_LOCAL)

    print("⬇  Downloading FACILITY_MAPPER.csv…")
    download(FACILITY_FILE_ID, FACILITY_LOCAL)

    # ── 2. Load transport – only columns we need ───────────────────────────
    print("⚙  Processing transport data…")
    transport_cols = [
        "active",
        "source_facility_id",
        "destination_facility_id",
        "service",
        "source_cutoff",
        "transit_time",
    ]
    transport = pd.read_csv(
        TRANSPORT_LOCAL,
        usecols=transport_cols,
        low_memory=False,
        dtype=str,
    )
    print(f"   Total rows loaded: {len(transport):,}")

    # ── 3. Filter active == true ───────────────────────────────────────────
    transport["active"] = transport["active"].str.strip().str.lower()
    transport = transport[transport["active"] == "true"].copy()
    print(f"   Active rows: {len(transport):,}")

    # ── 4. Load facility mapper ────────────────────────────────────────────
    print("⚙  Loading FACILITY_MAPPER.csv…")
    facility = pd.read_csv(
        FACILITY_LOCAL,
        usecols=["facility_id", "facility_name"],
        dtype=str,
    )
    facility["facility_id"]   = facility["facility_id"].str.strip()
    facility["facility_name"] = facility["facility_name"].str.strip()
    fmap = dict(zip(facility["facility_id"], facility["facility_name"]))
    print(f"   Facility entries: {len(fmap):,}")

    # ── 5. Join names ──────────────────────────────────────────────────────
    transport["source_facility_id"]      = transport["source_facility_id"].str.strip()
    transport["destination_facility_id"] = transport["destination_facility_id"].str.strip()

    transport["source_name"]      = transport["source_facility_id"].map(fmap)
    transport["destination_name"] = transport["destination_facility_id"].map(fmap)

    # Drop rows where either facility couldn't be resolved
    before = len(transport)
    transport.dropna(subset=["source_name", "destination_name"], inplace=True)
    dropped = before - len(transport)
    if dropped:
        print(f"   ⚠  {dropped:,} rows dropped (facility ID not in mapper)")

    # ── 6. Select output columns & deduplicate ─────────────────────────────
    result = transport[
        ["source_name", "destination_name", "service", "source_cutoff", "transit_time"]
    ].copy()
    result.drop_duplicates(inplace=True)
    print(f"   Unique active routes: {len(result):,}")

    # ── 7. Write data.json ─────────────────────────────────────────────────
    payload = {
        "lastUpdated": datetime.now(timezone.utc).isoformat(),
        "routes": result.to_dict(orient="records"),
    }
    with open("data.json", "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, separators=(",", ":"))

    size_kb = os.path.getsize("data.json") / 1024
    print(f"✅  data.json written — {len(payload['routes']):,} routes, {size_kb:.1f} KB")

    # ── 8. Clean up temp files ─────────────────────────────────────────────
    for f in (TRANSPORT_LOCAL, FACILITY_LOCAL):
        try:
            os.remove(f)
        except OSError:
            pass


if __name__ == "__main__":
    main()
