"""
AivisSpeech Clipboard Reader
=========================================
クリップボードを監視し、AivisSpeech (または VOICEVOX) を使用して読み上げるツールです。

Features:
- クリップボードのリアルタイム監視
- ストリーミング再生（合成しながら再生）
- 連続コピー時の順次キューイング処理
- 音声ファイル(FLAC)の自動保存とタグ付け
- 誤爆防止フィルター（文字数・ひらがなチェック）
- 緊急停止機能

Author: Unadorned Ohtori
License: MIT
"""

import time
import pyperclip
import requests
import sounddevice as sd
import soundfile as sf
import io
import re
import os
import sys
from datetime import datetime
import numpy as np
from threading import Thread, Event
import queue
from typing import Optional, Tuple, List

# ─── 設定ファイルの読み込み ────────────────────────
try:
    import settings
except ImportError:
    print("❌ エラー: 設定ファイル (settings.py) が見つかりません。")
    print("👉 settings_template.py をコピーして settings.py を作成し、環境に合わせて編集してください。")
    sys.exit(1)

# ─── ライブラリ依存チェック ────────────────────────
try:
    from mutagen.flac import FLAC, Picture
    from mutagen.id3 import PictureType
    HAS_MUTAGEN = True
except ImportError:
    HAS_MUTAGEN = False
    print("⚠️ 注意: 'mutagen' ライブラリが見つかりません。タグとアートワークの埋め込みはスキップされます。")

# ─── Configクラス（settings.pyのラッパー） ──────────
class Config:
    """
    アプリケーション全体の設定を管理するクラス。
    settings.py の値を参照し、未定義の場合はデフォルト値を提供します。
    """
    # 接続設定
    HOST = settings.HOST
    PORT = settings.PORT
    SPEAKER_ID = settings.SPEAKER_ID
    
    # 音声パラメータ
    VOICE_SPEED = settings.VOICE_SPEED
    VOICE_INTONATION = settings.VOICE_INTONATION
    VOICE_PITCH = settings.VOICE_PITCH
    POST_PAUSE = settings.POST_PAUSE

    # 保存先設定
    SAVE_DIR_ROOT = settings.SAVE_DIR_ROOT
    CHECK_INTERVAL = 0.5
    
    # メタデータ設定
    ARTIST_NAME = settings.ARTIST_NAME
    ALBUM_PREFIX = settings.ALBUM_PREFIX
    ARTWORK_PATH = settings.ARTWORK_PATH

    # 辞書・コマンド
    USER_DICT = settings.USER_DICT
    STOP_COMMAND = getattr(settings, 'STOP_COMMAND', ';;STOP')

    # 誤爆防止フィルター（設定がない場合のデフォルト値も設定）
    MIN_LENGTH = getattr(settings, 'MIN_LENGTH', 10)
    REQUIRE_HIRAGANA = getattr(settings, 'REQUIRE_HIRAGANA', True)

# ─── AudioPlayer クラス ────────────────────────────
class AudioPlayer:
    def __init__(self):
        self.queue: queue.Queue = queue.Queue()
        self.thread = Thread(target=self._playback_worker, daemon=True)
        self.thread.start()

    def _playback_worker(self):
        while True:
            item = self.queue.get()
            if item is None: break
            
            data, sr = item
            try:
                sd.play(data, sr)
                sd.wait()
            except Exception as e:
                print(f"⚠️ 再生エラー: {e}")
            finally:
                self.queue.task_done()

    def enqueue(self, data: np.ndarray, sr: int):
        self.queue.put((data, sr))

    def stop_and_clear(self):
        sd.stop()
        with self.queue.mutex:
            self.queue.queue.clear()

