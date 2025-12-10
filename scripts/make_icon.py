import os

from PIL import Image

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src = os.path.join(base_dir, "assets/cover_sample.jpg")
dst = os.path.join(base_dir, "assets/icon.ico")

if os.path.exists(src):
    try:
        img = Image.open(src)
        img.save(
            dst,
            format="ICO",
            sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)],
        )
        print(f"Created {dst} from {src}")
    except Exception as e:
        print(f"Error converting image: {e}")
else:
    print(f"{src} not found")
