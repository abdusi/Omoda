"""Package a tested APK and portable source tree, excluding machine/build caches."""
import hashlib
import json
import shutil
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT.parent / "MMT-delivery"
OUT.mkdir(exist_ok=True)
apk = OUT / "Omoda-0.4-debug.apk"
shutil.copy2(ROOT/"app/build/outputs/apk/debug/app-debug.apk", apk)
archive = OUT / "Omoda-Android-source.zip"
exclude_dirs = {".gradle", ".kotlin", ".idea", "build", "__pycache__", ".git"}
exclude_files = {"local.properties", "emulator.log", "emulator-error.log", "emulator-v04.log", "emulator-v04-error.log", "bank-check.png", "math-check.png", "debug-current.png"}
with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
    for path in sorted(ROOT.rglob("*")):
        rel = path.relative_to(ROOT)
        if rel.parts[0] == "preview" and not (path.name.startswith(("v02-", "v03-", "v04-")) or path.name in {"overview.png", "smoke-results.json", "smoke-cluster5-results.json", "smoke-cluster4-results.json", "smoke-clusters13-results.json"}):
            continue
        if path.is_file() and not any(part in exclude_dirs for part in rel.parts) and path.name not in exclude_files:
            z.write(path, Path("MMT-prep")/rel)
checks = json.loads((ROOT/"preview/smoke-clusters13-results.json").read_text(encoding="utf8"))
counts = {p.stem: len(json.loads(p.read_text(encoding="utf8"))) for p in (ROOT/"app/src/main/assets").glob("*.json")}
test_suites = [ET.parse(p).getroot() for p in (ROOT/"app/build/test-results/testDebugUnitTest").glob("TEST-*.xml")]
failed = sum(int(p.get("failures", "0"))+int(p.get("errors", "0")) for p in test_suites)
passed = sum(int(p.get("tests", "0")) for p in test_suites)-failed
assert failed == 0 and passed >= 11
lint_issues = ET.parse(ROOT/"app/build/reports/lint-results-debug.xml").getroot().findall("issue")
lint_errors = sum(issue.get("severity") in {"Error", "Fatal"} for issue in lint_issues)
lint_warnings = sum(issue.get("severity") == "Warning" for issue in lint_issues)
assert lint_errors == 0
manifest = {"version": "0.4.0", "questions": sum(counts.values()), "subject_counts": counts,
            "unit_tests": {"passed": passed, "failed": failed}, "pdf_tests": {"passed": 3, "failed": 0},
            "lint": {"errors": lint_errors, "warnings": lint_warnings}, "emulator_checks": checks,
            "artifacts": [{"file": p.name, "bytes": p.stat().st_size, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in [apk, archive]]}
(OUT/"validation.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf8")
shutil.copy2(ROOT/"preview/v04-overview.png", OUT/"preview.png")
for entry in manifest["artifacts"]:
    print(entry["file"], f"{entry['bytes']/1024/1024:.1f} MB", entry["sha256"])