# ─── AivisSynthesizer クラス ───────────────────────
class AivisSynthesizer:
    def __init__(self, config):
        self.cfg = config
        self.base_url = f'http://{self.cfg.HOST}:{self.cfg.PORT}'
        os.makedirs(self.cfg.SAVE_DIR_ROOT, exist_ok=True)
        self.session = requests.Session()

    def check_connection(self) -> bool:
        try:
            self.session.get(f'{self.base_url}/speakers', timeout=2)
            return True
        except:
            return False

    def synthesize_segment(self, text: str) -> Optional[Tuple[np.ndarray, int]]:
        try:
            q_res = self.session.post(
                f'{self.base_url}/audio_query',
                params={'text': text, 'speaker': self.cfg.SPEAKER_ID},
                timeout=10
            )
            if q_res.status_code != 200: return None
            
            query = q_res.json()
            query['speedScale'] = self.cfg.VOICE_SPEED
            query['intonationScale'] = self.cfg.VOICE_INTONATION
            query['pitchScale'] = self.cfg.VOICE_PITCH

            w_res = self.session.post(
                f'{self.base_url}/synthesis',
                params={'speaker': self.cfg.SPEAKER_ID},
                json=query,
                headers={'Accept': 'audio/wav'},
                timeout=30
            )
            if w_res.status_code != 200: return None
            
            return sf.read(io.BytesIO(w_res.content))
        except Exception:
            return None

    def save_merged(self, segments: List[np.ndarray], original_text: str, sr: int):
        if not segments: return
        full_audio = np.concatenate(segments)
        
        today_str = datetime.now().strftime('%y%m%d')
        daily_save_dir = os.path.join(self.cfg.SAVE_DIR_ROOT, today_str)
        os.makedirs(daily_save_dir, exist_ok=True)

        # タイトル生成（改行対策）
        lines = [line.strip() for line in original_text.splitlines() if line.strip()]
        if lines and (lines[0].startswith('（') or lines[0].startswith('(')):
            title_source = "".join(lines[1:])
        else:
            title_source = "".join(lines)
        if not title_source: title_source = "NoTitle"

        meta_title = re.sub(r'[^\w\u3002]', '', title_source)
        sentence_part = title_source.split('。')[0]
        clean_title = re.sub(r'[^\w]', '', sentence_part)[:20] or "NoTitle"

        try:
            existing_files = [f for f in os.listdir(daily_save_dir) if f.endswith('.flac')]
            track_number = len(existing_files) + 1
        except Exception:
            track_number = 1

        timestamp = datetime.now().strftime('%y%m%d%H%M')
        filename = f"{timestamp}_{clean_title}.flac" 
        path = os.path.join(daily_save_dir, filename)

        try:
            sf.write(path, full_audio, sr, format='FLAC', subtype='PCM_16')
            
            if HAS_MUTAGEN:
                self._add_metadata(path, meta_title, track_number)
                
            print(f"💾 [保存完了] {today_str}/ No.{track_number} - {filename}")
        except Exception as e:
            print(f"⚠️ 保存失敗: {e}")

    def _add_metadata(self, filepath: str, meta_title_text: str, track_num: int):
        try:
            audio = FLAC(filepath)
            
            current_date_str = datetime.now().strftime('%y%m%d')
            album_name = f"{self.cfg.ALBUM_PREFIX}_{current_date_str}"
            
            audio['artist'] = self.cfg.ARTIST_NAME
            audio['album'] = album_name
            audio['title'] = meta_title_text
            audio['tracknumber'] = str(track_num)
            
            if os.path.exists(self.cfg.ARTWORK_PATH):
                image = Picture()
                image.type = PictureType.COVER_FRONT
                if self.cfg.ARTWORK_PATH.lower().endswith(('.jpg', '.jpeg')):
                    image.mime = u"image/jpeg"
                else:
                    image.mime = u"image/png"
                with open(self.cfg.ARTWORK_PATH, 'rb') as f:
                    image.data = f.read()
                audio.add_picture(image)
            audio.save()
        except Exception as e:
            print(f"⚠️ タグ書き込みエラー: {e}")

