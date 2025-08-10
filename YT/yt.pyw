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
    QGraphicsDropShadowEffect, QMenu, QAction, QActionGroup)
from PyQt5.QtGui import QIcon, QFont, QPixmap, QClipboard, QColor, QPainter, QBrush, QPen, QFontMetrics
from PyQt5.QtCore import (
    Qt, QSize, QThread, pyqtSignal, QObject, QMutex, QPoint)
import pyperclip
import yt_dlp

class DownloadThread(QThread):
    # Signal to emit download progress dictionary
    progress_signal = pyqtSignal(dict)
    # Signal to emit the final info dictionary on success
    finished_signal = pyqtSignal(dict)
    # Signal to emit on an error, passing item_id and the error message
    error_signal = pyqtSignal(int, str)
    # Signal to emit the item_id when the thread starts
    item_id_signal = pyqtSignal(int)

    def __init__(self, url, ydl_opts, item_id, parent=None):
        super().__init__(parent)
        self.url = url
        self.ydl_opts = ydl_opts
        self.item_id = item_id

    def run(self):
        try:
            self.item_id_signal.emit(self.item_id)
            # Add the progress hook to the options
            self.ydl_opts['progress_hooks'] = [self.progress_hook]

            with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                info_dict = ydl.extract_info(self.url, download=True)
                # If there was an error, ydl.extract_info might return None
                # or a dict without filepath for a failed download.
                if not info_dict or 'filepath' not in info_dict:
                    # This check is a fallback. The hook should report 'error' status.
                    raise yt_dlp.utils.DownloadError("Download failed, no file produced.")

            info_dict['item_id'] = self.item_id
            self.finished_signal.emit(info_dict)

        except yt_dlp.utils.DownloadError as e:
            self.error_signal.emit(self.item_id, str(e))
        except Exception as e:
            self.error_signal.emit(self.item_id, f"An unexpected error occurred: {e}")

    def progress_hook(self, d):
        # Add item_id to the dictionary so the receiver knows which download it is
        d['item_id'] = self.item_id
        self.progress_signal.emit(d)

def is_windows():
    return platform.system() == "Windows"

def sanitize_filename(filename):
    return re.sub(r'[\\/*?"<>|]', "", filename)

def get_subprocess_env():
    env = os.environ.copy()
    env['PYTHONIOENCODING'] = 'utf-8'
    env['LANG'] = 'en_US.UTF-8'
    return env

def get_clipboard_link():
    content = pyperclip.paste()
    if content and isinstance(content, str) and content.startswith("http"):
        return content
    return None


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

