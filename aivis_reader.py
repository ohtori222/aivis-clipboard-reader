"""
AivisSpeech Clipboard Reader
=========================================
クリップボードを監視し、AivisSpeech (VOICEVOX互換) で読み上げるツールです。

Features:
- クリップボードのリアルタイム監視
- ストリーミング再生（合成しながら再生）
- 連続コピー時の順次キューイング処理
- 音声ファイル(FLAC)の自動保存とタグ付け
- 緊急停止機能

Author: NeNe Project
License: MIT (Recommended)
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
    # 接続確認用のURLなどを先に構築
    BASE_URL = f'http://{settings.HOST}:{settings.PORT}'
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
    print("   (pip install mutagen でインストール可能です)")

# ─── Configクラス（settings.pyのラッパー） ──────────
class Config:
    """
    アプリケーション全体の設定を管理するクラスです。
    基本的には settings.py の値を参照します。
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
    CHECK_INTERVAL = 0.5  # クリップボード監視間隔(秒)
    
    # メタデータ設定
    ARTIST_NAME = settings.ARTIST_NAME
    ALBUM_PREFIX = settings.ALBUM_PREFIX
    ARTWORK_PATH = settings.ARTWORK_PATH

    # 辞書・コマンド
    USER_DICT = settings.USER_DICT
    STOP_COMMAND = ";;STOP"  # この文字列をコピーすると緊急停止

# ─── AudioPlayer クラス ────────────────────────────
class AudioPlayer:
    """
    音声データの再生を管理するクラス。
    別スレッドで動作し、キューに入った音声データを順次再生します。
    """
    def __init__(self):
        self.queue: queue.Queue = queue.Queue()
        self.thread = Thread(target=self._playback_worker, daemon=True)
        self.thread.start()

    def _playback_worker(self):
        """再生ループ（デーモンスレッド）"""
        while True:
            item = self.queue.get()
            if item is None: break
            
            data, sr = item
            try:
                sd.play(data, sr)
                sd.wait() # 再生終了を待機
            except Exception as e:
                print(f"⚠️ 再生エラー: {e}")
            finally:
                self.queue.task_done()

    def enqueue(self, data: np.ndarray, sr: int):
        """再生キューに音声データを追加"""
        self.queue.put((data, sr))

    def stop_and_clear(self):
        """再生を即時停止し、待機中のキューを破棄"""
        sd.stop()
        with self.queue.mutex:
            self.queue.queue.clear()

