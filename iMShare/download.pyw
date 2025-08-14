import sys
import os
import platform
import subprocess
import time
import uuid
import re
import json
from queue import Queue
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QPushButton,
    QTextEdit, QVBoxLayout, QHBoxLayout, QProgressBar,
    QDesktopWidget, QFrame, QListWidget, QListWidgetItem,
    QAbstractItemView, QSizePolicy, QDialog, QGridLayout,
    QScrollArea, QScrollBar, QGraphicsDropShadowEffect, QFileDialog, QMenu)
from PyQt5.QtGui import (
    QColor, QPainter, QBrush, QLinearGradient, QFont, QPixmap, QRegion, QPolygon, QPainterPath,
    QPen, QImage, QDesktopServices, QIcon)
from PyQt5.QtCore import (
    Qt, pyqtSignal, QTimer, QPoint, QThreadPool, QRunnable, QObject, QUrl, QThread)

# --- INSTANCE HANDLING ---
def is_windows():
    return platform.system() == "Windows"

def get_app_data_dir():
    try:
        if is_windows():
            app_data_path = os.path.join(os.environ['LOCALAPPDATA'], 'iMShare')
        elif platform.system() == "Darwin":
            app_data_path = os.path.join(os.path.expanduser('~/Library/Application Support'), 'iMShare')
        else:
            app_data_path = os.path.join(os.path.expanduser('~/.local/share'), 'iMShare')
        os.makedirs(app_data_path, exist_ok=True)
        return app_data_path
    except (OSError, KeyError) as e:
        print(f"Error: Could not create or access app data directory: {e}")
        return None

