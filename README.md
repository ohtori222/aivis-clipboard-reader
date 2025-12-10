<div align="center">
  <img src="assets/cover_sample.jpg" width="150" height="150">
</div>

# AivisSpeech Clipboard Reader

クリップボードにコピーされたテキストをリアルタイムで検知し、**AivisSpeech** (または VOICEVOX) を使用して読み上げる Python ツールです。
「Web 記事のながら聴き」や「AI チャットのログ音声化」に最適化されています。

[![Download](https://img.shields.io/github/v/release/ohtori222/aivis-clipboard-reader?label=Download&style=for-the-badge&logo=windows)](https://github.com/ohtori222/aivis-clipboard-reader/releases/latest)
　![Downloads](https://img.shields.io/github/downloads/ohtori222/aivis-clipboard-reader/total?style=flat-square&logo=github&label=Downloads&color=blue)

## ✨ 特徴

- **⚡ ストリーミング再生 & 順次キューイング**
  - コピーした順に自動で予約リスト（キュー）に入り、途切れることなく読み上げます。
- **🧹 高度なテキストクリーニング**
  - Markdown 記号（`#`, `*`等）、URL、ルビ（`漢（おとこ）`→`おとこ`）を自動で整形して読み上げます。
- **⌨️ ホットキー操作**
  - 他のウィンドウで作業中でも、キーボードショートカットで「一時停止」「緊急停止」が可能です。
- **📂 リッチなログ保存 (FFmpeg 連携)**
  - **FFmpeg インストール済みの場合**: 高圧縮な **Opus 形式 (.opus)** で保存し、カバー画像 (`cover.jpg`) を自動で埋め込みます。
  - **FFmpeg なしの場合**: **FLAC 形式** で音声を保存します。
  - 日次フォルダ（例: `251204/`）を作成し、ファイル名にタイトルを含めて自動整理します。

## 🔒 プライバシーとセキュリティ

ユーザーのプライバシーを最優先に設計されています。

- **ローカル保存がデフォルト**: 生成された音声ファイルは、デフォルト設定では**PC 内のフォルダ（ローカル）にのみ**保存されます。
- **クラウドへの自動アップロードなし**: ユーザーが意図して設定を変更しない限り、Dropbox や OneDrive などのクラウドストレージに勝手にファイルがアップロードされることはありません。
- **オプトイン方式の連携**: Dropbox などの自動保存機能を利用したい場合は、設定ファイル (`config.json` または `config.local.json`) で明示的に機能を有効（オプトイン）にする必要があります。

## 📦 必要要件

- **OS:** Windows (推奨) / macOS / Linux
- **Python:** 3.8 以上 ※EXE 版は Python インストール不要です（DL リンク） [![Download](https://img.shields.io/github/v/release/ohtori222/aivis-clipboard-reader?label=Download&style=for-the-badge&logo=windows)](https://github.com/ohtori222/aivis-clipboard-reader/releases/latest)
- **音声合成エンジン:** 以下のいずれかがローカルで起動していること
  - AivisSpeech (推奨)
  - VOICEVOX
- **(推奨) FFmpeg:** インストールしてパスを通しておくと、Opus 圧縮と画像埋め込み機能が有効になります。

> [!NOTE]
> 設定や使い方に関する詳細な情報は、配布物に含まれる `はじめにお読みください.txt` も併せてご確認ください。

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

3. **設定ファイルの準備（任意）**

   デフォルト設定で動作しますが、詳細設定を変更したい場合は `config.json` を修正してください。

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
   `assets` フォルダに `cover.jpg` (または `cover.png`) を置くと、生成される音声ファイルに埋め込まれます。

## ▶️ 使い方

### 🖥️ GUI 版 (推奨)

モダンなインターフェースで操作できる GUI 版です。

1.  AivisSpeech / VOICEVOX を起動します。
2.  スクリプトを実行します。
    ```bash
    python src/aivis_gui.py
    ```
3.  ウィンドウが表示されます。この状態でテキストを **コピー (Ctrl+C)** すると、自動で読み上げが始まります。
    - **Dashboard**: 再生状態の確認、一時停止、停止、スキップ操作が可能です。
    - **Log**: 読み上げ履歴を確認できます。
    - **Settings**: 速度や音量をリアルタイムに変更し、保存できます。

### ⌨️ CLI 版 (従来版)

コマンドラインだけで完結する軽量モードです。

1.  AivisSpeech / VOICEVOX を起動します。
2.  スクリプトを実行します。
    ```bash
    python src/aivis_reader.py
    ```
3.  読み上げたいテキストを **コピー (Ctrl+C)** すると、自動で読み上げが始まります。

### ⌨️ コマンドライン引数 (CLI/GUI 共通)

```bash
# 日付を指定して起動 (過去ログの整理などに便利)
# 保存先のフォルダ名とファイル名の日付部分が指定した値になります
python src/aivis_gui.py --date 251206

# 強制的にFLACで保存 (FFmpeg導入環境でもOpusを使わない場合)
python src/aivis_gui.py --flac
```

※ `aivis_reader.py` でも同じ引数が使えます。

### ⌨️ 操作コマンド (ホットキー)

作業中でも以下のキーで操作可能です（`config.json` で変更可能）。GUI 版/CLI 版共通です。

- **Ctrl + Alt + S**: **緊急停止** (再生を止め、予約キューを全て破棄します)
- **Ctrl + Alt + P**: **一時停止 / 再開**

## ⚙️ 設定 (config.json)

プロジェクトルートに `config.json` を置くことで設定を変更できます。
GUI 版では「Settings」タブから値を変更し、「Save Settings」を押すことで `config.local.json` に保存されます。

| キー          | 説明                                                 | デフォルト         |
| :------------ | :--------------------------------------------------- | :----------------- |
| `speaker_id`  | 使用するボイスの ID                                  | `888753760`        |
| `output_dir`  | 保存先フォルダ名                                     | `"Aivis_AudioLog"` |
| `use_dropbox` | Dropbox/OneDrive の自動検出を有効にする (true/false) | `false`            |
| `dropbox_dir` | Dropbox のルートパス (明示的に指定する場合)          | `null`             |
| `speed`       | 話速                                                 | `1.0`              |
| `force_flac`  | FFmpeg があっても Opus を使わず FLAC で保存する      | `false`            |
| `hotkeys`     | 操作キー割り当て                                     | (上記参照)         |

### 🔧 開発者向け: config.local.json

`config.local.json` というファイルを作成すると、`config.json` の設定を上書きできます。
このファイルは `.gitignore` に含まれているため、自分の環境専用のパスや設定を書いてもコミットされません。

GUI 版の「Settings」タブで保存すると、このファイルが自動生成・更新されます。

```json
{
  "dropbox_dir": "D:\\Personal\\Dropbox",
  "volume": 0.8
}
```

## 📦 EXE 化して利用する場合

Python 環境構築が面倒な場合、同梱の `build.bat` を実行することで、簡単に実行ファイル（`.exe`）を作成できます。

1.  以下のコマンドを実行します（Windows）。
    ```cmd
    .\scripts\build.bat
    ```
2.  `dist` フォルダに `AivisClipboardReader.exe` が生成されます。
3.  このファイルを実行するだけで、Python のインストールなしで利用可能です。
    ※ `cover.jpg` や `config.json` は exe と同じフォルダに置いてください。

## ⚠️ 免責事項 (Disclaimer)

1. **著作権について**:
   本ツールを使用して生成された音声データの利用は、個人の私的利用の範囲に留めてください。
   著作権者の許可なく、生成された音声をインターネット上で公開・配布することは法律で禁じられている場合があります。

2. **音声ライブラリの規約について**:
   使用する音声合成エンジン（AivisSpeech, VOICEVOX 等）および各キャラクターの利用規約を遵守してください。
   特に、公序良俗に反する内容や、各キャラクターが禁止している内容の生成・公開によるトラブルについて、開発者は一切の責任を負いません。

3. **セキュリティについて**:
   本ツールはクリップボードの内容を読み取りますが、外部サーバーへの送信は行いません（設定で意図的に連携した場合を除く）。
   ただし、本ツールの使用によって生じたいかなる損害についても、開発者は責任を負いかねます。

[MIT License](LICENSE)
