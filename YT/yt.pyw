import sys
import os
import platform
import subprocess
import re
import json
import logging
import requests
from PyQt5.QtWidgets import (QApplication, QWidget, QLabel, QLineEdit,
                             QPushButton, QTextEdit, QVBoxLayout, QHBoxLayout,
                             QSizePolicy, QProgressBar, QDesktopWidget, QScrollBar,
                             QListWidget, QListWidgetItem, QMessageBox)
from PyQt5.QtGui import QIcon, QFont, QPixmap, QClipboard, QColor
from PyQt5.QtCore import Qt, QSize, QThread, pyqtSignal, QObject, QMutex, QWaitCondition
import pyperclip

# --- Constants ---
APP_NAME = "iMA Menu: Downloader"
APP_ID = "myappid"  # for Windows taskbar icon

# --- Styles ---
STYLE_SHEET = {
    "MainWindow": "QWidget { background-color: #2b2b2b; }",
    "CustomLabel": "QLabel { border-radius: 10px; background-color: #444; min-width: 200px; max-width: 300px; }",
    "TitleLabel": "QLabel { color: white; }",
    "URLLabel": "QLabel { color: white; }",
    "QLineEdit": "QLineEdit { background-color: #444; color: white; border: 3px solid #555; border-radius: 10px; padding: 5px; } QLineEdit:focus { border: 3px solid teal; }",
    "QPushButton_Paste": "QPushButton { background-color: #444; color: white; border: 3px solid teal; border-radius: 10px; padding: 1px; max-width: 30px; min-width: 30px; font-size: 18px; } QPushButton:hover { background-color: teal; } QPushButton:pressed{background-color: teal; } QPushButton:focus { border: 3px solid teal; }",
    "QPushButton": "QPushButton { background-color: #444; color: white; border: 3px solid %button_color%; border-radius: 10px; padding: 10px 20px; font-size: 14px; min-width: 150px;} QPushButton:hover { background-color: %button_color%; border: 2px solid %button_color%; } QPushButton:pressed{background-color: %button_color%; border: 3px solid %button_color%;}",
    "QProgressBar": "QProgressBar { border: 3px solid #555; border-radius: 10px; background-color: #333; text-align: center; color: white; font-size: 14px; height: 20px;} QProgressBar::chunk { background-color: %color%; margin: 1px; border-radius: 9px; }",
    "QTextEdit": "QTextEdit { background-color: #333; color: lightgray; border: 1px solid #555; border-radius: 10px; padding: 5px; } QTextEdit:focus {border: 3px teal;} ",
    "StatusLabel": "QLabel { color: white; font-style: italic; }",
    "QueueListWidget": """
        QListWidget {
            background-color: #333;
            color: white;
            border: none;
            outline: 0;
        }
        QListWidget::item {
            background-color: #444;
            border-radius: 10px;
            padding: 10px;
            margin: 5px;
            color: white;
            box-shadow: 2px 2px 5px rgba(0, 0, 0, 0.5);
        }
        QListWidget::item:selected, QListWidget::item:hover {
            background-color: #555;
        }
    """,
    "ModernScrollBar": """
        QScrollBar:vertical { background-color: transparent; width: 10px; margin: 0px 0px 0px 0px; border-radius: 10px; }
        QScrollBar::handle:vertical { background-color: rgba(80, 80, 80, 150); min-height: 20px; border-radius: 10px; }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { background: none; }
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical{ background: none; border-radius: 10px;}
    """
}

# --- Colors ---
VIDEO_BUTTON_COLOR = "#3e284f"
AUDIO_BUTTON_COLOR = "#28528d"
STATUS_SUCCESS_COLOR = "green"
STATUS_FAIL_COLOR = "red"
STATUS_DOWNLOAD_COLOR = "yellow"

# --- Settings ---
MAX_CONCURRENT_DOWNLOADS = 2
THUMBNAIL_SIZE = (200, 300)
# --- End Constants ---

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def is_windows():
    return platform.system() == "Windows"