def handle_instance_check():
    app_data_dir = get_app_data_dir()
    if not app_data_dir:
        return
    lock_file_path = os.path.join(app_data_dir, 'imshare_download.lock')
    if os.path.exists(lock_file_path):
        try:
            with open(lock_file_path, 'r') as f:
                pid = int(f.read().strip())
            if is_windows():
                subprocess.run(['taskkill', '/F', '/PID', str(pid)], capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
            else:
                subprocess.run(['kill', '-9', str(pid)], capture_output=True)
        except (ValueError, FileNotFoundError, OSError) as e:
            print(f"Error handling lock file: {e}")
    try:
        with open(lock_file_path, 'w') as f:
            f.write(str(os.getpid()))
    except OSError as e:
        print(f"Error writing new lock file: {e}")

# --- END OF INSTANCE HANDLING ---

def resource_path(relative_path):
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

def set_drop_shadow(widget, blur_radius=10, offset_x=4, offset_y=4, opacity=150):
    shadow = QGraphicsDropShadowEffect()
    shadow.setBlurRadius(blur_radius)
    shadow.setColor(QColor(0, 0, 0, opacity))
    shadow.setOffset(offset_x, offset_y)
    widget.setGraphicsEffect(shadow)

def create_circular_thumbnail(image_path, size):
    image = None 
    try:
        if image_path and os.path.exists(image_path): 
            temp_image = QImage(image_path)
            if not temp_image.isNull(): 
                image = temp_image
    except Exception:
        pass 
    if image is None: 
        image = QImage(resource_path("iMShare.png"))
    scaled_image = image.scaled(size, size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
    x = (scaled_image.width() - size) // 2
    y = (scaled_image.height() - size) // 2
    cropped_image = scaled_image.copy(x, y, size, size)
    thumbnail = QPixmap(size, size)
    thumbnail.fill(Qt.transparent)
    painter = QPainter(thumbnail)
    painter.setRenderHint(QPainter.Antialiasing, True)
    path = QPainterPath()
    path.addEllipse(0, 0, size, size)
    painter.setClipPath(path)
    painter.drawPixmap(0, 0, QPixmap.fromImage(cropped_image))
    painter.end()
    return thumbnail

class WorkerSignals(QObject):
    output_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool, str, str)
    progress_signal = pyqtSignal(int)
    speed_signal = pyqtSignal(str)
    hashing_progress_signal = pyqtSignal(int)
    hashing_finished_signal = pyqtSignal()
    status_update_signal = pyqtSignal(str, str)
    time_remaining_signal = pyqtSignal(str)
    current_file_signal = pyqtSignal(str, str)
    file_name_size_signal = pyqtSignal(str,str,str)

class DownloadWorker(QRunnable):
    def __init__(self, code_prefix, parent=None, queue_id=None):
        super().__init__()
        self.signals = WorkerSignals()
        self.code_prefix = code_prefix
        self.process = None
        self.is_hashing = True
        self.hashing_complete = False
        self.queue_id = queue_id
        self.filename = "File"
        self.filesize = "N/A"
        self.full_file_path = None
        self.path_exists = False
        self.total_files = 1
        self.current_file_index = 0
        self.download_dir = None

    def run(self):
        try:
            command = f'croc --yes {self.code_prefix}'
            full_command = ["powershell", "-Command", command] if is_windows() else ["croc", "--yes", self.code_prefix]
            self.process = subprocess.Popen(full_command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                            universal_newlines=True, creationflags=subprocess.CREATE_NO_WINDOW if is_windows() else 0)
            self.signals.current_file_signal.emit(self.filename, self.filesize)
            output = ""
            while True:
                line = self.process.stdout.readline()
                if not line:
                    break
                output += line
                self.signals.output_signal.emit(line)
                self.parse_output_line(line)
            self.process.wait()
            if self.process.returncode != 0:
                status = "Not Ready" if "not ready" in output else "Failed"
                self.signals.finished_signal.emit(False, self.queue_id, status)
            else:
                self.signals.finished_signal.emit(True, self.queue_id, "Complete!")
        except FileNotFoundError:
            self.signals.output_signal.emit("\nError: 'croc' or 'powershell' not found. Please ensure they are installed and in the system's PATH.\n")
            self.signals.finished_signal.emit(False, self.queue_id, "Failed")
        except Exception as e:
            self.signals.output_signal.emit(f"\nAn unexpected error occurred: {e}\n")
            self.signals.finished_signal.emit(False, self.queue_id, "Failed")

    def parse_output_line(self, line):
        if initial_summary_match := re.match(r'Receiving (\d+) files \((.+)\)', line):
            self.total_files = int(initial_summary_match.group(1))
            self.filesize = initial_summary_match.group(2).strip()
            self.filename = f"Receiving {self.total_files} files"
            self.signals.file_name_size_signal.emit(self.filename, self.filesize, self.queue_id)
            self.signals.current_file_signal.emit(self.filename, self.filesize)
        elif accept_match := re.search(r"Accept '(.+)' \((.+)\)\?", line):
            self.filename = accept_match.group(1).strip()
            self.filesize = accept_match.group(2).strip()
            self.signals.file_name_size_signal.emit(self.filename, self.filesize, self.queue_id)
            self.signals.current_file_signal.emit(self.filename, self.filesize)
        elif folder_name_match := re.match(r'(.+?)\\', line):
            self.download_dir = folder_name_match.group(1).strip()
            self.full_file_path = os.path.join(os.getcwd(), self.download_dir)
            self.path_exists = os.path.isdir(self.full_file_path)
            self.filename = self.download_dir
            self.signals.file_name_size_signal.emit(self.filename, self.filesize, self.queue_id)
            self.signals.current_file_signal.emit(self.filename, self.filesize)
        elif uploading_match := re.match(r'(.+?)\s+(\d+)%\s+\|(.+?)\|\s+\((.+?),\s*(.+?)\)\s+(\d+)/(\d+)', line):
            filename, progress, _, _, speed, current_file_index, total_files = uploading_match.groups()
            self.filename = filename.strip()
            self.current_file_index = int(current_file_index)
            self.total_files = int(total_files)
            current_file_progress = int(progress)
            if self.total_files > 1:
                progress_per_file = 100 / self.total_files
                completed_files_progress = (self.current_file_index - 1) * progress_per_file
                current_file_contribution = (current_file_progress / 100) * progress_per_file
                overall_progress = completed_files_progress + current_file_contribution
                self.signals.progress_signal.emit(int(overall_progress))
            else:
                self.signals.progress_signal.emit(current_file_progress)
            self.signals.speed_signal.emit(speed.strip())
            self.is_hashing = False
            self.signals.status_update_signal.emit("Downloading...", "yellow")
            self.signals.time_remaining_signal.emit("")
        elif file_created := re.search(r'file: (.+)', line):
            full_file_path = file_created.group(1).strip()
            if os.path.exists(full_file_path):
                self.full_file_path = full_file_path
                self.path_exists = True
            else:
                self.full_file_path = None
                self.path_exists = False

    def close_process(self):
        if self.process and self.process.poll() is None:
            if is_windows():
                self.process.terminate()
                try:
                    self.process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    kill_command = ['taskkill', '/F', '/T', '/PID', str(self.process.pid)]
                    subprocess.Popen(kill_command, creationflags=subprocess.CREATE_NO_WINDOW)
            else:
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()

def update_output(output_widget, line):
    output_widget.insertPlainText(line)
    output_widget.verticalScrollBar().setValue(output_widget.verticalScrollBar().maximum())

def handle_command_completion(success, status_label, progress_bar, window, queue_id, status_message):
    window.dot_animation_timer.stop()
    status_property = "success" if success else "error"
    window.show_status_message(status_message, status_property)
    window.speed_label.setText("")
    progress_bar.setValue(0)
    window.is_sending = False
    if success:
        window.update_queue_item_status(queue_id, "Complete!")
    else:
        window.remove_queue_item(queue_id)
    window.process_pending_queue()

class ClickableImageLabel(QLabel):
    clicked = pyqtSignal()
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.PointingHandCursor)
        self.is_hovered = False

    def enterEvent(self, event):
        self.is_hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.is_hovered = False
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        color = QColor("white") if self.is_hovered else QColor("#AAAAAA")
        pen = QPen(color, 2)
        pen.setStyle(Qt.DotLine)
        painter.setPen(pen)
        painter.drawEllipse(self.rect().adjusted(1, 1, -1, -1))

class ModernScrollBar(QScrollBar):
    def __init__(self, parent=None):
        super().__init__(parent)

class TitleBar(QWidget):
    def __init__(self, parent_window, parent=None):
        super().__init__(parent)
        self.parent_window = parent_window
        self.start_move_position = None
        self.window_position = None

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.start_move_position = event.globalPos()
            self.window_position = self.parent_window.pos()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self.start_move_position is not None:
            delta = event.globalPos() - self.start_move_position
            self.parent_window.move(self.window_position + delta)
            event.accept()

    def mouseReleaseEvent(self, event):
        self.start_move_position = None
        event.accept()

class ThumbnailSignals(QObject):
    finished = pyqtSignal(QPixmap)

