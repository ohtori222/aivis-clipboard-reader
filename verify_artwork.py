import sys
import os

# srcディレクトリをパスに追加
sys.path.append(os.path.join(os.getcwd(), "src"))

from aivis_reader import ConfigManager


def test_artwork_resolution():
    print("--- Testing Artwork Resolution ---")

    # ConfigManagerの初期化（これによりロード処理が走る）
    cfg = ConfigManager()

    artwork_path = cfg.get("artwork_path")
    print(f"Resolved artwork_path: {artwork_path}")

    full_path = os.path.join(cfg.root_dir, artwork_path)
    print(f"Full path: {full_path}")
    print(f"Exists: {os.path.exists(full_path)}")

    # 期待値の確認
    # ルートに cover.jpg がなければ assets/cover_sample.jpg (または assets/cover.jpg) になっているはず
    if "assets" in artwork_path:
        print("✅ SUCCESS: Artwork resolved to assets folder.")
    elif (
        os.path.exists(os.path.join(cfg.root_dir, "cover.jpg"))
        and artwork_path == "cover.jpg"
    ):
        print("ℹ️ NOTE: Root cover.jpg found and prioritized.")
    else:
        print("❓ UNKNOWN: Unexpected path resolution.")


if __name__ == "__main__":
    test_artwork_resolution()
