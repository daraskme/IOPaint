"""Verify that built distributions contain IOPaint's runtime data files."""

from __future__ import annotations

import argparse
import tarfile
import zipfile
from pathlib import Path

REQUIRED_FILES = {
    "iopaint/web_app/index.html",
    "iopaint/model/anytext/anytext_sd15.yaml",
    "iopaint/model/anytext/ocr_recog/ppocr_keys_v1.txt",
    "iopaint/model/original_sd_configs/sd_xl_base.yaml",
    "iopaint/model/original_sd_configs/sd_xl_refiner.yaml",
    "iopaint/model/original_sd_configs/v1-inference.yaml",
    "iopaint/model/original_sd_configs/v2-inference-v.yaml",
}


def normalized_names(archive: Path) -> set[str]:
    if archive.suffix == ".whl":
        with zipfile.ZipFile(archive) as wheel:
            return set(wheel.namelist())

    with tarfile.open(archive, mode="r:gz") as sdist:
        names = set()
        for member in sdist.getmembers():
            parts = Path(member.name).parts
            if len(parts) > 1:
                names.add(Path(*parts[1:]).as_posix())
        return names


def check_archive(archive: Path) -> list[str]:
    names = normalized_names(archive)
    errors = [
        f"missing {required}"
        for required in sorted(REQUIRED_FILES)
        if required not in names
    ]
    for suffix in (".css", ".js"):
        if not any(
            name.startswith("iopaint/web_app/") and name.endswith(suffix)
            for name in names
        ):
            errors.append(f"missing iopaint/web_app/**{suffix}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("dist_dir", type=Path, nargs="?", default=Path("dist"))
    args = parser.parse_args()

    archives = sorted(args.dist_dir.glob("*.whl")) + sorted(
        args.dist_dir.glob("*.tar.gz")
    )
    if not archives:
        print(f"No wheel or sdist found in {args.dist_dir}")
        return 1

    failed = False
    for archive in archives:
        errors = check_archive(archive)
        if errors:
            failed = True
            print(f"{archive}: FAIL")
            for error in errors:
                print(f"  - {error}")
        else:
            print(f"{archive}: packaged assets verified")
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
