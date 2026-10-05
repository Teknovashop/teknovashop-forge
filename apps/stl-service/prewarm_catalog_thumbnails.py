from __future__ import annotations

from catalog_thumbnail import CACHE_DIR, render_product_thumbnail
from model_contracts import PRODUCTS


def main() -> None:
    failures: list[tuple[str, str]] = []
    for index, slug in enumerate(sorted(PRODUCTS), start=1):
        try:
            data = render_product_thumbnail(slug)
            if not data.startswith(b"\x89PNG\r\n\x1a\n"):
                raise RuntimeError("not a PNG")
            print(f"[{index:02d}/{len(PRODUCTS)}] {slug}: {len(data)} bytes")
        except Exception as exc:
            failures.append((slug, f"{type(exc).__name__}: {exc}"))

    if failures:
        for slug, error in failures:
            print(f"FAILED {slug}: {error}")
        raise SystemExit(1)

    print(f"Pre-rendered {len(PRODUCTS)} catalog thumbnails into {CACHE_DIR}")


if __name__ == "__main__":
    main()