class CommandExecutor(QThread):
    output_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool)
    progress_signal = pyqtSignal(int)
    item_id_signal = pyqtSignal(int)

    def __init__(self, command, item_id, parent=None):
        super().__init__(parent)
        self.command = command
        self.item_id = item_id
        self.process = None

    def run(self):
        self.item_id_signal.emit(self.item_id)
        try:
            creation_flags = subprocess.CREATE_NO_WINDOW if is_windows() else 0
            self.process = subprocess.Popen(self.command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True, creationflags=creation_flags)
            for line in iter(self.process.stdout.readline, ''):
                self.output_signal.emit(line)
                match = re.search(r'\[download\]\s+(\d+(\.\d+)?)%', line)
                if match:
                    self.progress_signal.emit(int(float(match.group(1))))
            self.process.wait()
            if self.process.returncode != 0:
                self.output_signal.emit(f"\nError: Command exited with code {self.process.returncode}\n")
            self.finished_signal.emit(self.process.returncode == 0)
        except Exception as e:
             logging.error(f"Failed to execute command: {e}")
             self.output_signal.emit(f"\nAn error occurred: {e}\n")
             self.finished_signal.emit(False)
        finally:
            if self.process and self.process.stdout:
                self.process.stdout.close()

def get_clipboard_link():
    try:
        clipboard_content = pyperclip.paste()
        return clipboard_content if clipboard_content.startswith("http") else ""
    except Exception as e:
         logging.warning(f"Could not get clipboard content: {e}")
         return ""

class ThumbnailFetcher(QThread):
    thumbnail_loaded = pyqtSignal(QPixmap)
    title_loaded = pyqtSignal(str, bool)
    error_signal = pyqtSignal(str)

    def __init__(self, url, is_audio, parent=None):
        super().__init__(parent)
        self.url = url
        self.is_audio = is_audio

    def run(self):
        try:
            command = ["yt-dlp", "--no-warnings", "--playlist-items", "1", "-j", self.url]
            creation_flags = subprocess.CREATE_NO_WINDOW if is_windows() else 0
            info_process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True, creationflags=creation_flags)
            info_out, _ = info_process.communicate()

            if info_process.returncode != 0:
                self.error_signal.emit(f"yt-dlp failed with code {info_process.returncode}")
                return

            info_json = json.loads(info_out)
            title = info_json.get('title', 'No title found')
            self.title_loaded.emit(title, self.is_audio)
            thumbnail_url = info_json.get('thumbnail')

            if not thumbnail_url:
                self.error_signal.emit("No thumbnail URL found")
                return

            response = requests.get(thumbnail_url, stream=True)
            response.raise_for_status()
            pixmap = QPixmap()
            pixmap.loadFromData(response.content)
            if not pixmap.isNull():
                pixmap = pixmap.scaled(THUMBNAIL_SIZE[0], THUMBNAIL_SIZE[1], Qt.KeepAspectRatio)
                self.thumbnail_loaded.emit(pixmap)
            else:
                self.error_signal.emit("Failed to load pixmap from downloaded data")

        except json.JSONDecodeError:
            self.error_signal.emit("Could not decode json from yt-dlp")
        except requests.RequestException as e:
            self.error_signal.emit(f"Failed to download thumbnail: {e}")
        except Exception as e:
            self.error_signal.emit(f"Error loading thumbnail: {e}")

class CustomLabel(QLabel):
    def set_pixmap(self, pixmap):
       self.setPixmap(pixmap)

class ModernScrollBar(QScrollBar):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(STYLE_SHEET["ModernScrollBar"])

class DownloadQueue(QObject):
    def __init__(self, max_concurrent_downloads=MAX_CONCURRENT_DOWNLOADS):
        super().__init__()
        self.queue = []
        self.running_downloads = 0
        self.max_concurrent_downloads = max_concurrent_downloads
        self.mutex = QMutex()

    def start_download(self, executor):
        self.mutex.lock()
        self.queue.append(executor)
        self.mutex.unlock()
        self.try_start_next()

    def try_start_next(self):
        self.mutex.lock()
        while self.running_downloads < self.max_concurrent_downloads and self.queue:
            executor = self.queue.pop(0)
            self.running_downloads += 1
            executor.finished_signal.connect(self.on_download_finished)
            executor.start()
        self.mutex.unlock()

    def on_download_finished(self):
        self.mutex.lock()
        self.running_downloads -= 1
        self.mutex.unlock()
        self.try_start_next()

