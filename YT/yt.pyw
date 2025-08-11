import sys
import os
import platform
import subprocess
import re
import json
import time
import urllib.request
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit,
    QPushButton, QTextEdit, QVBoxLayout, QHBoxLayout,
    QSizePolicy, QProgressBar, QDesktopWidget, QScrollBar,
    QListWidget, QListWidgetItem, QMessageBox, QFrame,
    QGraphicsDropShadowEffect, QMenu, QAction, QActionGroup, QFileDialog)
from PyQt5.QtGui import QIcon, QFont, QPixmap, QClipboard, QColor, QPainter, QBrush, QPen, QFontMetrics
from PyQt5.QtCore import (
    Qt, QSize, QThread, pyqtSignal, QObject, QMutex, QPoint, QTimer, QRect)
import pyperclip
import yt_dlp

def is_windows():
    return platform.system() == "Windows"

def sanitize_filename(filename):
    return re.sub(r'[\\/*?"<>|]', "", filename)

def get_clipboard_link():
    content = pyperclip.paste()
    if content and isinstance(content, str) and content.startswith("http"):
        return content
    return None

class PreFlightThread(QThread):
    finished = pyqtSignal(dict, int, bool, str, int)
    error = pyqtSignal(int, str)

    def __init__(self, url, ydl_opts, item_id, is_audio, parent=None):
        super().__init__(parent)
        self.url = url
        self.ydl_opts = ydl_opts
        self.item_id = item_id
        self.is_audio = is_audio

    def run(self):
        try:
            with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                info_dict = ydl.extract_info(self.url, download=False)

                total_size = 0
                formats_to_download = info_dict.get('requested_formats')
                if formats_to_download:
                    for f in formats_to_download:
                        total_size += f.get('filesize') or f.get('filesize_approx', 0)
                else:
                    total_size = info_dict.get('filesize') or info_dict.get('filesize_approx', 0)

                self.finished.emit(info_dict, total_size, self.is_audio, self.url, self.item_id)

        except Exception as e:
            self.error.emit(self.item_id, str(e))

class DownloadThread(QThread):
    progress_signal = pyqtSignal(dict)
    finished_signal = pyqtSignal(dict)
    error_signal = pyqtSignal(int, str)
    item_id_signal = pyqtSignal(int)
    postprocessing_signal = pyqtSignal(dict)
    final_filepath_signal = pyqtSignal(int, str)

    def __init__(self, info_dict, ydl_opts, item_id, total_size, parent=None):
        super().__init__(parent)
        self.info_dict = info_dict
        self.ydl_opts = ydl_opts
        self.item_id = item_id
        self.total_combined_size = total_size
        self.video_bytes = 0
        self.audio_bytes = 0

    def run(self):
        try:
            self.item_id_signal.emit(self.item_id)
            self.ydl_opts['progress_hooks'] = [self.progress_hook]
            self.ydl_opts['postprocessor_hooks'] = [self.postprocessor_hook]

            with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                final_info = ydl.process_ie_result(self.info_dict, download=True)
                if not final_info:
                    raise yt_dlp.utils.DownloadError("Download failed, no info dictionary returned.")

            final_info['item_id'] = self.item_id
            self.finished_signal.emit(final_info)

        except yt_dlp.utils.DownloadError as e:
            self.error_signal.emit(self.item_id, str(e))
        except Exception as e:
            self.error_signal.emit(self.item_id, f"An unexpected error occurred: {e}")

    def progress_hook(self, d):
        d['item_id'] = self.item_id
        if d['status'] == 'downloading':
            info = d.get('info_dict', {})
            is_video = info.get('vcodec') != 'none' and info.get('acodec') == 'none'
            is_audio = info.get('acodec') != 'none' and info.get('vcodec') == 'none'

            if is_video:
                self.video_bytes = d.get('downloaded_bytes', 0)
            elif is_audio:
                self.audio_bytes = d.get('downloaded_bytes', 0)
            else:
                self.video_bytes = d.get('downloaded_bytes', 0)
                self.audio_bytes = 0

            total_downloaded = self.video_bytes + self.audio_bytes

            if self.total_combined_size > 0:
                percent = (total_downloaded / float(self.total_combined_size)) * 100
                d['total_percent'] = percent

        self.progress_signal.emit(d)

    def postprocessor_hook(self, d):
        d['item_id'] = self.item_id
        self.postprocessing_signal.emit(d)

        if d['status'] == 'finished':
            filepath = d.get('filepath') or d.get('info_dict', {}).get('filepath')
            if filepath:
                self.final_filepath_signal.emit(self.item_id, filepath)

