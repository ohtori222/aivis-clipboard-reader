import os

# ─── 接続・基本設定 ───────────────────────────────────
# AivisSpeech/VOICEVOXの接続先 (通常は127.0.0.1でOK)
HOST = '127.0.0.1'
PORT = '10101'
# 読み上げに使用する話者ID
SPEAKER_ID = 888753760 

# ─── 音声パラメータ ───────────────────────────────────
VOICE_SPEED = 1.0
VOICE_INTONATION = 1.9
VOICE_PITCH = 0.0
POST_PAUSE = 0.3

# ─── メタデータ・保存先設定 ───────────────────────────
# 【ユーザー名】FLACファイルに埋め込むアーティスト名
# 実行者が自由に設定する名前を想定 (例: Gemini, MyBot など)
ARTIST_NAME = "Aivis_Log_Source"
# アルバム名の接頭辞
ALBUM_PREFIX = "Log"
# ジャケット画像ファイルのパス
# ※このファイルがスクリプトと同じフォルダにある必要があります
ARTWORK_PATH = r"cover.jpg"

# 緊急停止コマンド（この文字列をコピーするとキューを全削除して止まる）
STOP_COMMAND = ";;STOP"

# ─── 保存ルートディレクトリの自動設定 ──────────────────
USER_HOME = os.path.expanduser("~")
DROPBOX_ROOT = os.path.join(USER_HOME, "Dropbox")

if os.path.exists(DROPBOX_ROOT):
    BASE_DIR = DROPBOX_ROOT
else:
    BASE_DIR = os.getcwd()

# 実際の保存ルート (YYMMDDフォルダは実行時に作成されます)
SAVE_DIR_ROOT = os.path.join(BASE_DIR, "Aivis_AudioLog")


# ─── ユーザー辞書 ───────────────────────────────────
# 頻繁に読み間違えられる単語やスラングを修正する辞書
USER_DICT = {
    # ─── 固有名詞・ITサービス ───
    "Gemini": "ジェミニ",
    "ChatGPT": "チャットジーピーティー",
    "Aivis": "アイビス",
    "Google": "グーグル",
    "YouTube": "ユーチューブ",
    "Amazon": "アマゾン",
    
    # ─── 略語・口語 ───
    "NG": "エヌジー",
    "OK": "オーケー",
    "GW": "ゴールデンウィーク",
    "MTG": "ミーティング",
    "PJ": "プロジェクト",
    "KPI": "ケーピーアイ",
    "Q&A": "キューアンドエー",
    "vs": "バーサス",
    "ver.": "バージョン",
    "vol.": "ボリューム",
    "No.": "ナンバー",
    "ID": "アイディー",
    
    # ─── 単位・記号 ───
    "cm": "センチ",
    "mm": "ミリ",
    "kg": "キロ",
    "km": "キロ",
    "fps": "エフピーエス",
    "Hz": "ヘルツ",
    "＆": "アンド",
    "&": "アンド",
    "％": "パーセント",
    "＋": "プラス",
    
    # ─── ファイル拡張子 ───
    ".exe": "エグゼ",
    ".jpg": "ジェイペグ",
    ".png": "ピング",
    ".pdf": "ピーディーエフ",
    ".txt": "テキスト",
    ".zip": "ジップ",
    
    # ─── 漢字の読ませ方補正 ───
    "日付": "ひづけ",
    "分間": "ふんかん",
}