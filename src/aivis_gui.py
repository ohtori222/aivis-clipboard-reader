import argparse
import ctypes
import os
import queue
import re
import sys
import threading
import time

import customtkinter as ctk
import pyperclip
from PIL import Image

import aivis_reader
from aivis_reader import get_project_root
from version import __version__

# テーマ設定
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("green")


class ConsoleRedirector:
    """stdoutをキャプチャしてGUIのテキストボックスに出力するクラス"""

    def __init__(self, text_widget, callback=None):
        self.text_widget = text_widget
        self.callback = callback
        self.queue: queue.Queue[str] = queue.Queue()
        self.running = True
        self.thread = threading.Thread(target=self._update_loop, daemon=True)
        self.thread.start()

    def write(self, message):
        if message:
            self.queue.put(message)

    def flush(self):
        pass

    def _update_loop(self):
        while self.running:
            try:
                message = self.queue.get(timeout=0.1)
                # GUI更新をメインスレッドで実行するために after を使用
                self.text_widget.after(0, self._safe_insert, message)
            except queue.Empty:
                pass
            except Exception as e:
                if sys.__stdout__:
                    sys.__stdout__.write(f"Console Error: {e}\n")

    def _safe_insert(self, message):
        self.text_widget.configure(state="normal")
        self.text_widget.insert("end", message)
        self.text_widget.see("end")
        self.text_widget.configure(state="disabled")
        if self.callback:
            self.callback(message)


