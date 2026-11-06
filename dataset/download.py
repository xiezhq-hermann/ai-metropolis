#!/usr/bin/env python3
"""Download, verify and unpack the AI Metropolis dataset. Needs only the standard library.

    python dataset/download.py                  # replay traces, enough for every benchmark
    python dataset/download.py raw-days         # the 31 whole-day runs, with timestamps
    python dataset/download.py --all
"""
import argparse
import hashlib
import json
import os
import sys
import tarfile
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
CHUNK = 1 << 20


def sha256_of(path):
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fetch(url, destination, expected_sha256):
    if destination.exists() and sha256_of(destination) == expected_sha256:
        print(f"{destination.name}: already downloaded")
        return
    partial = destination.with_name(destination.name + ".part")
    with urllib.request.urlopen(url) as response, open(partial, "wb") as out:
        total = int(response.headers.get("Content-Length") or 0)
        done = 0
        for chunk in iter(lambda: response.read(CHUNK), b""):
            out.write(chunk)
            done += len(chunk)
            if total:
                print(f"\r{destination.name}: {done / total:6.1%} of {total / 1e6:.0f} MB", end="", flush=True)
    print()
    actual = sha256_of(partial)
    if actual != expected_sha256:
        partial.unlink()
        sys.exit(f"{destination.name}: checksum mismatch (got {actual}), download discarded")
    os.replace(partial, destination)


def unpack(archive, root, files):
    """Extract only regular files listed in the manifest, verifying each one."""
    count = 0
    with tarfile.open(archive, "r:xz") as tar:
        for member in tar:
            expected = files.get(member.name)
            if expected is None or not member.isfile():
                sys.exit(f"{archive.name}: unexpected entry {member.name!r}")
            target = root / member.name
            target.parent.mkdir(parents=True, exist_ok=True)
            digest = hashlib.sha256()
            partial = target.with_name(target.name + ".part")
            source = tar.extractfile(member)
            with open(partial, "wb") as out:
                for chunk in iter(lambda: source.read(CHUNK), b""):
                    digest.update(chunk)
                    out.write(chunk)
            if digest.hexdigest() != expected["sha256"]:
                partial.unlink()
                sys.exit(f"{member.name}: checksum mismatch")
            os.replace(partial, target)
            count += 1
    return count


def main():
    manifest = json.loads((HERE / "MANIFEST.json").read_text())
    subsets = list(manifest["archives"])
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("subsets", nargs="*", metavar="subset", help=f"any of {', '.join(subsets)} (default: replay)")
    parser.add_argument("--all", action="store_true", help="fetch every subset")
    parser.add_argument("--output", type=Path, default=HERE, help="where to unpack (default: next to this script)")
    parser.add_argument("--base-url", default=manifest["base_url"], help="alternative location of the archives")
    parser.add_argument("--keep-archives", action="store_true", help="keep the .tar.xz files after unpacking")
    args = parser.parse_args()

    selected = subsets if args.all else args.subsets or ["replay"]
    unknown = sorted(set(selected) - set(subsets))
    if unknown:
        parser.error(f"unknown subset: {', '.join(unknown)}")

    args.output.mkdir(parents=True, exist_ok=True)
    for subset in selected:
        entry = manifest["archives"][subset]
        archive = args.output / entry["file"]
        fetch(f'{args.base_url.rstrip("/")}/{entry["file"]}', archive, entry["sha256"])
        count = unpack(archive, args.output, manifest["files"])
        print(f"{subset}: {count} files verified and unpacked into {args.output}")
        if not args.keep_archives:
            archive.unlink()


if __name__ == "__main__":
    main()
