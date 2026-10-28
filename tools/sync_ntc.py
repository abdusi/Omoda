"""Discover paired NTC PDFs, import into staging, and publish only verified complete banks."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import tempfile
import time
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup

from content import SOURCE_PAGE, SUBJECTS, build, encode
from import_bank import (SPECS, CLUSTER3_SPECS, CLUSTER4_SPECS,
                         CLUSTER5_SPECS, answer_keys, extract)

ALL_SPECS = {spec[0]: spec for spec in SPECS + CLUSTER3_SPECS + CLUSTER4_SPECS + CLUSTER5_SPECS}
MAX_PDF_BYTES = 80 * 1024 * 1024


def ntc_url(url):
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in {"ntc.tj", "www.ntc.tj"}:
        raise ValueError(f"Unexpected source URL: {url}")
    return url


def download(url, maximum=MAX_PDF_BYTES):
    ntc_url(url)
    for attempt in range(3):
        try:
            request = Request(url, headers={"User-Agent": "Omoda-content-sync/1.0"})
            with urlopen(request, timeout=60) as response:
                ntc_url(response.url)
                data = response.read(maximum + 1)
            if len(data) > maximum:
                raise ValueError("Source exceeds configured download limit")
            return data
        except (OSError, TimeoutError):
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)


def discover(html, page_url=SOURCE_PAGE):
    soup = BeautifulSoup(html, "html.parser")
    table = next((t for t in soup.find_all("table")
                  if any("A1-ALL_Tj.pdf" in a.get("href", "") for a in t.find_all("a"))), None)
    if table is None:
        raise ValueError("Component A table not found; NTC page layout needs review")
    by_stem = {spec[2].casefold(): sid for sid, spec in ALL_SPECS.items()}
    pairs = {}
    for cell in table.find_all(["td", "th"]):
        anchors = cell.find_all("a", href=True)
        pending = None
        for anchor in anchors:
            url = ntc_url(urljoin(page_url, anchor["href"])) if ".pdf" in anchor["href"].lower() else None
            if url is None:
                continue
            stem = Path(urlparse(url).path).stem.casefold()
            if "/keys_" in url:
                if pending:
                    pair = {"questionsUrl": pending[1], "keysUrl": url}
                    if pending[0] in pairs and pairs[pending[0]] != pair:
                        raise ValueError(f"Conflicting sources for {pending[0]}")
                    pairs[pending[0]] = pair
                    pending = None
            elif stem in by_stem:
                pending = (by_stem[stem], url)
    missing = set(SUBJECTS) - pairs.keys()
    if missing:
        raise ValueError(f"Missing Tajik question/key pairs: {sorted(missing)}")
    years = {int(re.search(r"/keys_(20\d{2})/", p["keysUrl"]).group(1))
             for p in pairs.values() if re.search(r"/keys_(20\d{2})/", p["keysUrl"])}
    if len(years) != 1:
        raise ValueError("Missing or inconsistent source years")
    return pairs, years.pop()


def sync(workspace, output, page_url=SOURCE_PAGE, selected=SUBJECTS, limit=0):
    pairs, year = discover(download(page_url, maximum=2 * 1024 * 1024), page_url)
    workspace.mkdir(parents=True, exist_ok=True)
    state_path = workspace / "sources.json"
    state = json.loads(state_path.read_text("utf-8")) if state_path.exists() else {}
    for sid in selected:
        spec = ALL_SPECS[sid]
        provenance = dict(pairs[sid], year=year, language="tj", component="A")
        sources = workspace / "pdf" / sid
        sources.mkdir(parents=True, exist_ok=True)
        for field, name in [("questionsUrl", f"{spec[2]}.pdf"), ("keysUrl", f"{spec[2]}_key.pdf")]:
            data = download(provenance[field])
            if not data.startswith(b"%PDF-"):
                raise ValueError(f"{sid}: source is not a PDF")
            (sources / name).write_bytes(data)
            provenance[field.replace("Url", "Sha256")] = hashlib.sha256(data).hexdigest()
        fingerprint = dict(provenance, limit=limit)
        existing = workspace / "app/src/main/assets" / f"{sid}.json"
        if state.get(sid) == fingerprint and existing.exists():
            print(f"{sid}: unchanged", flush=True)
            continue
        keys = answer_keys(sources / f"{spec[2]}_key.pdf", spec[4])
        if not keys:
            raise ValueError(f"{sid}: no readable answer keys; OCR/layout review required")
        expected = {number for number in keys if not limit or number <= limit}
        with tempfile.TemporaryDirectory(prefix="import-", dir=workspace) as temporary:
            stage = Path(temporary)
            extract(sources, limit, [spec], output_root=stage)
            bank_path = stage / "app/src/main/assets" / f"{sid}.json"
            questions = json.loads(bank_path.read_text("utf-8"))
            if {q["number"] for q in questions} != expected:
                raise ValueError(f"{sid}: incomplete extraction; keep previous published version")
            for q in questions:
                if q["correct"] != "ABCD".index(keys[q["number"]]):
                    raise ValueError(f"{sid}: mismatched answer key")
            destination = workspace / "app/src/main/assets"
            shutil.copytree(stage / "app/src/main/assets", destination, dirs_exist_ok=True)
            shutil.copytree(stage / "tools", workspace / "reports", dirs_exist_ok=True)
        state[sid] = fingerprint
        state_path.write_bytes(encode(state))
    if set(selected) != set(SUBJECTS) or limit:
        print("Partial verification run; publication disabled")
        return
    # A failed subject aborts before a new catalog can be published.
    build(workspace / "app/src/main/assets", output, year=year,
          source_page=page_url, provenance=state)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=Path(".source"))
    parser.add_argument("--output", type=Path, default=Path(".content"))
    parser.add_argument("--page", default=SOURCE_PAGE)
    parser.add_argument("--subjects", nargs="+", choices=SUBJECTS, default=SUBJECTS)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()
    sync(args.workspace, args.output, args.page, args.subjects, args.limit)
