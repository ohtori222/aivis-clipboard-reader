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
import argparse  # ★追加: 引数解析用

__version__ = "0.6.1"

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
        "hotkey_stop": "ctrl+alt+s",
        "hotkey_pause": "ctrl+alt+p",
        "artist": "AivisReader",
        "album_prefix": "Log",
        "dictionary": {},
        "force_flac": False,  # ★追加: デフォルト設定
    }

    def __init__(self):
        self.data = self.DEFAULT_CONFIG.copy()

        # デフォルトのアートワークが存在せず、サンプルがある場合はそちらを使用
        if not os.path.exists(self.data["artwork_path"]) and os.path.exists(
            "cover_sample.jpg"
        ):
            self.data["artwork_path"] = "cover_sample.jpg"

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

    def __setitem__(self, key, value):
        self.data[key] = value

    def save_to_local(self):
        """現在の設定の一部を config.local.json に保存する"""
        target_keys = [
            "speed",
            "volume",
            "pitch",
            "intonation",
            "host",
            "port",
            "speaker_id",
        ]
        save_data = {}

        # 既存の config.local.json があれば読み込んでマージする
        if os.path.exists("config.local.json"):
            try:
                with open("config.local.json", "r", encoding="utf-8") as f:
                    save_data = json.load(f)
            except:
                pass

        for key in target_keys:
            save_data[key] = self.data.get(key)

        try:
            with open("config.local.json", "w", encoding="utf-8") as f:
                json.dump(save_data, f, indent=2, ensure_ascii=False)
            print("💾 設定を config.local.json に保存しました")
        except Exception as e:
            print(f"⚠️ 設定保存エラー: {e}")


# グローバル設定インスタンス
cfg = ConfigManager()


# ─── プレーヤー (ストリーム再生・常時接続版) ────────────────
class AudioPlayer:
    def __init__(self):
        self.queue = queue.Queue()
        self.stop_flag = threading.Event()
        self.is_paused = False
        # ストリーム管理用
        self.stream = None
        self.current_sr = None

        self.thread = threading.Thread(target=self._worker, daemon=True)
        self.thread.start()

    def _worker(self):
        # アイドル時に流す無音チャンク（0.1秒分）
        silence_chunk = None

        while True:
            # 1. 停止フラグがあればキューを空にする
            if self.stop_flag.is_set():
                with self.queue.mutex:
                    self.queue.queue.clear()
                self.stop_flag.clear()

            # 2. キューからデータを取得
            try:
                item = self.queue.get(timeout=0.05)
            except queue.Empty:
                item = None

            # 3. データがある場合の処理
            if item is not None:
                data, sr = item

                # ストリームの初期化 or サンプリングレート変更時の再作成
                if self.stream is None or self.current_sr != sr:
                    if self.stream is not None:
                        self.stream.stop()
                        self.stream.close()

                    self.current_sr = sr
                    channels = 1 if data.ndim == 1 else data.shape[1]

                    try:
                        self.stream = sd.OutputStream(
                            samplerate=sr,
                            channels=channels,
                            dtype="float32",
                        )
                        self.stream.start()
                        # 無音チャンクもこのSRに合わせて作り直す
                        silence_chunk = np.zeros(
                            (int(sr * 0.1), channels), dtype=np.float32
                        )
                        if channels == 1:
                            silence_chunk = silence_chunk.flatten()

                        print(f"🔊 ストリーム開始: {sr}Hz / {channels}ch")
                    except Exception as e:
                        print(f"⚠️ ストリーム初期化エラー: {e}")
                        self.queue.task_done()
                        continue

                # 再生（書き込み）
                try:
                    while self.is_paused:
                        if self.stop_flag.is_set():
                            break
                        self.stream.write(silence_chunk)

                    if not self.stop_flag.is_set():
                        self.stream.write(data)

                except Exception as e:
                    print(f"⚠️ 再生書き込みエラー: {e}")
                finally:
                    self.queue.task_done()

            # 4. データがない（アイドル中）の場合
            else:
                if self.stream is not None and self.stream.active:
                    try:
                        self.stream.write(silence_chunk)
                    except Exception:
                        pass
                else:
                    pass

    def enqueue(self, data, sr):
        self.queue.put((data, sr))

    def stop_immediate(self):
        self.stop_flag.set()
        with self.queue.mutex:
            self.queue.queue.clear()

    def toggle_pause(self):
        self.is_paused = not self.is_paused
        return self.is_paused


