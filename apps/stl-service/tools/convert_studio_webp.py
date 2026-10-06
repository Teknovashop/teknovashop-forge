from pathlib import Path
from PIL import Image, ImageEnhance, ImageFilter
import sys

src = Path(sys.argv[1])
dst = Path(sys.argv[2])
img = Image.open(src).convert("RGB")

# Subtle final polish only; Blender provides the actual product lighting.
img = ImageEnhance.Contrast(img).enhance(1.04)
img = ImageEnhance.Color(img).enhance(0.96)
img = img.filter(ImageFilter.UnsharpMask(radius=1.0, percent=70, threshold=3))
img.save(dst, "WEBP", quality=92, method=6)
