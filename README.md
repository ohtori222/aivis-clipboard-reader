# AivisSpeech Clipboard Reader

クリップボードにコピーされたテキストをリアルタイムで検知し、**AivisSpeech** (または VOICEVOX) を使用して読み上げるPythonツールです。
「Web記事のながら聴き」や「AIチャットのログ音声化」に最適化されています。

## ✨ 特徴

* **⚡ ストリーミング再生 & 順次キューイング**
    * 合成処理と再生処理を並列化。長文でも待ち時間なく再生が始まります。
    * 連続してテキストをコピーしても、自動的に「予約リスト（キュー）」に入り、順番に読み上げられます。
* **🧹 高度なテキストクリーニング**
    * 読み上げに不要な Markdown記号（`#`, `*`, ` ``` ` 等）、URL、飾り文字を自動で除去します。
    * ルビ（例：`漢（おとこ）`）を認識し、自動的に読み仮名のみを発音させる機能を搭載。
* **📂 高機能なログ保存**
    * 読み上げた音声は FLAC形式 で自動保存されます。
    * ファイル名は「日付 + タイトル（2行目から抽出）」で自動生成され、視認性が抜群です。
    * **日次フォルダ**（例: `251203/`）を自動作成し、大量のファイルもスッキリ整理されます。
* **🎵 メタデータ & アートワーク埋め込み**
    * FLACタグに「アーティスト名」「アルバム名（日付連動）」「トラック番号」を自動付与。
    * 指定したジャケット画像（カバーアート）を埋め込むことができ、音楽プレイヤーでの見栄えが良くなります。

## 📦 必要要件

* **OS:** Windows / macOS / Linux
* **Python:** 3.8 以上
* **音声合成エンジン:** 以下のいずれかがローカルで起動していること
    * AivisSpeech (推奨/動作確認済み)
    * VOICEVOX (VOICEVOX互換APIを使用しているため動作する見込みですが、作者による直接の動作確認は行っていません)

## 🚀 インストール

1.  **リポジトリのクローン**
    ```bash
    git clone https://github.com/あなたのユーザー名/aivis-clipboard-reader.git
    cd aivis-clipboard-reader
    ```

2.  **依存ライブラリのインストール**
    ```bash
    # 仮想環境を作成
    python -m venv .venv

    # 仮想環境を有効化 (Windowsの場合)
    .\.venv\Scripts\activate

    # 仮想環境を有効化 (macOS/Linuxの場合)
    source .venv/bin/activate

    # 依存ライブラリのインストール
    pip install -r requirements.txt
    ```

3.  **設定ファイルの準備**
    テンプレートをコピーして、設定ファイルを作成します。
    ```bash
    # Windows (PowerShell)の場合
    Copy-Item settings_template.py settings.py
    
    # macOS / Linux の場合
    cp settings_template.py settings.py
    ```

4.  **アートワークの準備（任意）**
    スクリプトと同じフォルダに `cover.jpg` という名前で好きな画像を置いておくと、生成される音声ファイルに埋め込まれます。

## ⚙️ 設定 (settings.py)

### 🎙️ 話者IDの確認方法

`settings.py` の **`SPEAKER_ID`** を設定するために、以下の補助スクリプトを実行してください。

1.  **AivisSpeech/VOICEVOX を起動**します。
2.  ターミナルで以下を実行します。
    ```bash
    python aivis_search_id.py
    ```
3.  出力されたリストから、使用したいキャラクターのIDをコピーし、`settings.py` の `SPEAKER_ID` に貼り付けてください。

作成した `settings.py` をテキストエディタで開き、環境に合わせて編集してください。

| 項目 | 説明 | デフォルト例 |
| :--- | :--- | :--- |
| **`SPEAKER_ID`** | 使用したいボイスのID（上記で確認） | `888753760` |
| `ARTIST_NAME` | 音声ファイルのタグに記録されるアーティスト名 | `"MyAI"` |
| `ALBUM_PREFIX` | アルバム名の接頭辞（`Log_251203`のようになります） | `"Log"` |
| `DROPBOX_ROOT` | Dropboxフォルダのパス（自動検出しますが手動指定も可） | 自動検出 |
| `USER_DICT` | 読み間違いを修正する単語辞書 | (コード内参照) |

## ▶️ 使い方

アプリケーションの実行は、必ず仮想環境を有効化した状態で行ってください。

1.  **仮想環境の有効化**
    VS Codeを再起動したり、新しいターミナルを開いたりした際は、まず以下のコマンドで仮想環境を有効化してください。

    * **Windows (PowerShell)**:
        ```bash
        .\.venv\Scripts\activate
        ```

    * **macOS / Linux**:
        ```bash
        source .venv/bin/activate
        ```

2.  **AivisSpeech/VOICEVOX を起動**します。

3.  **スクリプトを実行**します。
    ```bash
    python aivis_reader.py
    ```

4.  読み上げさせたいテキストを **クリップボードにコピー（Ctrl+C）** してください。

5.  コンソールに「📝 新着検知」と表示され、読み上げと保存が始まります。

### 🛑 緊急停止コマンド
停止・終了方法は以下の2パターン存在します。

* **通常終了 (Graceful Shutdown):**
    * ターミナル上で **`Ctrl` + `C`** (macOS の場合は **`Cmd` + `C`**) を押してください。プログラムが進行中のタスクを停止し、安全に終了します。

* **緊急停止コマンド:**
    * 読み上げ予約（キュー）をすべて破棄して、即座に停止したい場合は、以下の文字列をコピーしてください。
    ```text
    ;;STOP
    ```
    ※ このコマンド文字列は `settings.py` の `STOP_COMMAND` で変更可能です。

## 📂 出力ファイル構成

デフォルトでは、Dropboxフォルダ内の `Aivis_AudioLog` に保存されます。

```text
Dropbox/
  └── Aivis_AudioLog/
       ├── 251203/                <-- 日付フォルダ(YYMMDD)
       │    ├── 2512031000_タイトルA.flac  (Track 1)
       │    ├── 2512031005_タイトルB.flac  (Track 2)
       │    └── ...
       ├── 251204/
       │    └── ...
```
## 📝 注意事項

  * **起動時のスキップ機能:** アプリ起動時にクリップボードに残っていたテキストは、意図しない読み上げを防ぐためスキップされます。
  * **音声が出ない場合:**
      * AivisSpeech/VOICEVOXが起動しているか確認してください。
      * `settings.py` の `HOST` と `PORT` が正しいか確認してください。

## 📜 License

[MIT License](https://www.google.com/search?q=LICENSE)