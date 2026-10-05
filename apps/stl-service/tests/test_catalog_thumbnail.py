from __future__ import annotations

from PIL import Image, ImageStat
from io import BytesIO
import pytest

from catalog_thumbnail import CANVAS, render_product_thumbnail


@pytest.mark.parametrize(
    "slug",
    ["vesa-adapter", "cable-tray", "vertical-laptop-dock", "desk-grommet", "electronics-box"],
)
def test_catalog_thumbnail_is_real_png_for_canonical_geometry(slug):
    data = render_product_thumbnail(slug)
    assert data.startswith(b"\x89PNG\r\n\x1a\n")
    image = Image.open(BytesIO(data))
    assert image.size == CANVAS
    assert image.mode == "RGB"
    assert len(data) > 5000
    # The renderer must produce a real lit product image, not a near-flat
    # placeholder. Keep this deliberately broad so the visual system can evolve.
    stats = ImageStat.Stat(image)
    assert max(stats.stddev) > 12


def test_thumbnail_render_is_deterministic_and_cached():
    first = render_product_thumbnail("vesa-adapter")
    second = render_product_thumbnail("vesa-adapter")
    assert first == second


def test_generated_thumbnail_uses_bright_studio_language():
    data = render_product_thumbnail("vertical-laptop-dock")
    image = Image.open(BytesIO(data)).convert("RGB")

    # Studio background should stay bright/cool, while the product itself
    # contributes clearly darker pixels. Broad thresholds avoid overfitting.
    corner = image.crop((0, 0, 160, 120))
    corner_mean = sum(ImageStat.Stat(corner).mean) / 3
    extrema = image.getextrema()
    darkest = min(channel[0] for channel in extrema)

    assert corner_mean > 150
    assert darkest < 90
