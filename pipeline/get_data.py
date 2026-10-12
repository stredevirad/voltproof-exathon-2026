"""Fetch (optionally) and verify the ESMI raw files from Harvard Dataverse.

Usage (normally via scripts\\get-data.ps1):
    python -m pipeline.get_data --set first            # verify the first-sample files in data/raw
    python -m pipeline.get_data --set up --download     # download missing UP-period files, then verify

What it does
- Reads the dataset's file list and published MD5 checksums from the Dataverse native API
  (no download gate applies to metadata).
- Looks for each wanted file in data/raw, accepting the original-format name (e.g. "... .csv")
  or the ingested tab-export name ("... .tab").
- Computes size, MD5 and SHA-256 and compares the MD5 with the published value.
- With --download: for each missing file, submits the runner's own Guestbook response (from the
  DATAVERSE_GB_* environment variables, normally loaded from a gitignored .env) and downloads the
  original-format file through the signed URL Dataverse returns.
- Writes data/manifest.json (no personal details) and exits non-zero if any wanted file is missing or
  fails verification.

Personal details are only ever sent to dataverse.harvard.edu in the Guestbook request body. They are
never printed, logged or written to disk by this module.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

SERVER = "https://dataverse.harvard.edu"
PERSISTENT_ID = "doi:10.7910/DVN/CLLZZM"
GUESTBOOK_ID = 251
USER_AGENT = "VoltProof-get-data/0.1 (+https://github.com/stredevirad/voltproof-exathon-2026)"

REPO_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = REPO_ROOT / "data" / "raw"
MANIFEST = REPO_ROOT / "data" / "manifest.json"
METADATA_CACHE = REPO_ROOT / "data" / "dataverse_dataset.json"

# Dataverse file ids grouped into download sets. Ids are stable for dataset version 2.0.
LOCATION_FILE = 3360848
ABOUT_PDF = 3360847
FIRST_SAMPLE = 3362279  # 2018 June-Aug, the smallest file inside the UP study period 2016-2019
UP_PERIOD = [3360857, 3360856, 3360888, 3362275, 3362278, 3362468, 3362279, 3362276, 4411478, 4411477]
SETS = {
    "meta": [LOCATION_FILE, ABOUT_PDF],
    "first": [LOCATION_FILE, ABOUT_PDF, FIRST_SAMPLE],
    "up": [LOCATION_FILE, ABOUT_PDF, *UP_PERIOD],
}
SETS["all"] = None  # every file in the dataset

GUESTBOOK_ENV = {
    "name": "DATAVERSE_GB_NAME",
    "email": "DATAVERSE_GB_EMAIL",
    "institution": "DATAVERSE_GB_INSTITUTION",
    "position": "DATAVERSE_GB_POSITION",
}
INTENDED_USE_ENV = "DATAVERSE_GB_INTENDED_USE"


def _request(url: str, data: bytes | None = None, headers: dict | None = None) -> urllib.request.Request:
    h = {"User-Agent": USER_AGENT}
    if headers:
        h.update(headers)
    return urllib.request.Request(url, data=data, headers=h, method="POST" if data is not None else "GET")


def fetch_dataset_metadata(refresh: bool = False) -> dict:
    if METADATA_CACHE.exists() and not refresh:
        return json.loads(METADATA_CACHE.read_text(encoding="utf-8"))
    url = f"{SERVER}/api/datasets/:persistentId/?persistentId={urllib.parse.quote(PERSISTENT_ID)}"
    with urllib.request.urlopen(_request(url), timeout=60) as resp:
        meta = json.loads(resp.read().decode("utf-8"))
    if meta.get("status") != "OK":
        raise RuntimeError(f"Dataverse metadata request failed: {meta.get('message')}")
    METADATA_CACHE.parent.mkdir(parents=True, exist_ok=True)
    METADATA_CACHE.write_text(json.dumps(meta, indent=1), encoding="utf-8")
    return meta


def file_catalogue(meta: dict) -> dict[int, dict]:
    version = meta["data"]["latestVersion"]
    cat = {}
    for f in version["files"]:
        df = f["dataFile"]
        cat[df["id"]] = {
            "id": df["id"],
            "stored_name": df["filename"],
            "stored_size": df.get("filesize"),
            "original_name": df.get("originalFileName") or df["filename"],
            "original_size": df.get("originalFileSize") or df.get("filesize"),
            "md5": (df.get("checksum") or {}).get("value") or df.get("md5"),
            "is_tabular": bool(df.get("originalFileName")),
        }
    return cat


def hash_file(path: Path) -> tuple[str, str, int]:
    md5, sha = hashlib.md5(), hashlib.sha256()
    size = 0
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(4 * 1024 * 1024), b""):
            md5.update(chunk)
            sha.update(chunk)
            size += len(chunk)
    return md5.hexdigest(), sha.hexdigest(), size


def find_local(entry: dict) -> Path | None:
    for name in (entry["original_name"], entry["stored_name"]):
        p = RAW_DIR / name
        if p.exists():
            return p
    return None


def ddi_row_count(file_id: int) -> int | None:
    """Observation count Dataverse publishes for an ingested tabular file (DDI caseQnty; no download gate)."""
    cache = REPO_ROOT / "data" / f"dataverse_ddi_{file_id}.xml"
    if not cache.exists():
        url = f"{SERVER}/api/access/datafile/{file_id}/metadata/ddi"
        with urllib.request.urlopen(_request(url), timeout=60) as resp:
            cache.write_bytes(resp.read())
    m = re.search(r"<caseQnty>(\d+)</caseQnty>", cache.read_text(encoding="utf-8", errors="replace"))
    return int(m.group(1)) if m else None


def count_data_rows(path: Path) -> int:
    """Lines after the header row (both the original CSV and the tab export carry one header line)."""
    with path.open("rb") as fh:
        lines = sum(1 for _ in fh)
    return max(lines - 1, 0)


def verify(entry: dict, path: Path) -> dict:
    md5, sha, size = hash_file(path)
    variant = "unknown"
    if size == entry["original_size"]:
        variant = "original"
    elif size == entry["stored_size"]:
        variant = "tab-export"
    rec = {
        "dataverse_file_id": entry["id"],
        "file": path.name,
        "variant": variant,
        "bytes": size,
        "md5": md5,
        "md5_published": entry["md5"],
        "sha256": sha,
    }
    if md5 == entry["md5"]:
        rec["status"] = "verified"
    elif variant == "tab-export" and entry["is_tabular"]:
        # Verified 2026-10-11: the published MD5 is the checksum of the ORIGINAL upload (the original-format
        # CSVs match it exactly). A tab-delimited export is a converted copy and cannot match, so it is
        # verified by exact byte size plus the observation count Dataverse publishes in its DDI metadata.
        expected_rows = ddi_row_count(entry["id"])
        rows = count_data_rows(path)
        rec["rows"] = rows
        rec["rows_published"] = expected_rows
        rec["status"] = ("verified-size-and-rows" if expected_rows is not None and rows == expected_rows
                         else "MISMATCH-rows")
    else:
        rec["status"] = "MISMATCH"
    return rec


def guestbook_body() -> dict:
    missing = [env for env in [*GUESTBOOK_ENV.values(), INTENDED_USE_ENV] if not os.environ.get(env)]
    if missing:
        raise SystemExit(
            "Download needs your own Guestbook details. Set these in your .env (see .env.example): "
            + ", ".join(missing)
        )
    body = {k: os.environ[v] for k, v in GUESTBOOK_ENV.items()}
    body["answers"] = [{"id": 182, "value": os.environ[INTENDED_USE_ENV]}]
    return {"guestbookResponse": body}


def _find_signed_url(obj) -> str | None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k.lower() in ("signedurl", "signed_url") and isinstance(v, str):
                return v
            found = _find_signed_url(v)
            if found:
                return found
    elif isinstance(obj, list):
        for v in obj:
            found = _find_signed_url(v)
            if found:
                return found
    elif isinstance(obj, str) and obj.startswith("http") and "token=" in obj:
        return obj
    return None


def download(entry: dict) -> Path:
    """Submit the runner's guestbook response and download the original-format file."""
    params = {"signed": "true"}
    if entry["is_tabular"]:
        params["format"] = "original"
    url = f"{SERVER}/api/access/datafile/{entry['id']}?{urllib.parse.urlencode(params)}"
    data = json.dumps(guestbook_body()).encode("utf-8")
    try:
        with urllib.request.urlopen(
            _request(url, data=data, headers={"Content-Type": "application/json"}), timeout=120
        ) as resp:
            payload = resp.read()
    except urllib.error.HTTPError as e:
        # The body is not printed: a validation error can repeat the submitted Guestbook details.
        raise RuntimeError(f"Guestbook/download request for file {entry['id']} failed: HTTP {e.code} {e.reason}. "
                           "Check the DATAVERSE_GB_* values in your .env.") from None
    try:
        signed = _find_signed_url(json.loads(payload.decode("utf-8")))
    except (UnicodeDecodeError, json.JSONDecodeError):
        signed = None
    if not signed:
        raise RuntimeError(f"Dataverse did not return a signed URL for file {entry['id']}.")
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    target = RAW_DIR / entry["original_name"]
    partial = target.with_name(target.name + ".part")
    with urllib.request.urlopen(_request(signed), timeout=600) as resp, partial.open("wb") as out:
        shutil.copyfileobj(resp, out, length=4 * 1024 * 1024)
    partial.replace(target)
    return target


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--set", choices=sorted(SETS), default="first", help="which files are wanted")
    ap.add_argument("--download", action="store_true", help="download missing files (needs your Guestbook details)")
    ap.add_argument("--refresh-metadata", action="store_true")
    ap.add_argument("--dest", help="folder for the files and their manifest (default data/raw + data/manifest.json); "
                                   "used to test the download without touching data/raw")
    args = ap.parse_args(argv)
    global RAW_DIR, MANIFEST
    if args.dest:
        RAW_DIR = Path(args.dest).resolve()
        MANIFEST = RAW_DIR / "manifest.json"

    meta = fetch_dataset_metadata(refresh=args.refresh_metadata)
    cat = file_catalogue(meta)
    wanted = SETS[args.set] or sorted(cat)
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    results, problems = [], 0
    for fid in wanted:
        entry = cat[fid]
        path = find_local(entry)
        if path is None and args.download:
            print(f"downloading  {entry['original_name']} ...", flush=True)
            path = download(entry)
        if path is None:
            print(f"MISSING      {entry['original_name']}  (expected {entry['original_size']:,} bytes)")
            results.append({"dataverse_file_id": fid, "file": entry["original_name"], "status": "missing"})
            problems += 1
            continue
        r = verify(entry, path)
        results.append(r)
        print(f"{r['status']:<12} {r['file']}  {r['bytes']:,} bytes  ({r['variant']})")
        if r["status"] not in ("verified", "verified-size-and-rows"):
            problems += 1

    manifest = {
        "source": {
            "persistent_id": PERSISTENT_ID,
            "dataset_version": f"{meta['data']['latestVersion'].get('versionNumber')}."
                               f"{meta['data']['latestVersion'].get('versionMinorNumber')}",
            "licence": (meta["data"]["latestVersion"].get("license") or {}).get("name"),
            "attribution": "Prayas (Energy Group), Electricity Supply Monitoring Initiative (ESMI)",
            "terms": "docs/data/SOURCE_TERMS.md",
        },
        "verified_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "set": args.set,
        "files": results,
    }
    body = json.dumps(manifest["files"], sort_keys=True).encode("utf-8")
    manifest["files_sha256"] = hashlib.sha256(body).hexdigest()
    MANIFEST.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    shown = MANIFEST.relative_to(REPO_ROOT) if MANIFEST.is_relative_to(REPO_ROOT) else MANIFEST
    print(f"manifest: {shown}  files_sha256={manifest['files_sha256'][:16]}...")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
