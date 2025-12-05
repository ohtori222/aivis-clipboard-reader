import sys
import time
import json
import os
import re
import queue
import threading
import datetime
import io
import numpy as np
import requests
import sounddevice as sd
import soundfile as sf
import pyperclip
import keyboard
import shutil
import subprocess
import base64

# FLACタグ編集用 (あれば使う)
try:
    from mutagen.flac import Picture
    from mutagen.id3 import PictureType
    from mutagen import File as MutagenFile

    HAS_MUTAGEN = True
except ImportError:
    HAS_MUTAGEN = False

# FFmpeg検出 (あればOpusエンコードに使用)
FFMPEG_PATH = shutil.which("ffmpeg")
HAS_FFMPEG = FFMPEG_PATH is not None

# バージョン情報
__version__ = "0.5.1"

# === グローバル変数・状態管理 ===
play_queue = queue.Queue()
stop_event = threading.Event()
is_paused = False
config = {}


# ─── 設定管理クラス ────────────────────────
class ConfigManager:
    DEFAULT_CONFIG = {
        "speaker_id": 888753760,
        "host": "127.0.0.1",
        "port": 10101,
        "output_dir": "Aivis_AudioLog",
        "dropbox_dir": None,
        "artwork_path": "cover.jpg",
        "volume": 1.0,
        "speed": 1.0,
        "pitch": 0.0,
        "intonation": 1.0,
        "post_pause": 0.3,
        "min_length": 10,
        "require_hiragana": True,
        "stop_command": ";;STOP",
        # ★変更: 設定をフラット化 (hotkeys廃止)
        "hotkey_stop": "ctrl+alt+s",
        "hotkey_pause": "ctrl+alt+p",
        # ★変更: 設定をフラット化 (tags廃止)
        "artist": "AivisReader",
        "album_prefix": "Log",
        "dictionary": {},
    }

    def __init__(self):
        self.data = self.DEFAULT_CONFIG.copy()
        self.load()

    def load(self):
        if os.path.exists("config.json"):
            try:
                with open("config.json", "r", encoding="utf-8") as f:
                    self._deep_update(self.data, json.load(f))
            except (OSError, json.JSONDecodeError) as e:
                print(f"⚠️ config.json 読み込みエラー: {e}")

        if os.path.exists("config.local.json"):
            try:
                with open("config.local.json", "r", encoding="utf-8") as f:
                    self._deep_update(self.data, json.load(f))
                    print("🔧 config.local.json を適用しました")
            except (OSError, json.JSONDecodeError) as e:
                print(f"⚠️ config.local.json 読み込みエラー: {e}")

    def _deep_update(self, base_dict, update_dict):
        for key, value in update_dict.items():
            if (
                isinstance(value, dict)
                and key in base_dict
                and isinstance(base_dict[key], dict)
            ):
                self._deep_update(base_dict[key], value)
            else:
                base_dict[key] = value

    def get(self, key, default=None):
        return self.data.get(key, default)

    def __getitem__(self, key):
        return self.data[key]


# グローバル設定インスタンス
cfg = ConfigManager()


# ─── プレーヤー (消費者スレッド) ────────────────
class AudioPlayer:
    def __init__(self):
        self.queue = queue.Queue()
        self.stop_flag = threading.Event()
        self.is_paused = False
        self.thread = threading.Thread(target=self._worker, daemon=True)
        self.thread.start()

    def _worker(self):
        while True:
            if self.stop_flag.is_set():
                with self.queue.mutex:
                    self.queue.queue.clear()
                self.stop_flag.clear()

            item = self.queue.get()
            if item is None:
                self.queue.task_done()
                continue
            data, sr = item

            while self.is_paused:
                if self.stop_flag.is_set():
                    break
                time.sleep(0.1)

            try:
                if not self.stop_flag.is_set():
                    sd.play(data, sr)
                    sd.wait()
            except Exception as e:
                print(f"⚠️ 再生エラー: {e}")
            finally:
                self.queue.task_done()

    def enqueue(self, data, sr):
        self.queue.put((data, sr))

    def stop_immediate(self):
        self.stop_flag.set()
        sd.stop()
        with self.queue.mutex:
            self.queue.queue.clear()
        self.queue.put(None)

    def toggle_pause(self):
        self.is_paused = not self.is_paused
        return self.is_paused


