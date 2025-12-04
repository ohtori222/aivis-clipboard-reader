# AivisSpeech Clipboard Reader

クリップボードにコピーされたテキストをリアルタイムで検知し、**AivisSpeech** (または VOICEVOX) を使用して読み上げるPythonツールです。
「Web記事のながら聴き」や「AIチャットのログ音声化」に最適化されています。

## ✨ 特徴

* **⚡ ストリーミング再生 & 順次キューイング**
  * コピーした順に自動で予約リスト（キュー）に入り、途切れることなく読み上げます。
* **🧹 高度なテキストクリーニング**
  * Markdown記号（`#`, `*`等）、URL、ルビ（`漢（おとこ）`→`おとこ`）を自動で整形して読み上げます。
* **⌨️ ホットキー操作**
  * 他のウィンドウで作業中でも、キーボードショートカットで「一時停止」「緊急停止」が可能です。
* **📂 リッチなログ保存 (FFmpeg連携)**
  * **FFmpegインストール済みの場合**: 高圧縮な **Opus形式 (.ogg)** で保存し、カバー画像 (`cover.jpg`) を自動で埋め込みます。
  * **FFmpegなしの場合**: **FLAC形式** で音声を保存します。
  * 日次フォルダ（例: `251204/`）を作成し、ファイル名にタイトルを含めて自動整理します。

## 📦 必要要件

* **OS:** Windows (推奨) / macOS / Linux
* **Python:** 3.8 以上
* **音声合成エンジン:** 以下のいずれかがローカルで起動していること
  * AivisSpeech (推奨)
  * VOICEVOX
* **(推奨) FFmpeg:** インストールしてパスを通しておくと、Opus圧縮と画像埋め込み機能が有効になります。

## 🚀 インストール

1. **リポジトリのクローン**
   ```bash
   git clone [https://github.com/ohtori222/aivis-clipboard-reader.git](https://github.com/ohtori222/aivis-clipboard-reader.git)
   cd aivis-clipboard-reader
   ```

2. **依存ライブラリのインストール**
   ```bash
   # 仮想環境の作成と有効化 (Windows)
   python -m venv .venv
   .\.venv\Scripts\activate

   # インストール
   pip install -r requirements.txt
   ```

3. **設定ファイルの準備**
   `settings_template.py` は廃止されました。代わりに `config.json` を作成してください。
   ```json
   {
     "speaker_id": 888753760,
     "host": "127.0.0.1",
     "port": 10101,
     "hotkeys": {
       "stop": "ctrl+alt+s",
       "pause": "ctrl+alt+p"
     }
   }
   ```
   ※ その他の設定項目はソースコード内のデフォルト値が使われます。

4. **アートワークの準備（任意）**
   スクリプトと同じフォルダに `cover.jpg` を置くと、生成される音声ファイル(Ogg)に埋め込まれます。

## ▶️ 使い方

1. AivisSpeech / VOICEVOX を起動します。
2. スクリプトを実行します。
   ```bash
   python aivis_reader.py
   ```
3. 読み上げたいテキストを **コピー (Ctrl+C)** すると、自動で読み上げが始まります。

### ⌨️ 操作コマンド (ホットキー)

作業中でも以下のキーで操作可能です（`config.json` で変更可能）。

* **Ctrl + Alt + S**: **緊急停止** (再生を止め、予約キューを全て破棄します)
* **Ctrl + Alt + P**: **一時停止 / 再開**

## ⚙️ 設定 (config.json)

プロジェクトルートに `config.json` を置くことで設定を変更できます。

| キー | 説明 | デフォルト |
| :--- | :--- | :--- |
| `speaker_id` | 使用するボイスのID | `888753760` |
| `output_dir` | 保存先フォルダ名 | `"Aivis_AudioLog"` |
| `dropbox_dir` | Dropboxのルートパス (nullで自動検出) | `null` |
| `speed` | 話速 | `1.0` |
| `hotkeys` | 操作キー割り当て | (上記参照) |

### 🔧 開発者向け: config.local.json

`config.local.json` というファイルを作成すると、`config.json` の設定を上書きできます。
このファイルは `.gitignore` に含まれているため、自分の環境専用のパスや設定を書いてもコミットされません。

```json
{
  "dropbox_dir": "D:\\Personal\\Dropbox",
  "volume": 0.8
}
```

## 📜 License

[MIT License](LICENSE)