class ThumbnailWorker(QRunnable):
    def __init__(self, image_path, size):
        super().__init__()
        self.image_path = image_path
        self.size = size
        self.signals = ThumbnailSignals()

    def run(self):
        pixmap = create_circular_thumbnail(self.image_path, self.size)
        self.signals.finished.emit(pixmap)

class FriendWidget(QWidget):
    def __init__(self, friend_data, parent=None):
        super().__init__(parent)
        self.friend_data = friend_data
        self.main_window = parent
        self.setFixedSize(75, 100)
        self.setCursor(Qt.PointingHandCursor)
        self.pixmap = create_circular_thumbnail(None, 70)
        self.is_hovered = False
        image_filename = self.friend_data.get("image")
        full_image_path = None
        if image_filename:
            full_image_path = os.path.join(self.main_window.friend_icons_path, image_filename)
        if full_image_path:
            worker = ThumbnailWorker(full_image_path, 70)
            worker.signals.finished.connect(self.set_pixmap)
            self.main_window.thread_pool.start(worker)

    def set_pixmap(self, pixmap):
        self.pixmap = pixmap
        self.update()

    def enterEvent(self, event):
        self.is_hovered = True
        self.update()

    def leaveEvent(self, event):
        self.is_hovered = False
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        path = QPainterPath()
        path.addEllipse(2, 2, 70, 70)
        painter.setClipPath(path)
        painter.drawPixmap(2, 2, self.pixmap)
        painter.setClipping(False)
        pen = QPen(QColor("#00BFFF"), 2) if self.is_hovered else QPen(QColor("#008080"), 1)
        painter.setPen(pen)
        painter.drawEllipse(2, 2, 70, 70)
        font = QFont("Arial", 9)
        font.setBold(True)
        painter.setFont(font)
        friend_name = self.friend_data.get("name", "Name")
        outline_color = QColor("black")
        painter.setPen(outline_color)
        painter.drawText(self.rect().translated(-1, -1), Qt.AlignBottom | Qt.AlignHCenter, friend_name)
        painter.drawText(self.rect().translated(1, -1), Qt.AlignBottom | Qt.AlignHCenter, friend_name)
        painter.drawText(self.rect().translated(-1, 1), Qt.AlignBottom | Qt.AlignHCenter, friend_name)
        painter.drawText(self.rect().translated(1, 1), Qt.AlignBottom | Qt.AlignHCenter, friend_name)
        painter.setPen(QColor("white"))
        painter.drawText(self.rect(), Qt.AlignBottom | Qt.AlignHCenter, friend_name)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.main_window.execute_croc_command(self.friend_data.get("download_code", ""))
        elif event.button() == Qt.RightButton:
            self.main_window.show_friend_context_menu(self, self.friend_data)

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        MainWindow.setObjectName("MainWindow")
        MainWindow.setWindowTitle("iMShare")
        MainWindow.setMinimumSize(800, 500)
        MainWindow.title_bar_height = 30
        MainWindow.setWindowFlag(Qt.FramelessWindowHint)
        main_layout = QVBoxLayout(MainWindow)
        main_layout.setContentsMargins(0, 0, 0, 0)
        MainWindow.title_bar = TitleBar(MainWindow, MainWindow)
        MainWindow.title_bar.setFixedHeight(MainWindow.title_bar_height)
        MainWindow.title_bar.setAttribute(Qt.WA_StyledBackground, True)
        MainWindow.title_bar_gradient = QLinearGradient(0, 0, MainWindow.width(), MainWindow.title_bar_height)
        MainWindow.title_bar_gradient.setColorAt(0, QColor("#141415"))
        MainWindow.title_bar_gradient.setColorAt(1, QColor("#232324ff"))
        MainWindow.title_bar_palette = MainWindow.title_bar.palette()
        MainWindow.title_bar_palette.setBrush(MainWindow.title_bar.backgroundRole(), QBrush(MainWindow.title_bar_gradient))
        MainWindow.title_bar.setPalette(MainWindow.title_bar_palette)
        MainWindow.title_bar.setAutoFillBackground(True)
        title_layout = QHBoxLayout(MainWindow.title_bar)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(0)
        main_layout.addWidget(MainWindow.title_bar)
        title_layout.addSpacing(90)
        MainWindow.title_label = QLabel("iMShare")
        MainWindow.title_label.setObjectName("title_label")
        MainWindow.title_label.setAlignment(Qt.AlignCenter)
        font = QFont()
        font.setBold(True)
        MainWindow.title_label.setFont(font)
        title_layout.addWidget(MainWindow.title_label)
        MainWindow.title_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        MainWindow.minimize_button = QPushButton("▬")
        MainWindow.minimize_button.setObjectName("minimize_button")
        MainWindow.minimize_button.setFixedSize(30,30)
        MainWindow.minimize_button.clicked.connect(MainWindow.showMinimized)
        title_layout.addWidget(MainWindow.minimize_button)
        MainWindow.close_button = QPushButton("⬤")
        MainWindow.close_button.setObjectName("close_button")
        MainWindow.close_button.setFixedSize(30,30)
        MainWindow.close_button.clicked.connect(MainWindow.close)
        title_layout.addWidget(MainWindow.close_button)
        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(20, 5, 20, 20)
        queue_area_layout = QVBoxLayout()
        MainWindow.queue_layout = QVBoxLayout()
        MainWindow.queue_layout.setAlignment(Qt.AlignTop)
        MainWindow.file_queue_list = QListWidget()
        MainWindow.file_queue_list.setObjectName("file_queue_list")
        MainWindow.file_queue_list.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        MainWindow.file_queue_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        MainWindow.file_queue_list.setVerticalScrollBar(ModernScrollBar())
        MainWindow.file_queue_list.setMaximumWidth(200)
        MainWindow.file_queue_list.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        MainWindow.file_queue_list.itemDoubleClicked.connect(MainWindow.handle_queue_item_click)
        MainWindow.queue_layout.addWidget(MainWindow.file_queue_list)
        queue_area_layout.addLayout(MainWindow.queue_layout)
        content_layout.addLayout(queue_area_layout)
        main_content_layout = QVBoxLayout()
        main_content_layout.setAlignment(Qt.AlignTop)
        MainWindow.file_info_layout = QVBoxLayout()
        MainWindow.file_name_label = QLabel("")
        MainWindow.file_name_label.setStyleSheet("color: white; font-size: 14px; font-weight: bold;")
        MainWindow.file_name_label.setAlignment(Qt.AlignLeft)
        MainWindow.file_info_layout.addWidget(MainWindow.file_name_label)
        MainWindow.file_size_label = QLabel("")
        MainWindow.file_size_label.setObjectName("file_size_label")
        MainWindow.file_size_label.setAlignment(Qt.AlignCenter)
        MainWindow.file_info_layout.addWidget(MainWindow.file_size_label)
        file_info_wrapper_layout = QHBoxLayout()
        file_info_wrapper_layout.addSpacing(130)
        file_info_wrapper_layout.addLayout(MainWindow.file_info_layout)
        file_info_wrapper_layout.addStretch(1)
        main_content_layout.addLayout(file_info_wrapper_layout)
        input_action_layout = QHBoxLayout()
        input_action_layout.setAlignment(Qt.AlignLeft)
        path_label = QLabel("Code:")
        path_label.setStyleSheet("color: white;")
        input_action_layout.addWidget(path_label)
        MainWindow.path_entry = QLineEdit()
        MainWindow.path_entry.setObjectName("path_entry")
        MainWindow.path_entry.mousePressEvent = MainWindow.select_all_text
        input_action_layout.addWidget(MainWindow.path_entry, stretch=1)
        MainWindow.download_file_button = QPushButton("Download")
        MainWindow.download_file_button.setObjectName("download_file_button")
        MainWindow.download_file_button.clicked.connect(MainWindow.start_download)
        input_action_layout.addWidget(MainWindow.download_file_button)
        MainWindow.clear_path_button = QPushButton("🗑")
        MainWindow.clear_path_button.setObjectName("clear_path_button")
        MainWindow.clear_path_button.clicked.connect(MainWindow.clear_all)
        MainWindow.clear_path_button.setFixedWidth(30)
        input_action_layout.addWidget(MainWindow.clear_path_button)
        main_content_layout.addLayout(input_action_layout)
        MainWindow.progress_bar = QProgressBar()
        MainWindow.progress_bar.setObjectName("progress_bar")
        MainWindow.progress_bar.setFixedHeight(20)
        MainWindow.progress_bar.setValue(0)
        main_content_layout.addWidget(MainWindow.progress_bar)
        MainWindow.progress_info_layout = QHBoxLayout()
        MainWindow.progress_info_layout.setAlignment(Qt.AlignCenter)
        MainWindow.time_remaining_label = QLabel("")
        MainWindow.time_remaining_label.setObjectName("time_remaining_label")
        MainWindow.time_remaining_label.setAlignment(Qt.AlignCenter)
        MainWindow.progress_info_layout.addWidget(MainWindow.time_remaining_label)
        MainWindow.speed_label = QLabel("")
        MainWindow.speed_label.setObjectName("speed_label")
        MainWindow.speed_label.setAlignment(Qt.AlignCenter)
        MainWindow.progress_info_layout.addWidget(MainWindow.speed_label)
        main_content_layout.addLayout(MainWindow.progress_info_layout)
        MainWindow.friends_scroll_area = QScrollArea()
        MainWindow.friends_scroll_area.setObjectName("friends_scroll_area")
        MainWindow.friends_scroll_area.setWidgetResizable(True)
        MainWindow.friends_scroll_area.setFrameShape(QFrame.NoFrame)
        MainWindow.friends_scroll_area.setVerticalScrollBar(ModernScrollBar())
        MainWindow.friends_container = QWidget()
        MainWindow.friends_container.setObjectName("friends_container")
        MainWindow.friends_container_layout = QGridLayout(MainWindow.friends_container)
        MainWindow.friends_container_layout.setAlignment(Qt.AlignTop)
        MainWindow.friends_container_layout.setContentsMargins(10, 10, 10, 10)
        MainWindow.friends_scroll_area.setWidget(MainWindow.friends_container)
        main_content_layout.addWidget(MainWindow.friends_scroll_area)
        MainWindow.add_friend_button = MainWindow.create_add_button()
        MainWindow.add_friend_button.setObjectName("add_friend_button")
        MainWindow.friends_container_layout.addWidget(MainWindow.add_friend_button, 0, 0)
        MainWindow.status_frame = QFrame()
        MainWindow.status_frame.setObjectName("status_frame")
        MainWindow.status_layout = QHBoxLayout(MainWindow.status_frame)
        MainWindow.output_expand_button = QPushButton("v")
        MainWindow.output_expand_button.setObjectName("output_expand_button")
        MainWindow.output_expand_button.setFixedSize(30, 30)
        MainWindow.output_expand_button.clicked.connect(MainWindow.toggle_output)
        MainWindow.status_layout.addWidget(MainWindow.output_expand_button, alignment=Qt.AlignLeft)
        MainWindow.status_label = QLabel("")
        MainWindow.status_label.setObjectName("status_label")
        MainWindow.status_label.setAlignment(Qt.AlignCenter)
        MainWindow.status_layout.addWidget(MainWindow.status_label, stretch=1)
        main_content_layout.addWidget(MainWindow.status_frame)
        MainWindow.output_text = QTextEdit()
        MainWindow.output_text.setObjectName("output_text")
        MainWindow.output_text.setVerticalScrollBar(ModernScrollBar())
        MainWindow.output_text.setHorizontalScrollBar(ModernScrollBar())
        MainWindow.output_text.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        MainWindow.output_text.setFixedHeight(80)
        main_content_layout.addWidget(MainWindow.output_text)
        content_layout.addLayout(main_content_layout)
        main_layout.addLayout(content_layout)
        MainWindow.queue_layout.setStretch(0, 1)

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.center_window()
        self.set_rounded_window()
        self.set_gradient_background()
        self.launch_path = os.getcwd()
        self.active_threads = []
        self.dot_animation_timer = QTimer(self)
        self.dot_animation_timer.timeout.connect(self.update_dots)
        self.dot_count = 0
        self.current_status_message = ""
        self.is_sending = False
        self.file_queue = Queue()
        self.queue_item_widgets = {}
        self.clear_message_timer = QTimer(self)
        self.clear_message_timer.setSingleShot(True)
        self.clear_message_timer.timeout.connect(self.clear_status_message)
        self.current_file = None
        self.output_visible = False
        self.output_text.setVisible(self.output_visible)
        self.output_expand_button.setText("^")
        self.old_pos = None
        QTimer.singleShot(0, self._deferred_init_data)

    def _deferred_init_data(self):
        app_data_dir = get_app_data_dir()
        if app_data_dir:
            self.config_file = os.path.join(app_data_dir, "iMShare.json")
            self.friend_icons_path = os.path.join(app_data_dir, "friend_icons")
            try:
                if not os.path.exists(self.friend_icons_path):
                    os.makedirs(self.friend_icons_path)
            except OSError as e:
                print(f"Error creating friend_icons directory: {e}")
                self.friend_icons_path = None
        else:
            self.config_file = None
            self.friend_icons_path = None
        self.settings = self.load_settings()
        self.download_code = self.settings.get("download_code", None)
        self.path_entry.setText(self.download_code or "")
        self.friends = self.settings.get("friends", [])
        self.thread_pool = QThreadPool()
        QTimer.singleShot(100, self.load_friends)
        QTimer.singleShot(200, self.apply_effects) # Defer effects

    def apply_effects(self):
        set_drop_shadow(self.download_file_button)
        set_drop_shadow(self.file_queue_list)
        set_drop_shadow(self.friends_scroll_area)
        set_drop_shadow(self.status_frame)
        set_drop_shadow(self.status_label)
        set_drop_shadow(self.path_entry)
        set_drop_shadow(self.clear_path_button)
        set_drop_shadow(self.progress_bar)

    def set_rounded_window(self):
        path = QPainterPath()
        rect = self.rect()
        path.addRoundedRect(rect.x(), rect.y(), rect.width(), rect.height(), 10, 10)
        polygons = path.toSubpathPolygons()
        if polygons:
            qpolygon = QPolygon()
            for point in polygons[0]:
                qpolygon.append(QPoint(int(point.x()), int(point.y())))
            region = QRegion(qpolygon)
            self.setMask(region)

    def closeEvent(self, event):
        self.thread_pool.waitForDone()
        event.accept()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            widget_at_pos = self.childAt(event.pos())
            interactive_widgets = (QPushButton, QLineEdit, QListWidget, QScrollArea, QTextEdit, TitleBar)
            if isinstance(widget_at_pos, interactive_widgets):
                event.ignore()
            else:
                self.old_pos = event.globalPos()
                event.accept()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self.old_pos is not None:
            delta = event.globalPos() - self.old_pos
            self.move(self.pos() + delta)
            self.old_pos = event.globalPos()
            event.accept()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self.old_pos = None
        event.accept()
        super().mouseReleaseEvent(event)

    def set_gradient_background(self):
        gradient = QLinearGradient(0, 0, self.width(), self.height())
        gradient.setColorAt(0, QColor("#141415"))
        gradient.setColorAt(1, QColor("#141415"))
        palette = self.palette()
        palette.setBrush(self.backgroundRole(), QBrush(gradient))
        self.setPalette(palette)
    
    def resizeEvent(self, event):
        self.title_bar_gradient = QLinearGradient(0, 0, self.width(), self.title_bar_height)
        self.title_bar_gradient.setColorAt(0, QColor("#141415"))
        self.title_bar_gradient.setColorAt(1, QColor("#141415"))
        self.title_bar_palette.setBrush(self.title_bar.backgroundRole(), QBrush(self.title_bar_gradient))
        self.title_bar.setPalette(self.title_bar_palette)
        self.set_gradient_background()
        super().resizeEvent(event)

    def update_progress_bar(self, progress, color, is_hashing):
        self.progress_bar.setValue(progress)

    def update_speed(self, speed):
        self.speed_label.setText(speed)

    def update_time_remaining(self, time_remaining):
        self.time_remaining_label.setText(time_remaining)

    def clear_path(self):
        self.path_entry.clear()
        self.file_name_label.setText("")
        self.file_size_label.setText("")

    def clear_all(self):
        self.output_text.clear()
        self.clear_path()
        self.show_status_message("Cleared!", "cleared", 3000)
        self.progress_bar.setValue(0)
        self.speed_label.setText("")
        self.time_remaining_label.setText("")
        self.dot_animation_timer.stop()
        self.is_sending = False
        self.current_file = None

    def show_status_message(self, text, status_property, timeout_ms=0):
        self.status_label.setText(text)
        self.status_label.setProperty("status", status_property)
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)
        if timeout_ms > 0:
            self.clear_message_timer.start(timeout_ms)

    def clear_status_message(self):
        self.show_status_message("", "")

    def update_animated_status(self, message, color):
        self.current_status_message = message
        self.show_status_message(message, "sending")
        self.status_label.setFont(QFont("Arial", 12, QFont.Normal))
        self.dot_count = 0
        self.update_dots()
        if "Loading..." in message or "Downloading..." in message:
            self.dot_animation_timer.start(500)
        else:
            self.dot_animation_timer.stop()

    def update_dots(self):
        if "Loading..." in self.current_status_message or "Downloading..." in self.current_status_message:
            dots = "." * (self.dot_count % 4)
            self.status_label.setText(f"{self.current_status_message}{dots}")
            self.dot_count += 1
        else:
            self.status_label.setText(self.current_status_message)

    def center_window(self):
        qr = self.frameGeometry()
        cp = QDesktopWidget().availableGeometry().center()
        qr.moveCenter(cp)
        self.move(qr.topLeft())
    
    def select_all_text(self, event):
        self.path_entry.selectAll()
        QLineEdit.mousePressEvent(self.path_entry, event)
    
    def load_settings(self):
        if not self.config_file or not os.path.exists(self.config_file):
            return {}
        try:
            with open(self.config_file, 'r') as file:
                return json.load(file)
        except (FileNotFoundError, json.JSONDecodeError, TypeError):
            pass
        return {}

    def save_code_to_json(self, code):
        if not self.config_file:
            return
        self.download_code = code
        self.settings["download_code"] = code
        try:
            with open(self.config_file, 'w') as file:
                json.dump(self.settings, file, indent=4)
        except Exception as e:
            print(f"Failed to save settings: {e}")
    
    def toggle_output(self):
        self.output_visible = not self.output_visible
        self.output_text.setVisible(self.output_visible)
        self.output_expand_button.setText("v" if self.output_visible else "^")
        
    def start_download(self):
        code_prefix = self.path_entry.text().strip()
        if not code_prefix:
            self.show_status_message("Please enter a code.", "error", 3000)
            return
        if self.is_sending:
            self.show_status_message("Already sending.", "error", 3000)
            return
        self.download_code = code_prefix
        self.save_code_to_json(code_prefix)
        queue_id = str(uuid.uuid4())
        self.file_queue.put((code_prefix, queue_id))
        self.process_pending_queue()

    def process_pending_queue(self):
        if self.is_sending or self.file_queue.empty():
            return
        code_prefix, queue_id = self.file_queue.get()
        self.is_sending = True
        self.current_file = ("Preparing...", "")
        self.file_name_label.setText("Preparing...")
        self.file_size_label.setText("")
        list_item = QListWidgetItem("Preparing...", self.file_queue_list)
        list_item.queue_id = queue_id
        self.queue_item_widgets[queue_id] = list_item
        self.file_queue_list.addItem(list_item)
        self.start_send_thread(code_prefix, queue_id)

    def start_send_thread(self, code_prefix, queue_id):
        worker = DownloadWorker(code_prefix, self, queue_id=queue_id)
        worker.signals.output_signal.connect(lambda line: update_output(self.output_text, line))
        worker.signals.finished_signal.connect(
            lambda success, q_id, msg: handle_command_completion(success, self.status_label, self.progress_bar, self, q_id, msg))
        worker.signals.progress_signal.connect(lambda progress: self.update_progress_bar(progress, "#008080", False))
        worker.signals.hashing_progress_signal.connect(lambda progress: self.update_progress_bar(progress, "#008080", True))
        worker.signals.speed_signal.connect(self.update_speed)
        worker.signals.status_update_signal.connect(self.update_animated_status)
        worker.signals.time_remaining_signal.connect(self.update_time_remaining)
        worker.signals.current_file_signal.connect(self.update_current_file_info)
        worker.signals.file_name_size_signal.connect(self.update_queue_item_name_size)
        self.active_threads.append(worker)
        self.thread_pool.start(worker)

    def update_queue_item_status(self, queue_id, status=None):
        item = self.queue_item_widgets.get(queue_id)
        if not item:
            return
        base_text = item.text().replace('📁 ', '').replace('⏳ ', '')
        if status == "Complete!":
            item.setText(f"📁  {base_text}")
            item.is_complete = True
        elif status == "Downloading...":
            item.setText(f"⏳ {base_text}")
            item.is_complete = False
        else:
            item.setText(base_text)
            item.is_complete = False
                    
    def update_queue_item_name_size(self, filename, filesize, queue_id):
        item = self.queue_item_widgets.get(queue_id)
        if item:
            item.setText(f"{filename} ({filesize})")
           
    def remove_queue_item(self, queue_id):
        item = self.queue_item_widgets.pop(queue_id, None)
        if item:
            row = self.file_queue_list.row(item)
            if row != -1:
                self.file_queue_list.takeItem(row)

    def update_current_file_info(self, filename, filesize):
        self.current_file = (filename, filesize)
        self.file_name_label.setText(filename)
        self.file_size_label.setText(f"Size: {filesize}")
    
    def handle_queue_item_click(self, item):
        if not (hasattr(item, 'queue_id') and hasattr(item, 'is_complete') and item.is_complete):
            return

        for thread in self.active_threads:
            if hasattr(thread, "queue_id") and thread.queue_id == item.queue_id:
                if thread.path_exists and thread.full_file_path:
                    try:
                        if os.path.isfile(thread.full_file_path):
                            QDesktopServices.openUrl(QUrl.fromLocalFile(thread.full_file_path))
                        else:
                            files = os.listdir(thread.full_file_path)
                            if len(files) == 1:
                                QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.join(thread.full_file_path, files[0])))
                            else:
                                QDesktopServices.openUrl(QUrl.fromLocalFile(thread.full_file_path))
                    except Exception as e:
                        print(f"Error opening path: {e}")
                        if thread.full_file_path:
                            QDesktopServices.openUrl(QUrl.fromLocalFile(thread.full_file_path))
                else:
                    print("Error: path not found")
                break
        self.file_queue_list.clearSelection()
    
    def create_add_button(self):
       button = QPushButton("Add")
       button.setFixedSize(70, 70)
       button.clicked.connect(self.show_add_friend_popup)
       set_drop_shadow(button)  
       return button

    def show_add_friend_popup(self):
        popup = FriendPopup(parent=self)
        if popup.exec_() == QDialog.Accepted:
            new_friend = popup.get_new_friend_data()
            if new_friend:
                self.add_friend(new_friend)
        
    def load_friends(self):
        self.clear_friends_container()
        row, col = 0, 0
        if self.friend_icons_path and self.friends:
            for friend in self.friends:
                friend_widget = FriendWidget(friend, self)
                set_drop_shadow(friend_widget)
                self.friends_container_layout.addWidget(friend_widget, row, col)
                col += 1
                if col > 5:
                    col = 0
                    row += 1
        self.friends_container_layout.addWidget(self.add_friend_button, row, col, alignment=Qt.AlignTop)
        if not self.friend_icons_path:
            self.add_friend_button.setEnabled(False)
            self.add_friend_button.setToolTip("Could not create AppData folder. Friend list is disabled.")
        else:
            self.add_friend_button.setEnabled(True)
            self.add_friend_button.setToolTip("")

    def clear_friends_container(self):
        while self.friends_container_layout.count():
            item = self.friends_container_layout.takeAt(0)
            widget = item.widget()
            if widget and widget != self.add_friend_button:
                widget.deleteLater()
    
    def add_friend(self, new_friend):
        if "image" in new_friend and new_friend.get("image") and os.path.exists(new_friend["image"]):
            thumbnail_path = self.save_friend_thumbnail(new_friend["image"])
            if thumbnail_path:
                new_friend["image"] = thumbnail_path
            else:
                new_friend["image"] = None
        self.friends.append(new_friend)
        self.save_friends_to_json()
        self.load_friends()
       
    def save_friends_to_json(self):
        if not self.config_file:
            return
        self.settings["friends"] = self.friends
        try:
            with open(self.config_file, 'w') as file:
                json.dump(self.settings, file, indent=4)
        except Exception as e:
            print(f"Failed to save friends settings: {e}")
            
    def show_friend_context_menu(self, widget, friend_data):
        menu = QMenu(self)
        delete_action = menu.addAction("Delete")
        edit_action = menu.addAction("Edit")
        action = menu.exec_(widget.mapToGlobal(widget.rect().topLeft()))
        if action == delete_action:
            self.delete_friend(friend_data)
        elif action == edit_action:
            self.show_edit_friend_popup(friend_data)

    def delete_friend(self, friend_to_delete):
        image_filename = friend_to_delete.get("image")
        if self.friend_icons_path and image_filename:
            image_path = os.path.join(self.friend_icons_path, image_filename)
            if os.path.exists(image_path):
                try:
                    os.remove(image_path)
                    print(f"Deleted friend icon: {image_path}")
                except Exception as e:
                    print(f"Error deleting friend icon {image_path}: {e}")
        self.friends = [friend for friend in self.friends if friend != friend_to_delete]
        self.save_friends_to_json()
        self.load_friends()

    def show_edit_friend_popup(self, friend_data):
        popup = FriendPopup(friend_data, self)
        if popup.exec_() == QDialog.Accepted:
            new_friend_data = popup.get_new_friend_data()
            if new_friend_data:
                self.edit_friend(friend_data, new_friend_data)

    def edit_friend(self, old_friend_data, new_friend_data):
        try:
            index = self.friends.index(old_friend_data)
            if "image" in new_friend_data and new_friend_data.get("image") and os.path.exists(new_friend_data["image"]) and new_friend_data["image"] != old_friend_data.get("image"):
                thumbnail_path = self.save_friend_thumbnail(new_friend_data["image"])
                if thumbnail_path:
                    new_friend_data["image"] = thumbnail_path
                else: 
                    new_friend_data["image"] = old_friend_data.get("image")
            self.friends[index] = new_friend_data
            self.save_friends_to_json()
            self.load_friends()
        except ValueError:
            print("Error: could not find friend to edit")

    def save_friend_thumbnail(self, image_path):
        if not self.friend_icons_path:
            return None
        try:
            thumbnail = create_circular_thumbnail(image_path, 70)
            if thumbnail.isNull():
                return None
            filename = f"{uuid.uuid4()}.png"
            thumbnail_path = os.path.join(self.friend_icons_path, filename)
            thumbnail.save(thumbnail_path, "PNG")
            return filename
        except Exception as e:
            print(f"Failed to save thumbnail: {e}")
            return None
        
    def execute_croc_command(self, code):
        if not code:
            self.show_status_message("No code for friend.", "error", 3000)
            return
        if self.is_sending:
            self.show_status_message("Already sending.", "error", 3000)
            return
        self.path_entry.setText(code)
        self.start_download()

