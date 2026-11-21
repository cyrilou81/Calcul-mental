
from pathlib import Path
from PIL import Image

STATIC_DIR = Path("static")
QUALITY = 85

converted = 0
skipped = 0

for file in STATIC_DIR.rglob("*"):
    if file.suffix.lower() not in (".jpg", ".jpeg", ".png"):
        continue

    output = file.with_suffix(".webp")

    if output.exists():
        skipped += 1
        continue

    try:
        with Image.open(file) as img:
            img.save(output, "WEBP", quality=QUALITY, method=6)

        print(f"OK : {file} -> {output}")
        converted += 1

    except Exception as e:
        print(f"ERREUR : {file} : {e}")

print(f"\nTerminé : {converted} convertis, {skipped} ignorés.")
