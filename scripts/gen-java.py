import json
import os
import sys

import requests

ADOPTIUM_API = "https://api.adoptium.net/v3"

PLATFORMS = [
    {"os": "windows", "arch": "x64", "goos": "windows", "goarch": "amd64"},
    {"os": "windows", "arch": "aarch64", "goos": "windows", "goarch": "arm64"},
    {"os": "linux", "arch": "x64", "goos": "linux", "goarch": "amd64"},
    {"os": "linux", "arch": "aarch64", "goos": "linux", "goarch": "arm64"},
    {"os": "mac", "arch": "x64", "goos": "darwin", "goarch": "amd64"},
    {"os": "mac", "arch": "aarch64", "goos": "darwin", "goarch": "arm64"},
]

BIN_PATH = {
    "windows": "bin/java.exe",
    "linux": "bin/java",
    "darwin": "Contents/Home/bin/java",
}


def fetch_all_versions():
    """Fetch all available major versions from Adoptium"""
    url = f"{ADOPTIUM_API}/info/available_releases"

    resp = requests.get(url)
    resp.raise_for_status()

    data = resp.json()
    return data["available_releases"]


def fetch_version_builds(major, goos, arch):
    """Fetch all builds for a major version on a specific platform"""
    url = (
        f"{ADOPTIUM_API}/assets/feature_releases/{major}/ga"
        f"?architecture={arch}&image_type=jdk&os={goos}&vendor=eclipse&page_size=20"
    )
    resp = requests.get(url)
    if resp.status_code == 404:
        return []
    resp.raise_for_status()
    return resp.json()


def build_manifest(existing_manifest=None):
    manifest = existing_manifest or {
        "name": "java",
        "description": "OpenJDK via Eclipse Temurin",
        "homepage": "https://adoptium.net",
        "versions": {},
    }

    major_versions = fetch_all_versions()
    print(f"Found major versions: {major_versions}", file=sys.stderr)

    for major in major_versions:
        print(f"Processing Java {major}...", file=sys.stderr)

        for platform in PLATFORMS:
            releases = fetch_version_builds(major, platform["os"], platform["arch"])

            for release in releases:
                # feature_releases returns releases with nested binaries array
                version_data = release.get("version", {})
                semver = version_data.get("semver", "")
                binaries = release.get("binaries", [])

                if not semver or not binaries:
                    continue

                # Get first binary that matches
                binary = binaries[0]
                package = binary.get("package", {})

                if not package.get("link"):
                    continue

                if semver not in manifest["versions"]:
                    manifest["versions"][semver] = {
                        "windows": {},
                        "linux": {},
                        "darwin": {},
                    }

                goos = platform["goos"]
                goarch = platform["goarch"]

                manifest["versions"][semver][goos][goarch] = {
                    "url": package["link"],
                    "checksum": f"sha256:{package.get('checksum', '')}",
                    "bin": BIN_PATH[goos],
                }

                print(f"  ✓ {semver} {goos}/{goarch}", file=sys.stderr)

    return manifest


def main():
    manifest_path = "manifests/java.json"

    existing = None
    if os.path.exists(manifest_path):
        try:
            with open(manifest_path, "r") as f:
                content = f.read().strip()
                if content:
                    existing = json.loads(content)
                    print("Loaded existing manifest, merging . . .", file=sys.stderr)
                else:
                    print("Existing manifest is empty, starting fresh", file=sys.stderr)
        except json.JSONDecodeError as err:
            print(
                f"Could not parse existing manifest ({err}), starting fresh. . . ",
                file=sys.stderr,
            )

    manifest = build_manifest(existing)

    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"Manifest written to {manifest_path}", file=sys.stderr)
    print(f"   Total versions: {len(manifest['versions'])}", file=sys.stderr)


if __name__ == "__main__":
    main()