class DownloadQueue(QObject):
    def __init__(self, max_concurrent_downloads=3):
        super().__init__()
        self.queue = []
        self.running_downloads = 0
        self.max_concurrent_downloads = max_concurrent_downloads
        self.mutex = QMutex()

    def start_download(self, executor):
        self.mutex.lock()
        if self.running_downloads < self.max_concurrent_downloads:
            self.running_downloads += 1
            self.mutex.unlock()
            executor.finished.connect(self.on_executor_finished)
            executor.start()
        else:
            self.queue.append(executor)
            self.mutex.unlock()

    def on_executor_finished(self):
        self.mutex.lock()
        self.running_downloads -= 1
        if self.queue:
            executor = self.queue.pop(0)
            self.running_downloads += 1
            self.mutex.unlock()
            executor.finished.connect(self.on_executor_finished)
            executor.start()
        else:
            self.mutex.unlock()

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
    def __init__(self, title, item, parent=None):
        super().__init__(parent)
        self.item = item
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(5, 5, 5, 5)
        self.layout.setSpacing(2)

        self.title_label = QLabel(title)
        self.title_label.setWordWrap(True)
        self.layout.addWidget(self.title_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(10)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat('%p%')
        self.layout.addWidget(self.progress_bar)

        self.status_label = QLabel("Waiting...")
        self.status_label.setStyleSheet("font-size: 10px; color: #aaa;")
        self.layout.addWidget(self.status_label)

    def set_title(self, text):
        self.title_label.setToolTip(text)
        self.title_label.setText(text)
        # After setting text, the widget's own sizeHint will change.
        # We need to inform the QListWidgetItem to update its size.
        if self.item:
            self.item.setSizeHint(self.sizeHint())

    def set_progress(self, value):
        self.progress_bar.setValue(value)

    def set_status(self, text, color):
        self.status_label.setText(text)
        self.status_label.setStyleSheet(f"font-size: 10px; color: {color};")

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
        self.VIDEO_COLOR = "#9b59b6" # Brighter Purple
        self.AUDIO_COLOR = "#3498db" # Brighter Blue

        self.VIDEO_QUALITY_MAP = {
            "Highest": "bestvideo+bestaudio/best",
            "High (1080p)": "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
            "Mid (720p)": "bestvideo[height<=720]+bestaudio/best[height<=720]",
            "Low (480p)": "bestvideo[height<=480]+bestaudio/best[height<=480]",
            "Very Low (360p)": "bestvideo[height<=360]+bestaudio/best[height<=360]",
        }
        self.AUDIO_QUALITY_MAP = {
            "Highest": "bestaudio/best",
            "High (~256kbps)": "bestaudio[abr<=256]",
            "Mid (~192kbps)": "bestaudio[abr<=192]",
            "Low (~128kbps)": "bestaudio[abr<=128]",
            "Very Low (~96kbps)": "bestaudio[abr<=96]",
        }
        self.video_quality = self.VIDEO_QUALITY_MAP["Highest"]
        self.audio_quality = self.AUDIO_QUALITY_MAP["Highest"]

        self.check_ffmpeg()
        self.setup_ui()
        self.center_window()
        self.paste_link()

        self.download_queue = DownloadQueue(max_concurrent_downloads=3)
        self.item_counter = 0
        self.queue_list.itemDoubleClicked.connect(self.open_downloaded_file)

    def check_ffmpeg(self):
        self.ffmpeg_checker = FFmpegCheckThread(self)
        self.ffmpeg_checker.finished.connect(self.on_ffmpeg_check_finished)
        self.ffmpeg_checker.finished.connect(self.on_thread_finished)
        self.active_threads.append(self.ffmpeg_checker)
        self.ffmpeg_checker.start()

    def on_ffmpeg_check_finished(self, found):
        if not found:
            msg_box = QMessageBox(self)
            msg_box.setIcon(QMessageBox.Warning)
            msg_box.setText("ffmpeg not found.")
            msg_box.setInformativeText("Please install ffmpeg and ensure it is in your system's PATH.")
            msg_box.setStandardButtons(QMessageBox.Ok)
            msg_box.exec_()

    def setup_ui(self):
        self.background_frame = QFrame(self)
        self.background_frame.setObjectName("background")
        self.apply_shadow(self.background_frame, 20, 5)

        main_layout = QVBoxLayout(self.background_frame)
        main_layout.setContentsMargins(15, 5, 15, 15)

        title_bar_layout = QHBoxLayout()
        icon_label = QLabel()
        icon_pixmap = QPixmap('yt.ico').scaled(24, 24, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        icon_label.setPixmap(icon_pixmap)
        title_label = QLabel("iMA Downloader")
        title_label.setStyleSheet("font-weight: bold;")

        settings_button = QPushButton("⚙️")
        settings_button.setObjectName("settingsBtn")
        settings_button.setFixedSize(28, 28)
        self.settings_menu = QMenu(self)
        settings_button.setMenu(self.settings_menu)
        self.apply_shadow(settings_button)

        video_quality_group = QActionGroup(self)
        video_quality_group.setExclusive(True)
        video_menu = self.settings_menu.addMenu("Video Quality")
        for quality in self.VIDEO_QUALITY_MAP.keys():
            action = QAction(quality, self, checkable=True)
            action.triggered.connect(lambda checked, q=quality: self.set_video_quality(q))
            if self.video_quality == self.VIDEO_QUALITY_MAP[quality]:
                action.setChecked(True)
            video_menu.addAction(action)
            video_quality_group.addAction(action)

        audio_quality_group = QActionGroup(self)
        audio_quality_group.setExclusive(True)
        audio_menu = self.settings_menu.addMenu("Audio Quality")
        for quality in self.AUDIO_QUALITY_MAP.keys():
            action = QAction(quality, self, checkable=True)
            action.triggered.connect(lambda checked, q=quality: self.set_audio_quality(q))
            if self.audio_quality == self.AUDIO_QUALITY_MAP[quality]:
                action.setChecked(True)
            audio_menu.addAction(action)
            audio_quality_group.addAction(action)

        minimize_button = QPushButton("—")
        minimize_button.setObjectName("controlBtn")
        minimize_button.clicked.connect(self.showMinimized)
        close_button = QPushButton("✕")
        close_button.setObjectName("controlBtn")
        close_button.clicked.connect(self.close)

        title_bar_layout.addWidget(icon_label)
        title_bar_layout.addWidget(title_label)
        title_bar_layout.addWidget(settings_button)
        title_bar_layout.addStretch()
        title_bar_layout.addWidget(minimize_button)
        title_bar_layout.addWidget(close_button)
        main_layout.addLayout(title_bar_layout)

        content_layout = QHBoxLayout()
        main_layout.addLayout(content_layout)

        self.queue_list = QListWidget()
        self.queue_list.setFixedWidth(220)
        self.queue_list.setVerticalScrollBar(ModernScrollBar())
        self.queue_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.apply_shadow(self.queue_list)
        content_layout.addWidget(self.queue_list)

        right_layout = QVBoxLayout()
        content_layout.addLayout(right_layout)

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
        self.output_text.setVerticalScrollBar(ModernScrollBar())
        self.output_text.setFixedHeight(120)
        self.apply_shadow(self.output_text)
        right_layout.addWidget(self.output_text)

        outer_layout = QVBoxLayout(self)
        outer_layout.addWidget(self.background_frame)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(outer_layout)

        self.output_dir = os.getcwd()
        self.set_stylesheet()

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
            f"QPushButton#controlBtn {{ background-color: transparent; color: #bfb8dd; border: none; font-size: 14px; font-weight: bold; }}"
            f"QPushButton#controlBtn:hover {{ color: #ff5555; }}"
            f"QPushButton#settingsBtn {{ background-color: transparent; color: #bfb8dd; border: none; font-size: 18px; }}"
            f"QPushButton#settingsBtn::menu-indicator {{ image: none; }}"
            f"QMenu {{ background-color: {self.BG_COLOR}; color: {self.TEXT_COLOR}; border: 1px solid {self.ACCENT_COLOR}; }}"
            f"QMenu::item:selected {{ background-color: {self.VIDEO_COLOR}; }}"
            f"QProgressBar {{ border: none; border-radius: 5px; background-color: {self.BG_COLOR}; text-align: center; color: white; font-size: 10px; font-weight: bold; }}"
            f"QProgressBar::chunk:horizontal[value_is_audio=\"false\"] {{ background-color: {self.VIDEO_COLOR}; border-radius: 5px; }}"
            f"QProgressBar::chunk:horizontal[value_is_audio=\"true\"] {{ background-color: {self.AUDIO_COLOR}; border-radius: 5px; }}"
        )
        self.setStyleSheet(stylesheet)

    def set_video_quality(self, quality):
        self.video_quality = self.VIDEO_QUALITY_MAP[quality]

    def set_audio_quality(self, quality):
        self.audio_quality = self.AUDIO_QUALITY_MAP[quality]

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
            self.on_url_changed(link)

    def on_url_changed(self, url):
        if url.startswith("http"):
            # Clear previous preview info
            self.current_preview_url = None
            self.current_preview_info = {}
            self.thumbnail_label.setPixmap(QPixmap())
            self.title_label.setText("Fetching title...")

            preview_fetcher = ThumbnailFetcher(url, False, -1, self)
            preview_fetcher.thumbnail_loaded.connect(self.set_thumbnail)
            preview_fetcher.info_loaded.connect(self.on_preview_info_loaded)
            preview_fetcher.error_signal.connect(lambda id, err: self.title_label.setText(err) if id == -1 else None)
            preview_fetcher.finished.connect(self.on_thread_finished)
            self.active_threads.append(preview_fetcher)
            preview_fetcher.start()

    def set_thumbnail(self, pixmap):
        self.thumbnail_label.setPixmap(pixmap)

    def add_to_queue(self, is_audio):
        url = self.url_entry.text()
        if not url:
            return

        self.item_counter += 1
        item_id = self.item_counter

        prefix = "🎧" if is_audio else "🎬"
        item = QListWidgetItem(self.queue_list)
        item.setData(Qt.UserRole, item_id)

        widget = DownloadItemWidget(f"{prefix} Starting...", item)
        widget.progress_bar.setProperty("value_is_audio", is_audio)
        self.download_widgets[item_id] = widget

        item.setSizeHint(widget.sizeHint())
        self.queue_list.insertItem(0, item)
        self.queue_list.setItemWidget(item, widget)

        if url == self.current_preview_url and self.current_preview_info:
            title = self.current_preview_info.get('title', 'No title found')
            self.start_download(title, is_audio, url, item_id)
        else:
            widget.set_title(f"{prefix} Fetching info...")
            fetcher = ThumbnailFetcher(url, is_audio, item_id, self)
            # Use a lambda to unpack the info dict and pass the title to start_download
            fetcher.info_loaded.connect(
                lambda info, is_audio, url, item_id: self.start_download(info.get('title', 'No Title'), is_audio, url, item_id)
            )
            fetcher.error_signal.connect(self.on_item_error)
            fetcher.finished.connect(self.on_thread_finished)
            self.active_threads.append(fetcher)
            fetcher.start()

    def start_download(self, title, is_audio, url, item_id):
        if item_id == -1: return

        sanitized_title = sanitize_filename(title)
        prefix = "🎧" if is_audio else "🎬"
        widget = self.download_widgets.get(item_id)
        if widget:
            full_title = f"{prefix} {sanitized_title}"
            widget.set_title(full_title)
            widget.set_status("Preparing...", self.TEXT_COLOR)

        output_template = os.path.join(self.output_dir, '%(title)s.%(ext)s')

        ydl_opts = {
            'outtmpl': output_template,
            'noplaylist': True,
            'no_warnings': True,
            'quiet': True, # We use our own progress reporting
        }

        if is_audio:
            ydl_opts.update({
                'format': self.audio_quality,
                'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3'}],
            })
        else:
            ydl_opts.update({
                'format': self.video_quality,
                'merge_output_format': 'mp4',
            })

        downloader = DownloadThread(url, ydl_opts, item_id, self)
        downloader.item_id_signal.connect(self.on_item_start)
        downloader.progress_signal.connect(self.on_item_progress_update)
        downloader.finished_signal.connect(self.on_item_finished)
        downloader.error_signal.connect(self.on_item_error)
        downloader.finished.connect(self.on_thread_finished)

        self.active_threads.append(downloader)
        downloader.start()

    def on_item_error(self, item_id, error_message):
        if item_id in self.download_widgets:
            widget = self.download_widgets[item_id]
            widget.set_status(f"Error: {error_message[:40]}...", "#ff5555")
            widget.title_label.setToolTip(error_message)


    def on_item_progress_update(self, d):
        item_id = d.get('item_id')
        widget = self.download_widgets.get(item_id)
        if not widget: return

        if d['status'] == 'downloading':
            total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
            if total_bytes > 0:
                percent = (d.get('downloaded_bytes', 0) / total_bytes) * 100
                widget.set_progress(int(percent))

            speed = d.get('speed')
            eta = d.get('eta')
            speed_str = f"{speed / 1024 / 1024:.2f} MiB/s" if speed else "..."
            eta_str = f"{int(eta)}s" if eta is not None else "..."
            widget.set_status(f"{speed_str} | {eta_str}", self.TEXT_COLOR)

        elif d['status'] == 'finished':
            widget.set_status("Finalizing...", "#50fa7b")
            widget.set_progress(100)

    def on_item_start(self, item_id):
        if item_id in self.download_widgets:
            widget = self.download_widgets[item_id]
            widget.set_status("Downloading...", self.TEXT_COLOR)

    def on_item_finished(self, info_dict):
        item_id = info_dict.get('item_id')
        widget = self.download_widgets.get(item_id)
        if widget:
            widget.set_status("Download Complete!", "#50fa7b")
            widget.set_progress(100)

        filepath = info_dict.get('filepath')
        if filepath:
            self.downloaded_files[item_id] = filepath

    def on_preview_info_loaded(self, info, is_audio, url, item_id):
        if item_id == -1:  # This is a preview fetch
            self.title_label.setText(info.get('title', 'No title found'))
            self.current_preview_url = url
            self.current_preview_info = info

    def on_thread_finished(self):
        thread = self.sender()
        if thread and thread in self.active_threads:
            self.active_threads.remove(thread)

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
