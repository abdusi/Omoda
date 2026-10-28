"""Publish generated content with an isolated Git index; keep old versions addressable."""
import os
import json
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / ".content"


def git(*args, data=None, env=None, check=True):
    return subprocess.run(["git", *args], cwd=ROOT, input=data, env=env,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=check)


def publish():
    fetch = git("fetch", "origin", "content", check=False)
    if fetch.returncode and b"couldn't find remote ref" not in fetch.stderr:
        raise RuntimeError(fetch.stderr.decode(errors="replace"))
    parent = git("rev-parse", "FETCH_HEAD").stdout.decode().strip() if fetch.returncode == 0 else None
    catalog = json.loads((OUTPUT / "catalog.json").read_text("utf-8"))
    if parent and not any(s.get("source") for s in catalog["subjects"]):
        print("Initial content already exists; seed will not replace published banks")
        return
    with tempfile.TemporaryDirectory(prefix="omoda-index-") as temporary:
        env = dict(os.environ, GIT_INDEX_FILE=str(Path(temporary) / "index"))
        git("read-tree", parent if parent else "--empty", env=env)
        files = sorted(p for p in OUTPUT.rglob("*") if p.is_file())
        if not (OUTPUT / "catalog.json").is_file():
            raise ValueError("No catalog to publish")
        hashes = git("hash-object", "-w", "--stdin-paths",
                     data="".join(str(p) + "\n" for p in files).encode()).stdout.decode().splitlines()
        records = "".join(f"100644 {sha}\t{p.relative_to(OUTPUT).as_posix()}\n"
                          for p, sha in zip(files, hashes))
        git("update-index", "--index-info", data=records.encode(), env=env)
        tree = git("write-tree", env=env).stdout.decode().strip()
        if parent and tree == git("rev-parse", f"{parent}^{{tree}}").stdout.decode().strip():
            print("Content unchanged")
            return
        args = ["commit-tree", tree, "-m", "content: publish verified question banks"]
        if parent:
            args.extend(["-p", parent])
        commit = git(*args).stdout.decode().strip()
        # Normal fast-forward push rejects a concurrent publication.
        result = git("push", "origin", f"{commit}:refs/heads/content", check=False)
        if result.returncode:
            raise RuntimeError(result.stderr.decode(errors="replace"))
        print(f"Content published: {commit}")


if __name__ == "__main__":
    publish()