class App(ctk.CTk):
    def __init__(self):
        # 1. タスクバーアイコンの分離 (AppUserModelID)
        try:
            myappid = f"ohtori.aivis_clipboard_reader.app_v2.{__version__}"
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except Exception:
            pass

        super().__init__()

        # ウィンドウ設定
        self.title(f"AivisSpeech Clipboard Reader v{__version__}")
        self.geometry("600x650")

        # 2. ウィンドウアイコンの設定
        self.after(200, self.setup_icon)

        # 終了処理
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        # データ管理
        self.clipboard_running = False
        self.last_text = ""

        # モジュール初期化
        self.cfg = aivis_reader.cfg
        self.player = aivis_reader.AudioPlayer()
        self.synth = aivis_reader.AivisSynthesizer()
        self.manager = aivis_reader.TaskManager(self.synth, self.player)

        # UI構築
        self.setup_ui()

        # コンソールリダイレクト
        sys.stdout = ConsoleRedirector(
            self.log_textbox, self.parse_log_message
        )  # type: ignore

        # 監視スレッド開始
        # 監視スレッド開始
        self.monitor_thread = threading.Thread(
            target=self.clipboard_monitor_loop, daemon=True
        )
        self.monitor_thread.start()
        self.clipboard_running = True

    def setup_icon(self):
        icon_name = "icon.ico"
        icon_path = None

        root_dir = get_project_root()
        # assetsフォルダ内を探す
        icon_path = os.path.join(root_dir, "assets", icon_name)

        # 優先順位:
        # 1. PyInstallerバンドル内 (sys._MEIPASS)
        # 2. get_project_root()/assets/icon.ico

        if hasattr(sys, "_MEIPASS"):
            bundled_path = os.path.join(sys._MEIPASS, "assets", icon_name)
            if os.path.exists(bundled_path):
                icon_path = bundled_path

        if icon_path and os.path.exists(icon_path):
            try:
                # Tkinter標準の方法
                self.iconbitmap(default=icon_path)

                # Windows APIを使用した強制適用 (タスクバー対策)
                self.force_windows_icon(icon_path)
            except Exception as e:
                print(f"⚠️ アイコン設定失敗: {e}")

    def force_windows_icon(self, icon_path):
        """Windows APIを使って明示的にアイコンを設定する (タスクバー反映用)"""
        try:
            # 定数定義
            WM_SETICON = 0x0080
            ICON_SMALL = 0
            ICON_BIG = 1
            LR_LOADFROMFILE = 0x0010
            IMAGE_ICON = 1

            # アイコン読み込み
            h_icon = ctypes.windll.user32.LoadImageW(
                None, icon_path, IMAGE_ICON, 0, 0, LR_LOADFROMFILE
            )

            if h_icon == 0:
                print("⚠️ Windows API: LoadImageW failed")
                return

            # HWND取得
            hwnd = ctypes.windll.user32.GetParent(self.winfo_id())
            if hwnd == 0:
                hwnd = self.winfo_id()

            # メッセージ送信
            ctypes.windll.user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, h_icon)
            ctypes.windll.user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, h_icon)

            print(f"🪟 Windows API: アイコン適用完了 (HWND: {hwnd})")

        except Exception as e:
            print(f"⚠️ Windows API Icons Error: {e}")

    def setup_ui(self):
        # タブ作成
        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(fill="both", expand=True, padx=10, pady=10)

        self.tab_dashboard = self.tabview.add("Dashboard")
        self.tab_log = self.tabview.add("Log")
        self.tab_settings = self.tabview.add("Settings")

        # --- Dashboard ---
        self.dashboard_frame = ctk.CTkScrollableFrame(
            self.tab_dashboard, fg_color="transparent"
        )
        self.dashboard_frame.pack(fill="both", expand=True)

        # アートワーク表示用フレーム (上部に固定) - 初期状態ではpackしない
        self.artwork_frame = ctk.CTkFrame(self.dashboard_frame, fg_color="transparent")

        # アートワーク表示 (あればここで配置される)
        self.setup_dashboard_artwork()

        self.status_label = ctk.CTkLabel(
            self.dashboard_frame,
            text="Wait...",
            font=ctk.CTkFont(size=32, weight="bold"),
        )
        self.status_label.pack(pady=10)

        # 再生コントロール
        self.control_frame = ctk.CTkFrame(self.dashboard_frame, fg_color="transparent")
        self.control_frame.pack(pady=10)

        self.btn_pause = ctk.CTkButton(
            self.control_frame,
            text="Pause / Resume",
            command=self.toggle_pause,
            width=140,
            height=50,
            font=ctk.CTkFont(size=14),
        )
        self.btn_pause.grid(row=0, column=0, padx=10)

        self.btn_stop = ctk.CTkButton(
            self.control_frame,
            text="STOP (Clear)",
            command=self.stop_playback,
            fg_color="red",
            hover_color="darkred",
            width=140,
            height=50,
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        self.btn_stop.grid(row=0, column=1, padx=10)

        self.btn_skip = ctk.CTkButton(
            self.control_frame,
            text="Skip Current",
            command=self.skip_queue,
            fg_color="gray",
            width=200,
            height=30,
        )
        self.btn_skip.grid(row=1, column=0, columnspan=2, pady=20)

        self.lbl_info = ctk.CTkLabel(
            self.dashboard_frame,
            text="Copy text to clipboard to start reading.",
            text_color="gray",
        )
        self.lbl_info.pack(side="bottom", pady=10)

        # --- Log ---
        self.log_textbox = ctk.CTkTextbox(
            self.tab_log, state="disabled", font=ctk.CTkFont(family="Consolas", size=12)
        )
        self.log_textbox.pack(fill="both", expand=True, padx=5, pady=5)

        # --- Settings ---
        self.create_settings_ui()

    def setup_dashboard_artwork(self):
        artwork_path = self.cfg.get("artwork_path", "cover.jpg")
        root_dir = get_project_root()

        # ConfigManagerで解決済みのパスを使用するが、
        # 相対パスの場合はルート基準で結合する
        if not os.path.isabs(artwork_path):
            artwork_path = os.path.join(root_dir, artwork_path)

        if os.path.exists(artwork_path):
            try:
                pil_image = Image.open(artwork_path)
                size = (250, 250)
                self.artwork_image = ctk.CTkImage(
                    light_image=pil_image, dark_image=pil_image, size=size
                )
                self.artwork_label = ctk.CTkLabel(
                    self.artwork_frame, text="", image=self.artwork_image
                )
                self.artwork_label.pack(pady=5)

                if self.cfg.get("show_artwork", True):
                    self.artwork_frame.pack(fill="x", pady=(5, 0))

                print(f"🖼️ Artwork loaded: {artwork_path}")
            except Exception as e:
                print(f"⚠️ Artwork load error: {e}")

    def create_settings_ui(self):
        frame = ctk.CTkScrollableFrame(self.tab_settings)
        frame.pack(fill="both", expand=True, padx=5, pady=5)

        # UI Settings
        ctk.CTkLabel(
            frame, text="Display Settings", font=ctk.CTkFont(size=14, weight="bold")
        ).pack(anchor="w", padx=10, pady=(10, 5))

        self.switch_artwork = ctk.CTkSwitch(
            frame,
            text="アートワークを表示 (Show Artwork)",
            command=self.toggle_artwork_visibility,
        )
        (
            self.switch_artwork.select()
            if self.cfg.get("show_artwork", True)
            else self.switch_artwork.deselect()
        )
        self.switch_artwork.pack(anchor="w", padx=20, pady=5)

        ctk.CTkLabel(
            frame, text="Playback Settings", font=ctk.CTkFont(size=14, weight="bold")
        ).pack(anchor="w", padx=10, pady=(20, 5))

        # Speed
        ctk.CTkLabel(frame, text="話速 (Speed)").pack(anchor="w", padx=10)
        self.slider_speed = ctk.CTkSlider(
            frame,
            from_=0.5,
            to=3.0,
            number_of_steps=25,
            command=self.update_speed_label,
        )
        self.slider_speed.set(self.cfg["speed"])
        self.slider_speed.pack(fill="x", padx=10, pady=5)
        self.lbl_speed_val = ctk.CTkLabel(frame, text=f"{self.cfg['speed']}")
        self.lbl_speed_val.pack(pady=(0, 10))

        # Volume
        ctk.CTkLabel(frame, text="音量 (Volume)").pack(anchor="w", padx=10)
        self.slider_volume = ctk.CTkSlider(
            frame,
            from_=0.0,
            to=2.0,
            number_of_steps=20,
            command=self.update_volume_label,
        )
        self.slider_volume.set(self.cfg["volume"])
        self.slider_volume.pack(fill="x", padx=10, pady=5)
        self.lbl_volume_val = ctk.CTkLabel(frame, text=f"{self.cfg['volume']}")
        self.lbl_volume_val.pack(pady=(0, 10))

        ctk.CTkLabel(
            frame, text="Connection Settings", font=ctk.CTkFont(size=14, weight="bold")
        ).pack(anchor="w", padx=10, pady=(20, 5))

        # Connection
        ctk.CTkLabel(frame, text="Host").pack(anchor="w", padx=10)
        self.entry_host = ctk.CTkEntry(frame)
        self.entry_host.insert(0, str(self.cfg["host"]))
        self.entry_host.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(frame, text="Port").pack(anchor="w", padx=10)
        self.entry_port = ctk.CTkEntry(frame)
        self.entry_port.insert(0, str(self.cfg["port"]))
        self.entry_port.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(frame, text="Speaker ID").pack(anchor="w", padx=10)
        self.entry_speaker = ctk.CTkEntry(frame)
        self.entry_speaker.insert(0, str(self.cfg["speaker_id"]))
        self.entry_speaker.pack(fill="x", padx=10, pady=5)

        # Save Button
        self.btn_save = ctk.CTkButton(
            frame,
            text="Save Settings",
            command=self.save_settings,
            fg_color="green",
            hover_color="darkgreen",
        )
        self.btn_save.pack(pady=30)

        self.lbl_save_status = ctk.CTkLabel(frame, text="")
        self.lbl_save_status.pack()

    def update_speed_label(self, value):
        val = round(value, 2)
        self.lbl_speed_val.configure(text=str(val))

    def update_volume_label(self, value):
        val = round(value, 2)
        self.lbl_volume_val.configure(text=str(val))

    def toggle_artwork_visibility(self):
        show = self.switch_artwork.get() == 1
        # アートワーク画像の有無に関わらずフレーム自体の表示を切り替え
        if hasattr(self, "artwork_frame"):
            if show:
                # status_labelより前に挿入することで上部配置を維持
                self.artwork_frame.pack(fill="x", pady=(5, 0), before=self.status_label)
            else:
                self.artwork_frame.pack_forget()

    def save_settings(self):
        try:
            self.cfg["speed"] = round(self.slider_speed.get(), 2)
            self.cfg["volume"] = round(self.slider_volume.get(), 2)
            self.cfg["host"] = self.entry_host.get()
            self.cfg["port"] = int(self.entry_port.get())
            self.cfg["speaker_id"] = int(self.entry_speaker.get())
            self.cfg["show_artwork"] = self.switch_artwork.get() == 1

            # 再接続のためにBase URLを更新
            self.synth.base_url = f"http://{self.cfg['host']}:{self.cfg['port']}"

            self.cfg.save_to_local()
            self.lbl_save_status.configure(
                text="Saved to config.local.json!", text_color="green"
            )
        except Exception as e:
            self.lbl_save_status.configure(text=f"Error: {e}", text_color="red")

    def toggle_pause(self):
        paused = self.player.toggle_pause()
        state = "Paused" if paused else "Resuming"
        sys.stdout.write(f"GUI: {state}\n")
        self.status_label.configure(
            text="PAUSED" if paused else "Playing",
            text_color="orange" if paused else "cyan",
        )

    def stop_playback(self):
        self.manager.force_stop()
        sys.stdout.write("GUI: Force Stopped\n")
        self.status_label.configure(text="STOPPED", text_color="red")

    def skip_queue(self):
        self.manager.skip_current()
        sys.stdout.write("GUI: Skip Current\n")

    def parse_log_message(self, message):
        # ログメッセージ解析してステータス更新
        msg = message.strip()
        if "合成開始" in msg:
            self.status_label.configure(text="Synthesizing...", text_color="cyan")
        elif "新着検知" in msg:
            self.status_label.configure(text="Reading...", text_color="yellow")
        elif "保存完了" in msg:
            self.status_label.configure(text="Ready", text_color="white")

    def clipboard_monitor_loop(self):
        """aivis_reader.mainのループ部分に相当"""
        stop_cmd = self.cfg.get("stop_command", ";;STOP")

        # 初期クリップボード取得
        try:
            self.last_text = pyperclip.paste()
        except Exception:
            self.last_text = ""

        while self.clipboard_running:
            try:
                current_text = pyperclip.paste()
            except Exception:
                current_text = ""

            if current_text and current_text != self.last_text:
                self.last_text = current_text

                if current_text.strip() == stop_cmd:
                    self.stop_playback()
                    continue

                if current_text.strip():
                    print("\n📝 新着検知")
                    self.manager.add_text(current_text)

            time.sleep(0.5)

    def on_closing(self):
        self.clipboard_running = False
        self.player.stop_immediate()
        self.destroy()
        sys.exit(0)


if __name__ == "__main__":
    # 引数解析
    parser = argparse.ArgumentParser(description="AivisSpeech Clipboard Reader (GUI)")
    parser.add_argument(
        "-f",
        "--flac",
        action="store_true",
        help="強制的にFLAC形式で保存します (FFmpegがある場合でも)",
    )
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
        aivis_reader.cfg["override_date"] = args.date
        print(f"📅 日付上書きモード: {args.date} として保存します")

    # FLAC強制オプション
    cfg_force_flac = aivis_reader.cfg.get("force_flac", False)
    if args.flac or cfg_force_flac:
        aivis_reader.cfg["force_flac"] = True  # 設定オブジェクトを更新
        if args.flac:
            print("🔧 オプション指定: 強制的にFLACで保存します。")

    app = App()
    app.mainloop()