# ─── TaskManager クラス ──────────────────────────
class TaskManager:
    def __init__(self, synth: AivisSynthesizer, player: AudioPlayer):
        self.synth = synth
        self.player = player
        self.task_queue: queue.Queue = queue.Queue()
        self.abort_current_flag = Event()
        self.thread = Thread(target=self._worker, daemon=True)
        self.thread.start()
        
        self.re_ruby = re.compile(r'([一-龠]+)[（\(]([ぁ-んァ-ンー]+)[）\)]')
        self.re_noise = re.compile(r'[{}#`|>[\]]')
        self.re_symbols = re.compile(r'[\*=\-]{2,}')
        self.re_url = re.compile(r'https?://[\w/:%#\$&\?\(\)~\.=\+\-]+')

    def add_text(self, text: str):
        self.task_queue.put(text)
        q_size = self.task_queue.qsize()
        if q_size > 1:
            print(f"📥 キューに追加しました (待機中: {q_size - 1}件)")

    def force_stop_all(self):
        print("🛑 【緊急停止】キューを全削除し、再生を停止します")
        with self.task_queue.mutex:
            self.task_queue.queue.clear()
        self.abort_current_flag.set()
        self.player.stop_and_clear()

    def _sanitize_text(self, text: str) -> str:
        text = self.re_ruby.sub(r'\2', text)
        for word, yomi in Config.USER_DICT.items():
            text = text.replace(word, yomi)
        text = self.re_noise.sub('', text)
        text = self.re_symbols.sub('', text)
        text = self.re_url.sub('', text)
        return text

    def _worker(self):
        while True:
            text = self.task_queue.get()
            self.abort_current_flag.clear()

            clean_text = self._sanitize_text(text)
            lines = [line.strip() for line in clean_text.splitlines() if line.strip()]

            if lines:
                print(f"🎤 合成開始: {len(lines)}行 (残りタスク: {self.task_queue.qsize()})")
                all_segments = []
                sample_rate = 44100

                for i, line in enumerate(lines):
                    if self.abort_current_flag.is_set():
                        print("⛔ タスク中断")
                        break

                    print(f"  ├ 合成中 ({i+1}/{len(lines)}): {line[:15]}...")
                    res = self.synth.synthesize_segment(line)
                    if not res: continue
                    data, sr = res
                    sample_rate = sr

                    self.player.enqueue(data, sr)
                    all_segments.append(data)

                    if Config.POST_PAUSE > 0 and i < len(lines) - 1:
                        silence = np.zeros(int(sr * Config.POST_PAUSE), dtype=data.dtype)
                        self.player.enqueue(silence, sr)
                        all_segments.append(silence)

                if not self.abort_current_flag.is_set() and all_segments:
                    self.synth.save_merged(all_segments, text, sample_rate)
            
            self.task_queue.task_done()

# ─── メインエントリーポイント ──────────────────────
def main():
    print("── AivisSpeech Reader v0.2.0 (Filter Enabled) ──")
    print(f"📂 保存先: {Config.SAVE_DIR_ROOT}")
    print(f"🎵 Artist: {Config.ARTIST_NAME}")
    print(f"🛑 緊急停止: '{Config.STOP_COMMAND}'")
    if Config.REQUIRE_HIRAGANA:
        print("🛡️ 誤爆防止フィルター: 有効 (ひらがな必須)")
    print("──────────────────────────────────────────")
    
    player = AudioPlayer()
    synth = AivisSynthesizer(Config)
    manager = TaskManager(synth, player)

    if not synth.check_connection():
        print("⚠️ エラー: AivisSpeech/VOICEVOXに接続できません。")
        print("   アプリケーションが起動しているか、ポート番号(settings.py)を確認してください。")

    try:
        last_text = pyperclip.paste()
        print("🔇 起動時のクリップボード内容はスキップします。")
    except:
        last_text = ""
    
    print("📋 クリップボード監視を開始します...")

    try:
        while True:
            try:
                text = pyperclip.paste()
            except:
                text = ""

            # ─── 誤爆防止フィルター ───
            # 1. 短すぎるテキストの無視
            if len(text) < Config.MIN_LENGTH:
                # 短いテキストも履歴更新だけは行い、無限ループを防ぐ
                if text != last_text:
                    # print(f"ℹ️ スキップ: 文字数が短すぎます ({len(text)}文字)")
                    last_text = text
                time.sleep(Config.CHECK_INTERVAL)
                continue

            # 2. 日本語（ひらがな）チェック
            if Config.REQUIRE_HIRAGANA and not re.search(r'[ぁ-ん]', text):
                if text != last_text:
                    # print("ℹ️ スキップ: ひらがなが含まれていません")
                    last_text = text
                time.sleep(Config.CHECK_INTERVAL)
                continue
            # ────────────────────────

            if text and text != last_text and text.strip():
                last_text = text
                
                if text.strip() == Config.STOP_COMMAND:
                    manager.force_stop_all()
                else:
                    print(f"\n📝 新着検知: {len(text)}文字 -> キューに追加")
                    manager.add_text(text)

            time.sleep(Config.CHECK_INTERVAL)

    except KeyboardInterrupt:
        print("\n👋 アプリケーションを終了します。")
        manager.force_stop_all()
        sys.exit()

if __name__ == "__main__":
    main()