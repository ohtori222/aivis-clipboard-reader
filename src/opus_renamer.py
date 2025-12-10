import os
import sys
import glob

try:
    from mutagen import File
except ImportError:
    print("❌ エラー: mutagen がインストールされていません。")
    print("pip install mutagen を実行してください。")
    input("Enterキーを押して終了...")
    sys.exit()


def main():
    print("=== 🎵 Opus アーティスト名 一括変換ツール ===")

    # 1. フォルダの指定（ドラッグ＆ドロップ対応）
    target_dir = (
        input("📁 対象のフォルダをここにドラッグ＆ドロップしてください: ")
        .strip()
        .strip('"')
    )

    if not os.path.isdir(target_dir):
        print("❌ エラー: フォルダが見つかりません。")
        return

    # 2. 新しいアーティスト名の入力
    new_artist = input("👤 新しいアーティスト名を入力してください: ").strip()
    if not new_artist:
        print("❌ エラー: アーティスト名が空です。")
        return

    # 3. ファイルの検索 (.opus)
    # サブフォルダは含まず、直下のみ検索します
    files = glob.glob(os.path.join(target_dir, "*.opus"))

    if not files:
        print("⚠️ .opus ファイルが見つかりませんでした。")
        return

    print(f"\n🔍 {len(files)} 個のファイルを検出しました。変換を開始します...")

    count = 0
    error_count = 0

    for filepath in files:
        filename = os.path.basename(filepath)
        try:
            audio = File(filepath)

            if audio is None:
                print(f"⚠️ スキップ (非対応形式): {filename}")
                error_count += 1
                continue

            # タグの書き換え (Vorbis Comment)
            # リスト形式で渡すのが作法です
            audio["artist"] = [new_artist]
            audio.save()

            print(f"✅ 更新: {filename}")
            count += 1

        except Exception as e:
            print(f"❌ 失敗: {filename} ({e})")
            error_count += 1

    print("-" * 30)
    print("🎉 完了しました！")
    print(f"成功: {count} 件")
    if error_count > 0:
        print(f"失敗: {error_count} 件")

    input("\nEnterキーを押して終了...")


if __name__ == "__main__":
    main()
