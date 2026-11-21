"""Build a self-contained PyPI distribution with its compiled, generic admin SPA.

Run from the repository root: uv run python scripts/build_release.py
The Pyntral UI is compiled in a temporary, empty host project. Application-owned
TSX extensions, credentials and generated bridge contracts are never packaged.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zipfile
import tarfile

ROOT = Path(__file__).resolve().parents[1]
EMBEDDED = ROOT / "src" / "pyntral" / "web_dist"


def validate_spa(source: Path) -> None:
    if not (source / "index.html").is_file():
        raise ValueError(f"Missing compiled SPA entrypoint: {source / 'index.html'}")
    if not (source / "assets").is_dir() or not any(
        child.suffix == ".js" for child in (source / "assets").rglob("*")
    ):
        raise ValueError(f"Missing compiled JavaScript assets: {source / 'assets'}")


def embed_spa(source: Path) -> None:
    """Copy the generic compiled SPA to the setuptools package-data directory."""
    source = source.resolve()
    validate_spa(source)
    if source == EMBEDDED.resolve():
        return
    # Clean stale hashed assets from previous releases.
    if EMBEDDED.exists():
        shutil.rmtree(EMBEDDED)
    shutil.copytree(source, EMBEDDED)


def verify_artifacts(dist: Path) -> None:
    wheels = sorted(dist.glob("pyntral-*.whl"))
    sources = sorted(dist.glob("pyntral-*.tar.gz"))
    if len(wheels) != 1 or len(sources) != 1:
        raise RuntimeError("Expected exactly one wheel and one sdist in dist/")
    with zipfile.ZipFile(wheels[0]) as archive:
        names = archive.namelist()
        for suffix in ("web_dist/index.html", ".js", ".css"):
            if not any("pyntral/web_dist/" in name and name.endswith(suffix) for name in names):
                raise RuntimeError(f"Wheel missing SPA asset: {suffix}")
        if any("/.pyntral/" in name or "admin/Insights" in name for name in names):
            raise RuntimeError("Wheel unexpectedly contains application-local frontend files")
    with tarfile.open(sources[0], "r:gz") as archive:
        names = archive.getnames()
        if not any("/src/pyntral/web_dist/index.html" in name for name in names):
            raise RuntimeError("Sdist missing bundled SPA")
    print(f"[pyntral] Verified self-contained distributions: {wheels[0].name}, {sources[0].name}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from-dist", type=Path, help="Use an already built GENERIC SPA instead of invoking npm")
    args = parser.parse_args()
    os.chdir(ROOT)
    if args.from_dist:
        embed_spa(args.from_dist)
    else:
        with tempfile.TemporaryDirectory(prefix="pyntral-release-") as directory:
            project = Path(directory)
            # Deliberately no pyntral.components.json or custom bridge registry.
            subprocess.run([
                "uv", "run", "pyntral", "--project", str(project),
                "build", "--base", "/admin/", "--force",
            ], cwd=ROOT, check=True)
            embed_spa(project / ".pyntral" / "dist")
    target = ROOT / "dist"
    # Setuptools reuses build/lib; remove old hashed assets from earlier builds.
    for generated in (target, ROOT / "build"):
        if generated.exists():
            shutil.rmtree(generated)
    subprocess.run(["uv", "build", "--out-dir", str(target)], cwd=ROOT, check=True)
    verify_artifacts(target)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"pyntral release: {exc}", file=sys.stderr)
        sys.exit(1)
