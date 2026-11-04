"""Generate responsive images without changing or removing source photographs.

Run from the repository root with Python and Pillow installed.
"""
from pathlib import Path
from PIL import Image, ImageOps

root = Path("frontend/public/images")
original_bytes = 0
responsive_bytes = {320: 0, 640: 0}
for source in sorted((root / "products").iterdir()):
    if source.suffix.lower() not in {".png", ".jpg", ".jpeg"}:
        continue
    original_bytes += source.stat().st_size
    with Image.open(source) as image:
        image = ImageOps.exif_transpose(image).convert("RGBA")
        canvas = Image.new("RGBA", image.size, "white")
        canvas.alpha_composite(image)
        for width in (320, 640):
            scaled = canvas.convert("RGB")
            scaled.thumbnail((width, width), Image.Resampling.LANCZOS)
            output = source.with_name(f"{source.stem}-{width}.webp")
            scaled.save(output, "WEBP", quality=82, method=6)
            responsive_bytes[width] += output.stat().st_size
with Image.open(root / "hero.webp") as image:
    image.thumbnail((800, 1000), Image.Resampling.LANCZOS)
    image.save(root / "hero-mobile.webp", "WEBP", quality=83, method=6)
print({"original_bytes": original_bytes, "responsive_bytes": responsive_bytes})
