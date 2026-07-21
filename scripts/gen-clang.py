import json
import os
import re
import sys

import requests

GITHUB_API = "https://api.github.com/repos/llvm/llvm-project/releases"

PLATFORMS = [
    {"pattern": "Windows-X64", "goos": "windows", "goarch": "amd64", "ext": ".zip"},
    {"pattern": "Windows-ARM64", "goos": "windows", "goarch": "arm64", "ext": ".zip"},
    {"pattern": "Linux-X64", "goos": "linux", "goarch": "amd64", "ext": ".tar.xz"},
    {"pattern": "Linux-ARM64", "goos": "linux", "goarch": "arm64", "ext": ".tar.xz"},
    {"pattern": "macOS-X64", "goos": "darwin", "goarch": "amd64", "ext": ".tar.xz"},
    {"pattern": "macOS-ARM64", "goos": "darwin", "goarch": "arm64", "ext": ".tar.xz"},
]

BIN_PATH = {"windows": "bin/clang.exe", "linux": "bin/clang", "darwin": "bin/clang"}


def fetch_releases(page=1):
    url = f"{GITHUB_API}?per_page=20%page={page}"
    headers = {}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    resp = requests.get(url, headers=headers)
    resp = requests.get(url, headers=headers)

    return resp.json()


def parse_version(tag_name):
    """This function extract the clean version from tag, example: 'llvmorg-18.1.0"""
    match = re.match(r"llvmorg-(\d+\.\d+\.\d+)$", tag_name)
    if match:
        return match.group(1)

    return None


def get_checksum(asset_url, headers):
    """Now, we try to fetch SHA256 checksum from .sha256 file"""
    sha_url = asset_url + ".sha256"
    try:
        resp = requests.get(sha_url, headers=headers)
        if resp.status_code == 200:
            return resp.text.split()[0]
    except Exception:
        pass
    return ""


def build_manifest(existing_manifest=None):
    manifest = existing_manifest or {
        "name": "clang",
        "description": "LLVM/Clang compiler toolchain",
        "homepage": "https://llvm.org",
        "versions": {},
    }

    headers = {}
    token = os.environ.get("GITHUB_TOKEN")

    if token:
        headers["Authorization"] = f"Bearer {token}"

    print("Fetching LLVM releases . . .", file=sys.stderr)

    page = 1
    while True:
        releases = fetch_releases(page)
        if not releases:
            break

        for release in releases:
            # We will skip pre-releases
            if release.get("prerelease") or release.get("draft"):
                continue

            tag = release.get("tag_name", "")
            version = parse_version(tag)
            if not version:
                continue

            print(f"Processing LLVM/Clang {version}. . .", file=sys.stderr)

            if version not in manifest["versions"]:
                manifest["versions"][version] = {
                    "windows": {},
                    "linux": {},
                    "darwin": {},
                }

            assets = release.get("assets", [])

            for platform in PLATFORMS:
                for asset in assets:
                    name = asset["name"]

                    if (
                        platform["pattern"] in name
                        and name.endswith(platform["ext"])
                        and "installer" not in name.lower()
                    ):
                        checksum = get_checksum(asset["browser_download_url"], headers)
                        goos = platform["goos"]
                        goarch = platform["goarch"]

                        manifest["versions"][version][goos][goarch] = {
                            "url": asset["browser_download_url"],
                            "checksum": f"sha256:{checksum}",
                            "bin": BIN_PATH[goos],
                        }

                        print(f"{version} {goos}/{goarch}", file=sys.stderr)
                        break

        page += 1
        if page > 5:
            break

    return manifest


def main():
    manifest_path = "manifest/clang.json"

    existing = None
    if os.path.exists(manifest_path):
        try:
            with open(manifest_path, "r") as file:
                content = file.read().strip()
                if content:
                    existing = json.loads(content)
                    print("Loaded existing manifest, mergin. . .", file=sys.stderr)

        except json.JSONDecodeError as err:
            print(
                f"Could not parse existing manifest ({err}), starting fresh . . .",
                file=sys.stderr,
            )

    manifest = build_manifest(existing)

    with open(manifest_path, "w") as file:
        json.dump(manifest, file, indent=2)

    print(f"\nSuccesfully manifest written to {manifest_path}", file=sys.stderr)
    print(f"   Total versions: {len(manifest['version'])}", file=sys.stderr)


if __name__ == "__main__":
    main()