# ─── 合成器 (API通信 & 保存) ───────────────────
class AivisSynthesizer:
    def __init__(self):
        self.base_url = f"http://{cfg['host']}:{cfg['port']}"

    def check_connection(self):
        try:
            requests.get(f"{self.base_url}/speakers", timeout=2)
            return True
        except Exception:
            return False

    def synthesize(self, text):
        try:
            params = {"text": text, "speaker": cfg["speaker_id"]}
            q_res = requests.post(
                f"{self.base_url}/audio_query", params=params, timeout=5
            )
            q_res.raise_for_status()

            query = q_res.json()
            query["speedScale"] = cfg["speed"]
            query["intonationScale"] = cfg["intonation"]
            query["pitchScale"] = cfg["pitch"]
            query["volumeScale"] = cfg["volume"]
            query["postPhonemeLength"] = cfg["post_pause"]

            w_res = requests.post(
                f"{self.base_url}/synthesis",
                params={"speaker": cfg["speaker_id"]},
                json=query,
                headers={"Accept": "audio/wav"},
                timeout=30,
            )
            w_res.raise_for_status()

            return sf.read(io.BytesIO(w_res.content))
        except Exception as e:
            print(f"❌ APIエラー: {e}")
            return None

    def save_log(self, full_audio, sr, original_text):
        """FLAC/Opusで保存し、mutagenでタグ付けを行う"""

        use_opus = HAS_FFMPEG
        target_ext = ".opus" if use_opus else ".flac"

        root_path = cfg["dropbox_dir"]
        if not root_path:
            possible = [
                os.path.join(os.path.expanduser("~"), p)
                for p in ["Dropbox", "OneDrive"]
            ]
            for p in possible:
                if os.path.exists(p):
                    root_path = p
                    break
        if not root_path:
            root_path = os.getcwd()

        daily_date_str = datetime.datetime.now().strftime("%y%m%d")
        daily_save_dir = os.path.join(root_path, cfg["output_dir"], daily_date_str)
        os.makedirs(daily_save_dir, exist_ok=True)

        try:
            existing_files = [
                f
                for f in os.listdir(daily_save_dir)
                if f.endswith((".flac", ".ogg", ".opus"))
            ]
            track_number = len(existing_files) + 1
        except OSError as e:
            print(f"⚠️ ディレクトリ読み込みエラー ({daily_save_dir}): {e}")
            track_number = 1

        meta_title = re.sub(r"[^\w\u3002]", "", original_text)
        sentence_part = original_text.split("。")[0]
        clean_title = re.sub(r"[^\w]", "", sentence_part)[:20] or "NoTitle"

        timestamp = datetime.datetime.now().strftime("%y%m%d%H%M%S")
        filename = f"{timestamp}_{clean_title}{target_ext}"
        filepath = os.path.join(daily_save_dir, filename)

        try:
            if use_opus:
                # --- FFmpeg Opus保存処理 ---
                if full_audio.dtype != np.float32:
                    audio_input = full_audio.astype(np.float32)
                else:
                    audio_input = full_audio

                channels = 1 if audio_input.ndim == 1 else audio_input.shape[1]

                command = [
                    FFMPEG_PATH,
                    "-f",
                    "f32le",
                    "-ar",
                    str(sr),
                    "-ac",
                    str(channels),
                    "-i",
                    "pipe:0",
                    "-c:a",
                    "libopus",
                    "-b:a",
                    "128k",
                    "-vbr",
                    "on",
                    "-y",
                    filepath,
                ]

                process = subprocess.Popen(
                    command,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                )
                _, stderr = process.communicate(input=audio_input.tobytes())

                if process.returncode != 0:
                    err_msg = stderr.decode("utf-8", errors="ignore")
                    print(f"⚠️ FFmpegエラー詳細: {err_msg}")
                    raise Exception(f"FFmpeg failed (Code: {process.returncode})")
            else:
                with open(filepath, "wb") as f:
                    sf.write(f, full_audio, sr, format="FLAC")

            if HAS_MUTAGEN:
                audio = MutagenFile(filepath)

                if audio is None:
                    print(
                        "⚠️ タグ付け失敗: mutagenがファイル形式を認識できませんでした。"
                    )
                else:
                    current_date_str = datetime.datetime.now().strftime("%y%m%d")

                    # ★変更: フラット化された設定値を使用
                    audio["title"] = meta_title
                    audio["artist"] = cfg["artist"]
                    audio["album"] = f"{cfg['album_prefix']}_{current_date_str}"
                    audio["tracknumber"] = str(track_number)

                    artwork = cfg["artwork_path"]
                    if os.path.exists(artwork):
                        image = Picture()
                        image.type = PictureType.COVER_FRONT
                        if artwork.lower().endswith((".jpg", ".jpeg")):
                            image.mime = "image/jpeg"
                        else:
                            image.mime = "image/png"
                        with open(artwork, "rb") as f:
                            image.data = f.read()

                        if use_opus:
                            encoded_data = base64.b64encode(image.write()).decode(
                                "ascii"
                            )
                            audio["METADATA_BLOCK_PICTURE"] = [encoded_data]
                        else:
                            audio.add_picture(image)

                    audio.save()

            print(f"💾 [保存完了] {daily_date_str}/ No.{track_number} - {filename}")

        except Exception as e:
            print(f"⚠️ 保存失敗: {e}")
            if os.path.exists(filepath):
                try:
                    os.remove(filepath)
                except OSError:
                    pass