class FriendPopup(QDialog):
    def __init__(self, friend_data=None, parent=None):
        super().__init__(parent)
        self.friend_data = friend_data or {}
        self.new_friend_data = self.friend_data.copy()
        self.setWindowTitle("Edit Friend" if friend_data else "Add Friend")
        self.setModal(True)
        self.setFixedSize(350, 300)
        self.setWindowFlags(Qt.Window | Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
        layout = QVBoxLayout(self)
        self.profile_preview = ClickableImageLabel()
        self.profile_preview.setFixedSize(80, 80)
        self.profile_preview.setAlignment(Qt.AlignCenter)
        image_filename = self.friend_data.get("image")
        full_image_path = None
        if image_filename and self.parent() and hasattr(self.parent(), 'friend_icons_path'):
            full_image_path = os.path.join(self.parent().friend_icons_path, image_filename)
        self.profile_preview.setPixmap(create_circular_thumbnail(full_image_path, 80))
        self.profile_preview.clicked.connect(self.select_profile_image)
        layout.addWidget(self.profile_preview, alignment=Qt.AlignCenter)
        set_drop_shadow(self.profile_preview)
        bold_font = QFont()
        bold_font.setBold(True)
        name_label = QLabel("Name:")
        name_label.setFont(bold_font)
        layout.addWidget(name_label)
        self.name_entry = QLineEdit(self.friend_data.get("name", ""))
        self.name_entry.setFont(bold_font)
        layout.addWidget(self.name_entry)
        set_drop_shadow(self.name_entry)
        code_label = QLabel("Code:")
        code_label.setFont(bold_font)
        layout.addWidget(code_label)
        self.code_entry = QLineEdit(self.friend_data.get("download_code", ""))
        self.code_entry.setFont(bold_font)
        layout.addWidget(self.code_entry)
        set_drop_shadow(self.code_entry)
        button_layout = QHBoxLayout()
        self.save_button = QPushButton("Save" if friend_data else "Add")
        self.save_button.setFont(bold_font)
        self.save_button.clicked.connect(self.try_accept)
        self.save_button.setDefault(True)
        button_layout.addWidget(self.save_button)
        set_drop_shadow(self.save_button)
        cancel_button = QPushButton("Cancel")
        cancel_button.setFont(bold_font)
        cancel_button.setObjectName("cancel_button")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)
        self.error_label = QLabel()
        self.error_label.setStyleSheet("color: red;")
        self.error_label.setFont(bold_font)
        layout.addWidget(self.error_label)

    def showEvent(self, event):
        super().showEvent(event)
        self.set_rounded_dialog()
        self.center_dialog()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.old_pos = event.globalPos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self.old_pos is not None:
            delta = event.globalPos() - self.old_pos
            self.move(self.pos() + delta)
            self.old_pos = event.globalPos()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self.old_pos = None
        super().mouseReleaseEvent(event)

    def select_profile_image(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Profile Image", "", "Image Files (*.png *.jpg *.jpeg *.bmp)")
        if file_path:
            self.new_friend_data["image"] = file_path
            self.profile_preview.setPixmap(create_circular_thumbnail(file_path, 80))

    def get_new_friend_data(self):
        name = self.name_entry.text().strip()
        code = self.code_entry.text().strip()
        if not code:
            return None
        self.new_friend_data["name"] = name
        self.new_friend_data["download_code"] = code
        return self.new_friend_data

    def try_accept(self):
        if not self.code_entry.text().strip():
            self.error_label.setText("Code required")
            return
        self.accept()

    def set_rounded_dialog(self):
        path = QPainterPath()
        rect = self.rect()
        path.addRoundedRect(rect.x(), rect.y(), rect.width(), rect.height(), 15, 15)
        polygons = path.toSubpathPolygons()
        if polygons:
            qpolygon = QPolygon()
            for point in polygons[0]:
                qpolygon.append(QPoint(int(point.x()), int(point.y())))
            region = QRegion(qpolygon)
            self.setMask(region)

    def center_dialog(self):
        if self.parent():
            parent_center_global = self.parent().mapToGlobal(self.parent().rect().center())
            dialog_width = self.width()
            dialog_height = self.height()
            new_x = parent_center_global.x() - (dialog_width // 2)
            new_y = parent_center_global.y() - (dialog_height // 2)
            self.move(new_x, new_y)
        else:
            qr = self.frameGeometry()
            cp = QDesktopWidget().availableGeometry().center()
            qr.moveCenter(cp)
            self.move(qr.topLeft())

if __name__ == '__main__':
    handle_instance_check()
    if is_windows():
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("myappid")
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(resource_path("iMShare.ico")))
    style_file = resource_path("download.qss")
    if os.path.exists(style_file):
        with open(style_file, "r") as f:
            app.setStyleSheet(f.read())
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())