class QueueListWidget(QListWidget):
    itemDoubleClickedSignal = pyqtSignal(QListWidgetItem)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(STYLE_SHEET["QueueListWidget"])
        self.itemDoubleClicked.connect(self.itemDoubleClickedSignal.emit)

    def addItem(self, text):
        item = QListWidgetItem(text)
        item.setSizeHint(QSize(200, 50))
        super().addItem(item)

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.setStyleSheet(STYLE_SHEET["MainWindow"])

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # Left side (Queue)
        self.queue_list = QueueListWidget()
        self.queue_list.setFixedWidth(250)
        main_layout.addWidget(self.queue_list)

        # Right side (Controls)
        right_layout = QVBoxLayout()
        main_layout.addLayout(right_layout)

        self.thumbnail_label = CustomLabel()
        self.thumbnail_label.setFixedSize(100, 100)
        self.thumbnail_label.setAlignment(Qt.AlignCenter)
        self.thumbnail_label.setStyleSheet(STYLE_SHEET["CustomLabel"])
        thumbnail_layout = QHBoxLayout()
        thumbnail_layout.setAlignment(Qt.AlignCenter)
        thumbnail_layout.addWidget(self.thumbnail_label)
        right_layout.addLayout(thumbnail_layout)

        self.title_label = QLabel("")
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setStyleSheet(STYLE_SHEET["TitleLabel"])
        self.title_label.setWordWrap(True)
        right_layout.addWidget(self.title_label)

        url_layout = QHBoxLayout()
        url_label = QLabel("URL:")
        url_label.setStyleSheet(STYLE_SHEET["URLLabel"])
        url_layout.addWidget(url_label)
        self.url_entry = QLineEdit()
        self.url_entry.setStyleSheet(STYLE_SHEET["QLineEdit"])
        self.url_entry.mousePressEvent = lambda event: self.url_entry.selectAll()
        self.url_entry.textChanged.connect(self.fetch_thumbnail)
        url_layout.addWidget(self.url_entry)
        self.paste_button = QPushButton("📋")
        self.paste_button.setStyleSheet(STYLE_SHEET["QPushButton_Paste"])
        self.paste_button.clicked.connect(self.paste_link)
        url_layout.addWidget(self.paste_button)
        right_layout.addLayout(url_layout)

        button_layout = QHBoxLayout()
        button_layout.setAlignment(Qt.AlignCenter)
        self.download_video_button = QPushButton("🎬 Download Video")
        self.download_video_button.clicked.connect(self.add_video_to_queue)
        self.set_button_style(self.download_video_button, VIDEO_BUTTON_COLOR)
        button_layout.addWidget(self.download_video_button)
        self.download_audio_button = QPushButton("🎧 Download Audio")
        self.download_audio_button.clicked.connect(self.add_audio_to_queue)
        self.set_button_style(self.download_audio_button, AUDIO_BUTTON_COLOR)
        button_layout.addWidget(self.download_audio_button)
        right_layout.addLayout(button_layout)

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(20)
        self.progress_bar.setStyleSheet(STYLE_SHEET["QProgressBar"].replace("%color%", "transparent"))
        self.progress_bar.setValue(0)
        right_layout.addWidget(self.progress_bar)

        self.output_text = QTextEdit()
        self.output_text.setStyleSheet(STYLE_SHEET["QTextEdit"])
        self.output_text.setVerticalScrollBar(ModernScrollBar())
        self.output_text.setFixedHeight(80)
        right_layout.addWidget(self.output_text)

        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet(STYLE_SHEET["StatusLabel"])
        right_layout.addWidget(self.status_label)

        self.output_dir = os.getcwd()
        self.download_queue = DownloadQueue()
        self.item_counter = 0
        self.queue_list.itemDoubleClickedSignal.connect(self.open_downloaded_file)

        self.center_window()
        self.paste_link()

    def set_button_style(self, button, color):
        button.setStyleSheet(STYLE_SHEET["QPushButton"].replace("%button_color%", color))

    def paste_link(self):
        link = get_clipboard_link()
        if link:
            self.url_entry.setText(link)

    def fetch_thumbnail(self, url):
        if url.startswith("http"):
            self.thumbnail_fetcher = ThumbnailFetcher(url, False, self)
            self.thumbnail_fetcher.thumbnail_loaded.connect(self.thumbnail_label.set_pixmap)
            self.thumbnail_fetcher.title_loaded.connect(self.update_title_label)
            self.thumbnail_fetcher.error_signal.connect(lambda error: logging.warning(f"Thumbnail error: {error}"))
            self.thumbnail_fetcher.start()

    def update_title_label(self, title, is_audio):
        self.title_label.setText(title)

    def add_to_queue(self, is_audio):
        url = self.url_entry.text()
        if not url:
            return
        self.item_counter += 1
        item_id = self.item_counter
        item_text = f"Audio: {url}" if is_audio else f"Video: {url}"
        self.queue_list.addItem(item_text)
        self.fetch_video_title(url, item_id, is_audio)
        self.start_download(url, item_id, is_audio)

    def add_video_to_queue(self):
        self.add_to_queue(is_audio=False)

    def add_audio_to_queue(self):
        self.add_to_queue(is_audio=True)

    def start_download(self, url, item_id, is_audio):
        if is_audio:
            command = ["yt-dlp", "--no-warnings", "--no-playlist", "-x", "--audio-format", "mp3", url, "-o", os.path.join(self.output_dir, "%(title)s.%(ext)s")]
            progress_color = AUDIO_BUTTON_COLOR
            status_text = "Downloading Audio..."
        else:
            command = ["yt-dlp", "--no-warnings", "--no-playlist", url, "-f", "bv*+ba/b", "--merge-output-format", "mp4", "-o", os.path.join(self.output_dir, "%(title)s.%(ext)s")]
            progress_color = VIDEO_BUTTON_COLOR
            status_text = "Downloading Video..."

        executor = CommandExecutor(command, item_id, self)
        executor.output_signal.connect(self.update_output)
        executor.finished_signal.connect(self.handle_command_completion)
        executor.progress_signal.connect(self.progress_bar.setValue)
        executor.item_id_signal.connect(self.on_item_start)
        executor.finished_signal.connect(self.on_item_finished)

        self.status_label.setText(status_text)
        self.status_label.setStyleSheet(f"color: {STATUS_DOWNLOAD_COLOR};")
        self.progress_bar.setStyleSheet(STYLE_SHEET["QProgressBar"].replace("%color%", progress_color))
        self.progress_bar.setValue(0)
        self.download_queue.start_download(executor)

    def update_output(self, line):
        self.output_text.insertPlainText(line)
        self.output_text.verticalScrollBar().setValue(self.output_text.verticalScrollBar().maximum())

    def handle_command_completion(self, success):
        self.status_label.setText("Download Complete!" if success else "Download Failed.")
        self.status_label.setStyleSheet(f"color: {STATUS_SUCCESS_COLOR if success else STATUS_FAIL_COLOR};")
        self.progress_bar.setValue(0)

    def on_item_start(self, item_id):
        item = self.queue_list.item(item_id - 1)
        if item:
            item.setBackground(QColor(VIDEO_BUTTON_COLOR if "Video" in item.text() else AUDIO_BUTTON_COLOR))

    def on_item_finished(self, success):
        # This needs a way to identify which item finished.
        # For now, let's assume one at a time for simplicity of this part.
        pass

    def fetch_video_title(self, url, item_id, is_audio):
        self.thumbnail_fetcher = ThumbnailFetcher(url, is_audio, self)
        self.thumbnail_fetcher.title_loaded.connect(lambda title, audio: self.update_queue_item(item_id, title, audio))
        self.thumbnail_fetcher.start()

    def update_queue_item(self, item_id, title, is_audio):
        item = self.queue_list.item(item_id - 1)
        if item:
            item.setText(f"Audio: {title}" if is_audio else f"Video: {title}")

    def center_window(self):
      qr = self.frameGeometry()
      cp = QDesktopWidget().availableGeometry().center()
      qr.moveCenter(cp)
      self.move(qr.topLeft())

    def open_downloaded_file(self, item):
         item_text = item.text()
         title = item_text.split(": ", 1)[1]
         filepath = None
         for filename in os.listdir(self.output_dir):
            if title in filename:
                 filepath = os.path.join(self.output_dir, filename)
                 if os.path.isfile(filepath):
                      break
         if filepath:
            try:
                 if is_windows():
                      os.startfile(filepath)
                 else:
                      subprocess.Popen(['xdg-open', filepath])
            except Exception as e:
                 QMessageBox.critical(self, "Error", f"Could not open file:\n{e}")
         else:
            QMessageBox.warning(self, "Warning", "File not found in the download directory.")

if __name__ == '__main__':
    if is_windows():
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