# ─── AivisSynthesizer クラス ───────────────────────
class AivisSynthesizer:
    """
    音声合成エンジンとの通信およびファイル保存を担当するクラス。
    """
    def __init__(self, config):
        self.cfg = config
        self.base_url = f'http://{self.cfg.HOST}:{self.cfg.PORT}'
        
        # 保存ルートフォルダの作成
        os.makedirs(self.cfg.SAVE_DIR_ROOT, exist_ok=True)
        
        # 通信セッションの作成（Keep-Aliveによる高速化）
        self.session = requests.Session()

    def check_connection(self) -> bool:
        """エンジンの稼働確認"""
        try:
            self.session.get(f'{self.base_url}/speakers', timeout=2)
            return True
        except:
            return False

    def synthesize_segment(self, text: str) -> Optional[Tuple[np.ndarray, int]]:
        """
        1文ごとの音声合成を実行します。
        Returns: (音声データ, サンプリングレート) または None
        """
        try:
            # 1. Query作成
            q_res = self.session.post(
                f'{self.base_url}/audio_query',
                params={'text': text, 'speaker': self.cfg.SPEAKER_ID},
                timeout=10
            )
            if q_res.status_code != 200: return None
            
            query = q_res.json()
            # パラメータ適用
            query['speedScale'] = self.cfg.VOICE_SPEED
            query['intonationScale'] = self.cfg.VOICE_INTONATION
            query['pitchScale'] = self.cfg.VOICE_PITCH

            # 2. 音声合成
            w_res = self.session.post(
                f'{self.base_url}/synthesis',
                params={'speaker': self.cfg.SPEAKER_ID},
                json=query,
                headers={'Accept': 'audio/wav'},
                timeout=30
            )
            if w_res.status_code != 200: return None
            
            # バイナリを読み込み
            return sf.read(io.BytesIO(w_res.content))
        except Exception:
            return None

    def save_merged(self, segments: List[np.ndarray], original_text: str, sr: int):
        """
        分割して合成された音声を結合し、ファイルとして保存します。
        """
        if not segments: return
        full_audio = np.concatenate(segments)
        
        # 日付フォルダの準備 (例: .../251203/)
        today_str = datetime.now().strftime('%y%m%d')
        daily_save_dir = os.path.join(self.cfg.SAVE_DIR_ROOT, today_str)
        os.makedirs(daily_save_dir, exist_ok=True)

        # ── タイトル生成ロジック ──
        # 2行目以降を結合してタイトルソースとする（改行対策）
        lines = [line.strip() for line in original_text.splitlines() if line.strip()]
        if lines and (lines[0].startswith('（') or lines[0].startswith('(')):
             # ト書きで始まる場合は2行目から
            title_source = "".join(lines[1:])
        else:
            title_source = "".join(lines)
        if not title_source: title_source = "NoTitle"

        # タグ用タイトル（記号削除のみ）
        meta_title = re.sub(r'[^\w\u3002]', '', title_source)

        # ファイル名用タイトル（最初の句点まで + 記号全削除 + 20文字制限）
        sentence_part = title_source.split('。')[0]
        clean_title = re.sub(r'[^\w]', '', sentence_part)[:20] or "NoTitle"

        # トラック番号の自動算出
        try:
            existing_files = [f for f in os.listdir(daily_save_dir) if f.endswith('.flac')]
            track_number = len(existing_files) + 1
        except Exception:
            track_number = 1

        # 保存実行
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
        """FLACファイルへのタグ書き込みとアートワーク埋め込み"""
        try:
            audio = FLAC(filepath)
            
            # アルバム名 (例: Log_251203)
            current_date_str = datetime.now().strftime('%y%m%d')
            album_name = f"{self.cfg.ALBUM_PREFIX}_{current_date_str}"
            
            audio['artist'] = self.cfg.ARTIST_NAME
            audio['album'] = album_name
            audio['title'] = meta_title_text
            audio['tracknumber'] = str(track_num)
            
            # ジャケット画像の埋め込み
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
    """
    読み上げタスクのキュー管理とテキスト処理を行うクラス。
    """
    def __init__(self, synth: AivisSynthesizer, player: AudioPlayer):
        self.synth = synth
        self.player = player
        self.task_queue: queue.Queue = queue.Queue()
        self.abort_current_flag = Event()
        
        # ワーカースレッドの開始
        self.thread = Thread(target=self._worker, daemon=True)
        self.thread.start()
        
        # 正規表現の事前コンパイル（高速化）
        # ルビ削除、Markdown記号削除、URL削除など
        self.re_ruby = re.compile(r'([一-龠]+)[（\(]([ぁ-んァ-ンー]+)[）\)]')
        self.re_noise = re.compile(r'[{}#`|>[\]]')
        self.re_symbols = re.compile(r'[\*=\-]{2,}')
        self.re_url = re.compile(r'https?://[\w/:%#\$&\?\(\)~\.=\+\-]+')

    def add_text(self, text: str):
        """テキストを処理キューに追加します"""
        self.task_queue.put(text)
        q_size = self.task_queue.qsize()
        if q_size > 1:
            print(f"📥 キューに追加しました (待機中: {q_size - 1}件)")

    def force_stop_all(self):
        """緊急停止：全てのキューを破棄し、再生を停止します"""
        print("🛑 【緊急停止】キューを全削除し、再生を停止します")
        with self.task_queue.mutex:
            self.task_queue.queue.clear()
        self.abort_current_flag.set()
        self.player.stop_and_clear()

    def _sanitize_text(self, text: str) -> str:
        """テキストのクリーニング処理"""
        # 1. ルビをひらがなに置換
        text = self.re_ruby.sub(r'\2', text)
        
        # 2. ユーザー辞書による置換
        for word, yomi in Config.USER_DICT.items():
            text = text.replace(word, yomi)
            
        # 3. 不要な記号・URLの削除
        text = self.re_noise.sub('', text)
        text = self.re_symbols.sub('', text)
        text = self.re_url.sub('', text)
        
        return text

    def _worker(self):
        """バックグラウンドでテキストを順次処理するワーカー"""
        while True:
            text = self.task_queue.get()
            self.abort_current_flag.clear()

            clean_text = self._sanitize_text(text)
            # 空行を除去してリスト化
            lines = [line.strip() for line in clean_text.splitlines() if line.strip()]

            if lines:
                print(f"🎤 合成開始: {len(lines)}行 (残りタスク: {self.task_queue.qsize()})")
                all_segments = []
                sample_rate = 44100

                for i, line in enumerate(lines):
                    # 中断フラグが立っていたら処理を打ち切る
                    if self.abort_current_flag.is_set():
                        print("⛔ タスク中断")
                        break

                    print(f"  ├ 合成中 ({i+1}/{len(lines)}): {line[:15]}...")
                    res = self.synth.synthesize_segment(line)
                    if not res: continue
                    data, sr = res
                    sample_rate = sr

                    # ストリーミング再生用にプレイヤーへ渡す
                    self.player.enqueue(data, sr)
                    all_segments.append(data)

                    # 文ごとのポーズ挿入
                    if Config.POST_PAUSE > 0 and i < len(lines) - 1:
                        silence = np.zeros(int(sr * Config.POST_PAUSE), dtype=data.dtype)
                        self.player.enqueue(silence, sr)
                        all_segments.append(silence)

                # 正常完了時のみファイル保存
                if not self.abort_current_flag.is_set() and all_segments:
                    self.synth.save_merged(all_segments, text, sample_rate)
            
            self.task_queue.task_done()

# ─── メインエントリーポイント ──────────────────────
def main():
    print("── AivisSpeech Reader v6.1 (Production) ──")
    print(f"📂 保存先: {Config.SAVE_DIR_ROOT}")
    print(f"🎵 Artist: {Config.ARTIST_NAME}")
    print(f"🛑 緊急停止コマンド: '{Config.STOP_COMMAND}' をコピーしてください")
    print("──────────────────────────────────────────")
    
    player = AudioPlayer()
    synth = AivisSynthesizer(Config)
    manager = TaskManager(synth, player)

    # エンジン接続チェック
    if not synth.check_connection():
        print("⚠️ エラー: AivisSpeech/VOICEVOXに接続できません。")
        print("   アプリケーションが起動しているか、ポート番号(settings.py)を確認してください。")

    # 起動時のクリップボード内容は無視
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

            if text and text != last_text and text.strip():
                last_text = text
                
                # 緊急停止コマンドの判定
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