# ─── 合成器 (API通信 & 保存) ───────────────────
class AivisSynthesizer:
    def __init__(self):
        self.base_url = f"http://{cfg['host']}:{cfg['port']}"
        self.force_flac = False  # デフォルトはFalseだが、main()で上書きされる可能性あり

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

            data, sr = sf.read(io.BytesIO(w_res.content), dtype="float32")

            # --- クリックノイズ対策 (フェード処理) ---
            fade_duration = 0.03
            fade_len = int(sr * fade_duration)

            if len(data) > fade_len * 2:
                fade_in_curve = np.linspace(0.0, 1.0, fade_len, dtype=np.float32)

                if data.ndim == 1:
                    data[:fade_len] *= fade_in_curve
                    data[-fade_len:] *= fade_in_curve[::-1]
                else:
                    data[:fade_len] *= fade_in_curve[:, np.newaxis]
                    data[-fade_len:] *= fade_in_curve[::-1][:, np.newaxis]
            # ---------------------------------------

            return data, sr

        except Exception as e:
            print(f"❌ APIエラー: {e}")
            return None

    def save_log(self, full_audio, sr, original_text):
        """FLAC/Opusで保存し、mutagenでタグ付けを行う"""

        # ★変更: 引数 or 設定でFLAC強制が指定されている場合は、Opusを使わない
        use_opus = HAS_FFMPEG and not self.force_flac
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

        # ★日付オーバーライド確認
        override_date = cfg.get("override_date")
        if override_date:
            daily_date_str = override_date
        else:
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

        if override_date:
            # 時刻だけ現在のものを使う
            current_time_str = datetime.datetime.now().strftime("%H%M%S")
            timestamp = f"{override_date}{current_time_str}"
        else:
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
                    if override_date:
                        current_date_str = override_date
                    else:
                        current_date_str = datetime.datetime.now().strftime("%y%m%d")

                    audio["title"] = meta_title
                    audio["artist"] = cfg["artist"]
                    audio["album"] = f"{cfg['album_prefix']}_{current_date_str}"
                    audio["tracknumber"] = str(track_number)

                    artwork = cfg["artwork_path"]
                    if os.path.exists(artwork):
                        image = Picture()
                        # ★修正: Enumではなく整数値(3=Cover Front)を明示的に設定
                        image.type = 3
                        # ★修正: Descriptionを明示 (一部プレーヤー対策)
                        image.desc = "Cover"

                        if artwork.lower().endswith((".jpg", ".jpeg")):
                            image.mime = "image/jpeg"
                        else:
                            image.mime = "image/png"

                        with open(artwork, "rb") as f:
                            image.data = f.read()

                        if use_opus:
                            # Opus (Ogg) の場合は METADATA_BLOCK_PICTURE タグとして
                            # Base64エンコードしたFLAC画像ブロック構造体を書き込む
                            image_data = image.write()
                            encoded_data = base64.b64encode(image_data).decode("ascii")
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
        self.player.stop_immediate()
        time.sleep(0.1)
        self.stop_current_flag = False

    def skip_current(self):
        """現在の読み上げのみ中断し、次はそのまま続ける"""
        self.stop_current_flag = True
        self.player.stop_immediate()
        # キューはクリアしない
        # stop_current_flagにより_workerループ内の合成/再生がbreakされる

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

# ─── メインループ ──────────────────────────


def run_cli():
    # ★追加: コマンドライン引数解析
    parser = argparse.ArgumentParser(description="AivisSpeech Clipboard Reader")
    parser.add_argument(
        "-f",
        "--flac",
        action="store_true",
        help="強制的にFLAC形式で保存します (FFmpegがある場合でも)",
    )
    # ★追加: 日付上書きオプション
    parser.add_argument(
        "-d",
        "--date",
        type=str,
        help="保存時の日付を強制的に指定します (形式: YYMMDD, 例: 251206)",
    )
    args = parser.parse_args()

    # 日付オプションのバリデーション
    if args.date:
        if not re.match(r"^\d{6}$", args.date):
            print(
                "❌ エラー: 日付形式が正しくありません。YYMMDD形式 (6桁の数字) で指定してください。"
            )
            sys.exit(1)
        cfg["override_date"] = args.date
        print(f"📅 日付上書きモード: {args.date} として保存します")

    # インスタンス生成
    player = AudioPlayer()
    synth = AivisSynthesizer()
    manager = TaskManager(synth, player)

    # ホットキー関数 (クロージャとして定義)
    def on_stop_hotkey():
        manager.force_stop()

    def on_pause_hotkey():
        player.toggle_pause()

    def setup_hotkeys():
        try:
            keyboard.add_hotkey(cfg["hotkey_stop"], on_stop_hotkey)
            keyboard.add_hotkey(cfg["hotkey_pause"], on_pause_hotkey)
        except Exception:
            pass

    # ★変更: 設定ファイルの値 または コマンドライン引数 のどちらかがTrueなら有効にする
    cfg_force_flac = cfg.get("force_flac", False)

    if args.flac or cfg_force_flac:
        synth.force_flac = True
        if args.flac:
            print("🔧 オプション指定: 強制的にFLACで保存します。")
        else:
            print("🔧 設定ファイル指定: デフォルト設定によりFLACで保存します。")

    print(f"✨ AivisSpeech Clipboard Reader v{__version__}")

    if HAS_FFMPEG:
        if synth.force_flac:
            print(
                "🔧 FFmpeg検出済みですが、設定またはオプションによりFLAC保存を行います。"
            )
        else:
            print("🔧 FFmpeg検出: Opus形式での保存を有効化します。")
    else:
        print("ℹ️ FFmpeg未検出: FLAC形式で保存します。")

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
    run_cli()