class ThumbnailFetcher(QThread):
    thumbnail_loaded = pyqtSignal(QPixmap)
    info_loaded = pyqtSignal(dict, bool, str, int)
    error_signal = pyqtSignal(int, str)

    def __init__(self, url, is_audio, item_id, parent=None):
        super().__init__(parent)
        self.url = url
        self.is_audio = is_audio
        self.item_id = item_id

    def run(self):
        try:
            ydl_opts = {
                'no_warnings': True,
                'noplaylist': True,
                'playlist_items': '1',
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'en-us,en;q=0.5',
                },
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info_dict = ydl.extract_info(self.url, download=False)

            if info_dict:
                self.info_loaded.emit(info_dict, self.is_audio, self.url, self.item_id)
                thumbnail_url = info_dict.get('thumbnail')
                if thumbnail_url:
                    with urllib.request.urlopen(thumbnail_url) as response:
                        thumbnail_data = response.read()
                        pixmap = QPixmap()
                        pixmap.loadFromData(thumbnail_data)
                        if not pixmap.isNull():
                            pixmap = pixmap.scaled(320, 180, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                            self.thumbnail_loaded.emit(pixmap)
            else:
                self.error_signal.emit(self.item_id, "Could not fetch video info.")

        except yt_dlp.utils.DownloadError as e:
            self.error_signal.emit(self.item_id, f"yt-dlp error: {e}")
        except Exception as e:
            self.error_signal.emit(self.item_id, f"Error loading thumbnail: {e}")

class ModernScrollBar(QScrollBar):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet('''
            QScrollBar:vertical { border: none; background: #28252b; width: 10px; margin: 0; }
            QScrollBar::handle:vertical { background-color: #3e284f; min-height: 20px; border-radius: 5px; }
            QScrollBar::handle:vertical:hover { background-color: #4e385f; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { background: none; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
        ''')

class DownloadItemWidget(QWidget):
    def __init__(self, item, parent=None):
        super().__init__(parent)
        self.item = item
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(5, 5, 5, 5)
        self.layout.setSpacing(3)
        self.title_label = QLabel("Starting...")
        self.title_label.setWordWrap(True)
        self.title_label.setStyleSheet("font-weight: bold;")
        self.layout.addWidget(self.title_label)
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(12)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat('%p%')
        self.layout.addWidget(self.progress_bar)
        self.status_label = QLabel("Waiting...")
        self.status_label.setStyleSheet("font-size: 10px; color: #aaa;")
        self.layout.addWidget(self.status_label)

    def set_title(self, text):
        self.title_label.setText(text)
        self.title_label.setToolTip(text)
        self.item.setSizeHint(self.sizeHint())

    def set_progress(self, value):
        self.progress_bar.setValue(value)

    def set_status(self, text, color_hex):
        self.status_label.setText(text)
        self.status_label.setStyleSheet(f"font-size: 10px; color: {color_hex};")

    def set_type(self, is_audio):
        self.progress_bar.setProperty("is_audio", is_audio)
        self.progress_bar.style().unpolish(self.progress_bar)
        self.progress_bar.style().polish(self.progress_bar)

class FFmpegCheckThread(QThread):
    finished = pyqtSignal(bool)
    def run(self):
        try:
            subprocess.run(['ffmpeg', '-version'], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW if is_windows() else 0)
            self.finished.emit(True)
        except (FileNotFoundError, subprocess.CalledProcessError):
            self.finished.emit(False)

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowTitle("iMA Downloader")
        self.old_pos = self.pos()
        self.downloaded_files = {}
        self.download_widgets = {}
        self.active_threads = []
        self.current_preview_url = None
        self.current_preview_info = {}
        self.BG_COLOR = "#28252b"
        self.TEXT_COLOR = "#bfb8dd"
        self.ACCENT_COLOR = "#141316"
        self.VIDEO_COLOR = "#9b59b6"
        self.AUDIO_COLOR = "#3498db"
        self.VIDEO_QUALITY_MAP = {
            "Max Quality (4K/8K)": "bestvideo+bestaudio",
            "Highest (1080p/1440p)": "bestvideo*[height<=1440]+bestaudio/best[height<=1440]",
            "High (1080p)": "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
            "Mid (720p)": "bestvideo[height<=720]+bestaudio/best[height<=720]",
            "Low (480p)": "bestvideo[height<=480]+bestaudio/best[height<=480]",
        }
        self.AUDIO_QUALITY_MAP = {
            "Highest": "bestaudio/best", "High (~256kbps)": "bestaudio[abr<=256]",
            "Mid (~192kbps)": "bestaudio[abr<=192]", "Low (~128kbps)": "bestaudio[abr<=128]",
        }
        self.load_config()
        self.check_ffmpeg()
        self.url_debounce_timer = QTimer(self)
        self.url_debounce_timer.setSingleShot(True)
        self.url_debounce_timer.timeout.connect(self.trigger_thumbnail_fetch)
        self.setup_ui()
        self.center_window()
        self.paste_link()
        self.item_counter = 0

    def check_ffmpeg(self):
        self.ffmpeg_checker = FFmpegCheckThread(self)
        self.ffmpeg_checker.finished.connect(self.on_ffmpeg_check_finished)
        self.ffmpeg_checker.finished.connect(self.on_thread_finished)
        self.active_threads.append(self.ffmpeg_checker)
        self.ffmpeg_checker.start()

    def on_ffmpeg_check_finished(self, found):
        if not found:
            QMessageBox.warning(self, "ffmpeg Not Found", "ffmpeg was not found on your system's PATH. Some features may not work.")

    def setup_ui(self):
        self.background_frame = QFrame(self)
        self.background_frame.setObjectName("background")
        self.apply_shadow(self.background_frame, 20, 5)
        main_layout = QVBoxLayout(self.background_frame)
        main_layout.setContentsMargins(15, 5, 15, 15)
        title_bar_layout = self.setup_title_bar()
        main_layout.addLayout(title_bar_layout)
        content_layout = QHBoxLayout()
        main_layout.addLayout(content_layout)
        self.queue_list = self.setup_queue_list()
        content_layout.addWidget(self.queue_list)
        right_layout = self.setup_right_panel()
        content_layout.addLayout(right_layout)
        outer_layout = QVBoxLayout(self)
        outer_layout.addWidget(self.background_frame)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(outer_layout)
        self.set_stylesheet()

    def setup_title_bar(self):
        title_bar_layout = QHBoxLayout()
        icon_label = QLabel()
        icon_pixmap = QPixmap('yt.ico').scaled(24, 24, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        icon_label.setPixmap(icon_pixmap)
        title_label = QLabel("iMA Downloader")
        title_label.setStyleSheet("font-weight: bold;")
        settings_button = self.setup_settings_menu()
        dir_button = self.setup_dir_button()
        minimize_button = QPushButton("—")
        minimize_button.setObjectName("controlBtn")
        minimize_button.clicked.connect(self.showMinimized)
        close_button = QPushButton("✕")
        close_button.setObjectName("controlBtn")
        close_button.clicked.connect(self.close)
        for widget in [icon_label, title_label, settings_button, dir_button]:
            title_bar_layout.addWidget(widget)
        title_bar_layout.addStretch()
        for widget in [minimize_button, close_button]:
            title_bar_layout.addWidget(widget)
        return title_bar_layout

    def setup_settings_menu(self):
        settings_button = QPushButton("⚙️")
        settings_button.setObjectName("settingsBtn")
        settings_button.setFixedSize(28, 28)
        self.settings_menu = QMenu(self)
        settings_button.setMenu(self.settings_menu)
        self.apply_shadow(settings_button)
        video_quality_group = QActionGroup(self)
        video_quality_group.setExclusive(True)
        video_menu = self.settings_menu.addMenu("Video Quality")
        for quality, format_string in self.VIDEO_QUALITY_MAP.items():
            action = QAction(quality, self, checkable=True)
            action.setData(format_string)
            action.triggered.connect(lambda checked, q=quality: self.set_video_quality(q))
            if self.video_quality == format_string:
                action.setChecked(True)
            video_menu.addAction(action)
            video_quality_group.addAction(action)
        audio_quality_group = QActionGroup(self)
        audio_quality_group.setExclusive(True)
        audio_menu = self.settings_menu.addMenu("Audio Quality")
        for quality, format_string in self.AUDIO_QUALITY_MAP.items():
            action = QAction(quality, self, checkable=True)
            action.setData(format_string)
            action.triggered.connect(lambda checked, q=quality: self.set_audio_quality(q))
            if self.audio_quality == format_string:
                action.setChecked(True)
            audio_menu.addAction(action)
            audio_quality_group.addAction(action)
        return settings_button

    def setup_dir_button(self):
        dir_button = QPushButton("📁")
        dir_button.setObjectName("dirBtn")
        dir_button.setFixedSize(28, 28)
        dir_button.setToolTip("Set Download Directory")
        dir_button.clicked.connect(self.select_output_directory)
        self.apply_shadow(dir_button)
        return dir_button

    def setup_queue_list(self):
        queue_list = QListWidget()
        queue_list.setSpacing(4)
        queue_list.setFixedWidth(220)
        queue_list.setVerticalScrollBar(ModernScrollBar())
        queue_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        queue_list.itemDoubleClicked.connect(self.open_downloaded_file)
        self.apply_shadow(queue_list)
        return queue_list

    def setup_right_panel(self):
        right_layout = QVBoxLayout()
        self.thumbnail_label = QLabel()
        self.thumbnail_label.setFixedSize(320, 180)
        self.thumbnail_label.setAlignment(Qt.AlignCenter)
        self.thumbnail_label.setStyleSheet(f"background-color: {self.ACCENT_COLOR}; border-radius: 10px;")
        self.apply_shadow(self.thumbnail_label)
        right_layout.addWidget(self.thumbnail_label)
        self.title_label = QLabel("Enter a URL to begin")
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        self.title_label.setWordWrap(True)
        right_layout.addWidget(self.title_label)
        url_layout = QHBoxLayout()
        self.url_entry = QLineEdit()
        self.url_entry.setPlaceholderText("https://...")
        self.url_entry.textChanged.connect(self.on_url_changed)
        self.apply_shadow(self.url_entry)
        url_layout.addWidget(self.url_entry)
        self.paste_button = QPushButton("📋")
        self.paste_button.setObjectName("paste")
        self.paste_button.setFixedSize(40, 40)
        self.paste_button.clicked.connect(self.paste_link)
        self.apply_shadow(self.paste_button)
        url_layout.addWidget(self.paste_button)
        right_layout.addLayout(url_layout)
        button_layout = QHBoxLayout()
        self.download_video_button = QPushButton("🎬 Video")
        self.download_video_button.setObjectName("download_video")
        self.download_video_button.clicked.connect(lambda: self.add_to_queue(is_audio=False))
        self.apply_shadow(self.download_video_button)
        button_layout.addWidget(self.download_video_button)
        self.download_audio_button = QPushButton("🎧 Audio")
        self.download_audio_button.setObjectName("download_audio")
        self.download_audio_button.clicked.connect(lambda: self.add_to_queue(is_audio=True))
        self.apply_shadow(self.download_audio_button)
        button_layout.addWidget(self.download_audio_button)
        right_layout.addLayout(button_layout)
        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        self.output_text.setVerticalScrollBar(ModernScrollBar())
        self.output_text.setFixedHeight(80)
        self.apply_shadow(self.output_text)
        right_layout.addWidget(self.output_text)
        return right_layout

    def set_stylesheet(self):
        stylesheet = (
            f"#background {{ background-color: {self.BG_COLOR}; border-radius: 20px; border: 2px solid {self.ACCENT_COLOR}; }}"
            f"QLabel {{ color: {self.TEXT_COLOR}; background-color: transparent; border: none; }}"
            f"QLineEdit {{ background-color: {self.ACCENT_COLOR}; color: {self.TEXT_COLOR}; border: 1px solid {self.ACCENT_COLOR}; border-radius: 10px; padding: 8px; font-size: 14px; }}"
            f"QLineEdit:focus {{ border: 1px solid {self.VIDEO_COLOR}; }}"
            f"QPushButton#paste {{ background-color: {self.ACCENT_COLOR}; color: {self.TEXT_COLOR}; border: none; border-radius: 10px; font-size: 18px; }}"
            f"QPushButton#paste:hover {{ background-color: {self.VIDEO_COLOR}; }}"
            f"QPushButton#download_video, QPushButton#download_audio {{ background-color: {self.ACCENT_COLOR}; color: {self.TEXT_COLOR}; border: none; border-radius: 10px; padding: 10px 20px; font-size: 14px; font-weight: bold; }}"
            f"QPushButton#download_video:hover {{ background-color: {self.VIDEO_COLOR}; }}"
            f"QPushButton#download_audio:hover {{ background-color: {self.AUDIO_COLOR}; }}"
            f"QTextEdit {{ background-color: {self.ACCENT_COLOR}; color: {self.TEXT_COLOR}; border: none; border-radius: 10px; padding: 5px; }}"
            f"QListWidget {{ background-color: {self.ACCENT_COLOR}; border: none; border-radius: 10px; color: {self.TEXT_COLOR}; padding: 5px; }}"
            f"QListWidget::item {{ background-color: transparent; border-radius: 8px; padding: 2px; margin: 2px; }}"
            f"QListWidget::item:hover {{ background-color: {self.BG_COLOR}; }}"
            f"QListWidget::item:selected {{ background-color: {self.VIDEO_COLOR}; color: white; border: 1px solid {self.TEXT_COLOR}; }}"
            f"QPushButton#controlBtn, QPushButton#dirBtn {{ background-color: transparent; color: #bfb8dd; border: none; font-size: 14px; font-weight: bold; }}"
            f"QPushButton#controlBtn:hover {{ color: #ff5555; }}"
            f"QPushButton#dirBtn:hover {{ color: #82e0aa; }}"
            f"QPushButton#settingsBtn {{ background-color: transparent; color: #bfb8dd; border: none; font-size: 18px; }}"
            f"QPushButton#settingsBtn::menu-indicator {{ image: none; }}"
            f"QMenu {{ background-color: {self.BG_COLOR}; color: {self.TEXT_COLOR}; border: 1px solid {self.ACCENT_COLOR}; }}"
            f"QMenu::item:selected {{ background-color: {self.VIDEO_COLOR}; }}"
            f"QProgressBar::chunk[is_audio=\"false\"] {{ background-color: {self.VIDEO_COLOR}; border-radius: 5px; }}"
            f"QProgressBar::chunk[is_audio=\"true\"] {{ background-color: {self.AUDIO_COLOR}; border-radius: 5px; }}"
        )
        self.setStyleSheet(stylesheet)

    def set_video_quality(self, quality_key):
        self.video_quality = self.VIDEO_QUALITY_MAP[quality_key]
        self.save_config()

    def set_audio_quality(self, quality_key):
        self.audio_quality = self.AUDIO_QUALITY_MAP[quality_key]
        self.save_config()

    def apply_shadow(self, widget, blur=20, y_offset=5):
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(blur)
        shadow.setColor(QColor(0, 0, 0, 160))
        shadow.setOffset(0, y_offset)
        widget.setGraphicsEffect(shadow)

    def paste_link(self):
        link = get_clipboard_link()
        if link:
            self.url_entry.setText(link)

    def on_url_changed(self, url):
        if "http" in url:
            self.url_debounce_timer.start(500)

    def trigger_thumbnail_fetch(self):
        url = self.url_entry.text()
        if not url.startswith("http"): return
        self.current_preview_url = url
        self.thumbnail_label.setPixmap(QPixmap())
        self.title_label.setText("Fetching title...")
        fetcher = ThumbnailFetcher(url, False, -1, self)
        fetcher.info_loaded.connect(self.on_preview_info_loaded)
        fetcher.thumbnail_loaded.connect(self.set_thumbnail)
        fetcher.error_signal.connect(lambda id, err: self.title_label.setText(err) if id == -1 else None)
        fetcher.finished.connect(self.on_thread_finished)
        self.active_threads.append(fetcher)
        fetcher.start()

    def set_thumbnail(self, pixmap):
        self.thumbnail_label.setPixmap(pixmap)

    def on_preview_info_loaded(self, info, is_audio, url, item_id):
        if item_id == -1:
            self.title_label.setText(info.get('title', 'No title found'))
            self.current_preview_info = info

    def add_to_queue(self, is_audio):
        url = self.url_entry.text()
        if not url: return
        self.item_counter += 1
        item_id = self.item_counter
        prefix = "🎧" if is_audio else "🎬"
        item = QListWidgetItem(self.queue_list)
        item.setData(Qt.UserRole, item_id)
        widget = DownloadItemWidget(item)
        widget.set_type(is_audio)
        widget.set_title(f"{prefix} Preparing...")
        self.download_widgets[item_id] = widget
        item.setSizeHint(widget.sizeHint())
        self.queue_list.insertItem(0, item)
        self.queue_list.setItemWidget(item, widget)
        output_template = os.path.join(self.output_dir, '%(title)s.%(ext)s')
        ydl_opts = {
            'outtmpl': output_template, 'noplaylist': True, 'no_warnings': True, 'quiet': True,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-us,en;q=0.5',
            },
        }
        if is_audio:
            ydl_opts.update({'format': self.audio_quality, 'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3'}]})
        else:
            ydl_opts.update({'format': self.video_quality, 'merge_output_format': 'mp4', 'postprocessors': [{'key': 'FFmpegVideoConvertor', 'preferedformat': 'mp4'}]})

        pre_flight_thread = PreFlightThread(url, ydl_opts, item_id, is_audio, self)
        pre_flight_thread.finished.connect(self.on_preflight_complete)
        pre_flight_thread.error.connect(self.on_item_error)
        pre_flight_thread.finished.connect(self.on_thread_finished)
        self.active_threads.append(pre_flight_thread)
        pre_flight_thread.start()

    def on_preflight_complete(self, info_dict, total_size, is_audio, url, item_id):
        widget = self.download_widgets.get(item_id)
        if not widget: return
        prefix = "🎧" if is_audio else "🎬"
        title = info_dict.get('title', 'No Title')
        sanitized_title = sanitize_filename(title)
        widget.set_title(f"{prefix} {sanitized_title}")
        ydl_opts = self.get_ydl_opts(is_audio)
        downloader = DownloadThread(info_dict, ydl_opts, item_id, total_size, self)
        downloader.item_id_signal.connect(self.on_item_start)
        downloader.progress_signal.connect(self.on_item_progress_update)
        downloader.finished_signal.connect(self.on_item_finished)
        downloader.final_filepath_signal.connect(self.on_final_filepath_ready)
        downloader.postprocessing_signal.connect(self.on_item_postprocessing)
        downloader.error_signal.connect(self.on_item_error)
        downloader.finished.connect(self.on_thread_finished)
        self.active_threads.append(downloader)
        downloader.start()

    def get_ydl_opts(self, is_audio):
        output_template = os.path.join(self.output_dir, '%(title)s.%(ext)s')
        ydl_opts = {
            'outtmpl': output_template, 'noplaylist': True, 'no_warnings': True, 'quiet': True,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-us,en;q=0.5',
            },
        }
        if is_audio:
            ydl_opts.update({'format': self.audio_quality, 'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3'}]})
        else:
            ydl_opts.update({'format': self.video_quality, 'merge_output_format': 'mp4', 'postprocessors': [{'key': 'FFmpegVideoConvertor', 'preferedformat': 'mp4'}]})
        return ydl_opts

    def on_item_error(self, item_id, error_message):
        if item_id in self.download_widgets:
            widget = self.download_widgets[item_id]
            widget.set_status(f"Error: {error_message[:40]}...", "#ff5555")
            widget.setToolTip(error_message)

    def on_item_progress_update(self, d):
        item_id = d.get('item_id')
        widget = self.download_widgets.get(item_id)
        if not widget: return
        if d['status'] == 'downloading':
            if 'total_percent' in d:
                widget.set_progress(int(d['total_percent']))
            else:
                total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                if total_bytes > 0:
                    percent = (d.get('downloaded_bytes', 0) / total_bytes) * 100
                    widget.set_progress(int(percent))
            info = d.get('info_dict', {})
            vcodec, acodec = info.get('vcodec'), info.get('acodec')
            stage = "Video" if vcodec != 'none' else "Audio" if acodec != 'none' else "Muxed"
            speed = d.get('speed')
            eta = d.get('eta')
            speed_str = f"{speed / 1024 / 1024:.2f} MiB/s" if speed else "..."
            eta_str = f"{int(eta)}s" if eta is not None else "..."
            widget.set_status(f"{stage}: {speed_str} | {eta_str}", self.TEXT_COLOR)
        elif d['status'] == 'finished':
            widget.set_status("Download stage complete...", "#aaa")

    def on_item_postprocessing(self, d):
        item_id = d.get('item_id')
        widget = self.download_widgets.get(item_id)
        if not widget: return
        if d['status'] == 'started' or d['status'] == 'processing':
            widget.set_status(f"Processing: {d.get('postprocessor')}...", self.TEXT_COLOR)

    def on_item_start(self, item_id):
        if item_id in self.download_widgets:
            self.download_widgets[item_id].set_status("Downloading...", self.TEXT_COLOR)

    def on_item_finished(self, info_dict):
        item_id = info_dict.get('item_id')
        widget = self.download_widgets.get(item_id)
        if widget:
            widget.set_status("Processing complete", "#50fa7b")
            widget.set_progress(100)

    def on_final_filepath_ready(self, item_id, filepath):
        self.downloaded_files[item_id] = filepath
        widget = self.download_widgets.get(item_id)
        if widget:
            widget.set_status("Download Complete!", "#50fa7b")

    def on_thread_finished(self):
        thread = self.sender()
        if thread and thread in self.active_threads:
            self.active_threads.remove(thread)

    def select_output_directory(self):
        directory = QFileDialog.getExistingDirectory(self, "Select Download Folder", self.output_dir)
        if directory:
            self.output_dir = directory
            self.save_config()

    def save_config(self):
        config = {'output_dir': self.output_dir, 'video_quality': self.video_quality, 'audio_quality': self.audio_quality}
        with open('config.json', 'w') as f:
            json.dump(config, f, indent=4)

    def load_config(self):
        default_video_quality = self.VIDEO_QUALITY_MAP.get("Highest (1080p/1440p)", "bestvideo+bestaudio/best")
        try:
            with open('config.json', 'r') as f:
                config = json.load(f)
                self.output_dir = config.get('output_dir', os.getcwd())
                self.video_quality = config.get('video_quality', default_video_quality)
                self.audio_quality = config.get('audio_quality', self.AUDIO_QUALITY_MAP["Highest"])
        except (FileNotFoundError, json.JSONDecodeError):
            self.output_dir = os.getcwd()
            self.video_quality = default_video_quality
            self.audio_quality = self.AUDIO_QUALITY_MAP["Highest"]

    def center_window(self):
        qr = self.frameGeometry()
        cp = QDesktopWidget().availableGeometry().center()
        qr.moveCenter(cp)
        self.move(qr.topLeft())

    def mousePressEvent(self, event):
        self.old_pos = event.globalPos()

    def mouseMoveEvent(self, event):
        delta = QPoint(event.globalPos() - self.old_pos)
        self.move(self.x() + delta.x(), self.y() + delta.y())
        self.old_pos = event.globalPos()

    def open_downloaded_file(self, item):
        item_id = item.data(Qt.UserRole)
        filepath = self.downloaded_files.get(item_id)
        if filepath and os.path.isfile(filepath):
            try:
                if is_windows():
                    os.startfile(os.path.normpath(filepath))
                else:
                    subprocess.Popen(['xdg-open', filepath])
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not open file:\n{e}")
        else:
            QMessageBox.warning(self, "Warning", f"File not found or download not complete. Path: {filepath}")

    def closeEvent(self, event):
        for thread in self.active_threads:
            if thread.isRunning():
                thread.terminate()
                thread.wait()
        super().closeEvent(event)

if __name__ == '__main__':
    if is_windows():
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("myappid")

    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon('yt.ico'))
    window = MainWindow()
    window.resize(600, 520)
    window.show()
    sys.exit(app.exec_())