# ─── TaskManager クラス ──────────────────────────
class TaskManager:
    def __init__(self, synth, player):
        self.synth = synth
        self.player = player
        self.task_queue = queue.Queue()
        self.stop_current_flag = False

        self.thread = threading.Thread(target=self._worker, daemon=True)
        self.thread.start()

    def add_text(self, text):
        self.task_queue.put(text)
        q_size = self.task_queue.qsize()
        if q_size > 1:
            print(f"📥 キュー待機中: {q_size}件")

    def force_stop(self):
        self.stop_current_flag = True
        with self.task_queue.mutex:
            self.task_queue.queue.clear()
        self.task_queue
        self.player.stop_immediate()
        time.sleep(0.1)
        self.stop_current_flag = False

    def _clean_text(self, text):
        user_dict = cfg.get("dictionary", {})
        if user_dict:
            for k, v in user_dict.items():
                text = text.replace(k, v)

        text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
        text = re.sub(r"http\S+", "", text)
        text = re.sub(r"[-=]{2,}", "", text)
        text = re.sub(r"[#\*`>]", "", text)
        text = re.sub(r"!\[.*?\]\(.*?\)", "", text)
        text = re.sub(r"\[(.*?)\]\(.*?\)", r"\1", text)
        text = re.sub(r"[一-龠々]+\s*[（\(]([ぁ-んァ-ン]+)[）\)]", r"\1", text)

        text = re.sub(r"[ \t]+", " ", text)

        if cfg["require_hiragana"]:
            if not re.search(r"[ぁ-ん]", text):
                return None

        return text.strip()

    def _worker(self):
        while True:
            raw_text = self.task_queue.get()
            self.stop_current_flag = False

            cleaned_text = self._clean_text(raw_text)

            if not cleaned_text:
                self.task_queue.task_done()
                continue

            lines = [line.strip() for line in cleaned_text.splitlines() if line.strip()]

            total_len = sum(len(line) for line in lines)
            if total_len < cfg["min_length"]:
                self.task_queue.task_done()
                continue

            print(f"🎤 合成開始: {len(lines)}行 (Queue: {self.task_queue.qsize()})")

            audio_segments = []
            sample_rate = 0

            for i, line in enumerate(lines):
                if self.stop_current_flag:
                    print("⛔ タスク中断")
                    break

                print(f"  ├ 合成中 ({i + 1}/{len(lines)}): {line[:20]}...")

                res = self.synth.synthesize(line)
                if not res:
                    continue

                data, sr = res
                sample_rate = sr

                self.player.enqueue(data, sr)
                audio_segments.append(data)

            if audio_segments and not self.stop_current_flag:
                full_audio = np.concatenate(audio_segments)
                self.synth.save_log(full_audio, sample_rate, cleaned_text)

            self.task_queue.task_done()


# ─── メインループ ──────────────────────────
player = AudioPlayer()
synth = AivisSynthesizer()
manager = TaskManager(synth, player)


def on_stop_hotkey():
    manager.force_stop()


def on_pause_hotkey():
    player.toggle_pause()


def setup_hotkeys():
    try:
        # ★変更: フラット化された設定値を使用
        keyboard.add_hotkey(cfg["hotkey_stop"], on_stop_hotkey)
        keyboard.add_hotkey(cfg["hotkey_pause"], on_pause_hotkey)
    except Exception:
        pass


def main():
    print(f"✨ AivisSpeech Clipboard Reader v{__version__}")

    if HAS_FFMPEG:
        print("🔧 FFmpeg検出: Opus形式での保存を有効化します。")

    if not synth.check_connection():
        print(
            "❌ エラー: 音声サーバーに接続できません。起動確認とポート設定をお願いします。"
        )

    try:
        last_text = pyperclip.paste()
        print("🔇 起動時のクリップボード内容はスキップします。")
    except Exception:
        last_text = ""

    print(f"📋 監視中... (Min: {cfg['min_length']}文字)")
    setup_hotkeys()

    stop_cmd = cfg.get("stop_command", ";;STOP")

    try:
        while True:
            try:
                current_text = pyperclip.paste()
            except Exception:
                current_text = ""

            if current_text and current_text != last_text:
                last_text = current_text

                if current_text.strip() == stop_cmd:
                    on_stop_hotkey()
                    continue

                if current_text.strip():
                    print("\n📝 新着検知")
                    manager.add_text(current_text)

            time.sleep(0.5)

    except KeyboardInterrupt:
        print("\n👋 終了します")
        sys.exit(0)


if __name__ == "__main__":
    main()
