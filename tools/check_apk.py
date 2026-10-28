"""Fail a build if bundled question banks or their images accidentally return to the APK."""
import sys
import zipfile

with zipfile.ZipFile(sys.argv[1]) as apk:
    assets = [name for name in apk.namelist() if name.startswith("assets/")]
    assert "assets/catalog.json" in assets, "Missing bootstrap catalog"
    assert not any(name.startswith("assets/questions/") or
                   (name.endswith(".json") and name != "assets/catalog.json") for name in assets), assets
print("APK contains only the bootstrap catalog; no bundled banks or question images")
