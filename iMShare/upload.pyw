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
    QAbstractItemView, QSizePolicy, QSpacerItem, QFileDialog, QDialog, QGraphicsDropShadowEffect,
    QScrollBar)
from PyQt5.QtGui import (QFont, QColor, QPainter, QBrush, QLinearGradient, QRegion, QPainterPath, QPolygon, QDragEnterEvent, QDropEvent, QIcon)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QPoint, QObject
import pyperclip

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
    lock_file_path = os.path.join(app_data_dir, 'imshare_upload.lock')
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
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)

def quote_path(path):
    path = (path or "").strip().strip('"')
    return f'"{path}"' if path else ""

def get_clipboard_path():
    try:
        content = pyperclip.paste().strip()
        stripped_content = content.strip('"')
        return stripped_content if os.path.exists(stripped_content) else ""
    except (RuntimeError, TypeError):
        return ""

def format_file_size(size):
    units = ["B", "KB", "MB", "GB", "TB"]
    for unit in units:
        if size < 1024.0:
            break
        size /= 1024.0
    return f"{size:.1f}{unit}"

def truncate_filename(filename, length):
    return filename[:length] + "..." if len(filename) > length else filename

def set_drop_shadow(widget, blur_radius=10, offset_x=4, offset_y=4, opacity=150):
    shadow = QGraphicsDropShadowEffect()
    shadow.setBlurRadius(blur_radius)
    shadow.setColor(QColor(0, 0, 0, opacity))
    shadow.setOffset(offset_x, offset_y)
    widget.setGraphicsEffect(shadow)

def _set_gradient_background(widget, extra_widgets=None):
    gradient = QLinearGradient(0, 0, widget.width(), widget.height())
    gradient.setColorAt(0, QColor("#373737"))
    gradient.setColorAt(1, QColor("#261f2b"))
    palette = widget.palette()
    palette.setBrush(widget.backgroundRole(), QBrush(gradient))
    widget.setPalette(palette)
    if extra_widgets:
        for w in extra_widgets:
            w.setAutoFillBackground(True)
            widget_palette = w.palette()
            widget_palette.setBrush(w.backgroundRole(), QBrush(gradient))
            w.setPalette(widget_palette)

def _set_rounded_window(widget):
    path = QPainterPath()
    rect = widget.rect()
    path.addRoundedRect(rect.x(), rect.y(), rect.width(), rect.height(), 10, 10)
    widget.setMask(QRegion(path.toFillPolygon().toPolygon()))

class SendFileThread(QThread):
    output_signal = pyqtSignal(str)
    status_signal = pyqtSignal(str, str)
    finished_signal = pyqtSignal(bool)
    progress_signal = pyqtSignal(int)
    speed_signal = pyqtSignal(str)
    hashing_progress_signal = pyqtSignal(int)
    hashing_finished_signal = pyqtSignal()
    status_update_signal = pyqtSignal(str, str)
    time_remaining_signal = pyqtSignal(str)
    current_file_signal = pyqtSignal(str, str)
    queue_id_signal = pyqtSignal(str)
    thread_finished_signal = pyqtSignal(object)

    def __init__(self, filepath, code_prefix, parent=None, queue_id=None, total_expected_files=0):
        super().__init__(parent)
        self.filepath = filepath
        self.code_prefix = code_prefix
        self.process = None
        self.is_hashing = True
        self.hashing_complete = False
        self.start_time = 0
        self.queue_id = queue_id
        self.is_cancelled = False
        self.total_expected_files = total_expected_files
        self.current_hashing_file_count = 0
        self.filepath_stripped = self.filepath.strip().strip('"')
        self.is_directory = os.path.isdir(self.filepath_stripped)
        self.total_files_in_batch = 0
        self.last_completed_file_num = 0
        self.filename = os.path.basename(self.filepath_stripped)
        try:
            self.filesize = format_file_size(os.path.getsize(self.filepath_stripped))
        except OSError:
            self.filesize = "N/A"

    def run(self):
        try:
            if is_windows():
                if self.code_prefix:
                    command = f'croc --ignore-stdin --overwrite send --hash imohash --code {self.code_prefix} {quote_path(self.filepath)}'
                else:
                    command = f'croc --ignore-stdin send --hash imohash {quote_path(self.filepath)}'
                full_command = ["powershell", "-Command", command]
                creation_flags = subprocess.CREATE_NO_WINDOW
                use_shell = False
            else:
                full_command = ['croc', '--ignore-stdin', 'send', '--hash', 'imohash']
                if self.code_prefix:
                    full_command.extend(['--code', self.code_prefix])
                full_command.append(self.filepath.strip().strip('"'))
                creation_flags = 0
                use_shell = False
            self.process = subprocess.Popen(full_command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                            universal_newlines=True, creationflags=creation_flags,
                                            shell=use_shell)
            self.start_time = time.time()
            self.current_file_signal.emit(self.filename, self.filesize)
            self.queue_id_signal.emit(self.queue_id)
            while True:
                line = self.process.stdout.readline()
                if not line:
                    break
                self.output_signal.emit(line)
                self.parse_output_line(line)
            self.process.wait()
            if self.process.returncode != 0:
                if not self.is_cancelled:
                    self.output_signal.emit(f"\nError: Command exited with code {self.process.returncode}\n")
                    self.finished_signal.emit(False)
            else:
                self.finished_signal.emit(True)
                self.status_update_signal.emit("Completed!", "white")
                self.queue_id_signal.emit(self.queue_id)
        except FileNotFoundError:
            self.output_signal.emit("\nError: 'croc' or 'powershell' not found. Please ensure it's in your system's PATH.\n")
            self.finished_signal.emit(False)
        except (OSError, IOError) as e:
            self.output_signal.emit(f"\nAn operating system or I/O error occurred: {e}\n")
            self.finished_signal.emit(False)
        except Exception as e:
            self.output_signal.emit(f"\nAn unexpected error occurred: {e}\n")
            self.finished_signal.emit(False)
        finally:
            self.thread_finished_signal.emit(self)

    def parse_output_line(self, line):
        clean_line = line.strip()
        if match := re.match(r'Hashing (.+?)\s+(\d+)%\s+.*\((.+?)\).*', clean_line):
            self._handle_hashing(match)
        elif match := re.match(r'(.+?)\s+(\d+)%\s+.*\((.+?)(?:,\s*(.+?))?\)\s*(?:\((.+?)\))?\s*(\d+/\d+)?', clean_line):
            self._handle_uploading(match)
        elif match := re.search(r'Sending (\d+) files(?: and (\d+) folders)? \(([^)]+)\)', clean_line):
            self._handle_sending(match)
        elif match := re.search(r'Code is:', clean_line):
            self._handle_code(match)

    def _handle_sending(self, match):
        current_files = int(match.group(1))
        self.current_hashing_file_count = current_files
        total_size = match.group(3)
        self.current_file_signal.emit(self.filename, total_size)
        self.is_hashing = True
        self.status_update_signal.emit("Loading...", "yellow")
        if self.total_expected_files > 0:
            progress = (self.current_hashing_file_count / self.total_expected_files) * 100
            self.hashing_progress_signal.emit(int(progress))
        else:
            self.hashing_progress_signal.emit(0)

    def _handle_code(self, match):
        if self.hashing_complete:
            return
        self.hashing_progress_signal.emit(100)
        self.hashing_complete = True
        self.is_hashing = False
        self.hashing_finished_signal.emit()
        self.status_update_signal.emit("Ready to Upload", "#0058d3")
        self.time_remaining_signal.emit("")

    def _handle_hashing(self, match):
        _, progress, speed = match.groups()
        self.hashing_progress_signal.emit(int(progress))
        self.speed_signal.emit(speed.strip())
        self.is_hashing = True
        self.status_update_signal.emit("Loading...", "yellow")
        elapsed = time.time() - self.start_time
        self.time_remaining_signal.emit(self.format_time(elapsed))

    def _handle_uploading(self, match):
        filename, progress_str, size, speed, time_remaining, file_count = match.groups()
        progress = int(progress_str)
        if self.is_directory:
            if self.total_files_in_batch == 0 and file_count:
                _, self.total_files_in_batch = map(int, file_count.split('/'))
            if self.total_files_in_batch > 0:
                if file_count:
                    current_file_num, _ = map(int, file_count.split('/'))
                    self.last_completed_file_num = current_file_num
                    total_progress = current_file_num / self.total_files_in_batch * 100
                else:
                    current_file_progress = progress / 100.0
                    total_progress = (self.last_completed_file_num + current_file_progress) / self.total_files_in_batch * 100
                self.progress_signal.emit(int(total_progress))
            else:
                self.progress_signal.emit(0)
        else:
            self.progress_signal.emit(progress)
        if speed:
            self.speed_signal.emit(speed.strip())
        self.is_hashing = False
        self.status_update_signal.emit("Uploading file...", "yellow")
        if time_remaining:
            self.time_remaining_signal.emit(time_remaining.strip())

    def format_time(self, seconds):
        minutes = int(seconds // 60)
        seconds = int(seconds % 60)
        return f"{minutes}m{seconds}s"

    def close_process(self):
        if self.process and self.process.poll() is None:
            kill_command = ["taskkill", "/F", "/T", "/PID", str(self.process.pid)] if is_windows() else ["kill", "-9", str(self.process.pid)]
            subprocess.run(kill_command, creationflags=subprocess.CREATE_NO_WINDOW if is_windows() else 0, shell=not is_windows(), capture_output=True)

def update_output(output_widget, line):
    output_widget.insertPlainText(line)
    scrollbar = output_widget.verticalScrollBar()
    scrollbar.setValue(scrollbar.maximum())

def handle_command_completion(success, status_label, progress_bar, window):
    status_label.setText("Complete!" if success else "Failed.")
    status_label.setProperty("status", "success" if success else "error")
    status_label.style().unpolish(status_label)
    status_label.style().polish(status_label)
    window.speed_label.setText("")
    progress_bar.setValue(0)
    window.is_sending = False
    window.start_next_transfer()

class CircularButton(QPushButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(22, 22)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QBrush(QColor("#333")))
        painter.drawEllipse(self.rect())
        super().paintEvent(event)

class ModernScrollBar(QScrollBar):
    def __init__(self, parent=None):
        super().__init__(parent)

class QueueListItem(QWidget):
    def __init__(self, filename, filesize, queue_id, remove_callback, parent=None):
        super().__init__(parent)
        self.queue_id = queue_id
        self.remove_callback = remove_callback
        self.filename = filename
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        self.remove_button = CircularButton("✖")
        self.remove_button.clicked.connect(self.on_remove_clicked)
        layout.addWidget(self.remove_button)
        layout.setAlignment(self.remove_button, Qt.AlignLeft | Qt.AlignVCenter)
        layout.setSpacing(1)
        self.label = QLabel(f"{truncate_filename(filename, 14)} ({filesize})")
        self.label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.label.setMaximumWidth(140)
        layout.addWidget(self.label)
        set_drop_shadow(self.label)

    def on_remove_clicked(self):
        if self.remove_callback:
            self.remove_callback(self.filename, self.queue_id)

class SettingsPopup(QDialog):
    def __init__(self, main_window, initial_code, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.setObjectName("SettingsPopup")
        self.setWindowTitle("Set Code")
        self.setWindowFlag(Qt.FramelessWindowHint)
        self.setModal(True)
        self.window_position = None
        self.start_move_position = None
        self.resize_timer = QTimer(self)
        self.resize_timer.setSingleShot(True)
        self.resize_timer.timeout.connect(self._apply_resize_styles)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        self.code_label = QLabel("Set Your Secret Code")
        self.code_label.setObjectName("code_label")
        self.code_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.code_label)
        set_drop_shadow(self.code_label)
        self.code_input = QLineEdit(initial_code)
        self.code_input.textChanged.connect(self.validate_code_input)
        self.code_input.returnPressed.connect(self.save_settings)
        layout.addWidget(self.code_input)
        set_drop_shadow(self.code_input)
        self.code_description = QLabel("This code is used by others to receive your files.")
        self.code_description.setObjectName("code_description")
        self.code_description.setWordWrap(True)
        self.code_description.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.code_description)
        set_drop_shadow(self.code_description)
        self.error_label = QLabel("")
        self.error_label.setObjectName("error_label")
        self.error_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.error_label)
        set_drop_shadow(self.error_label)
        button_layout = QHBoxLayout()
        self.set_button = QPushButton("Set Code")
        self.set_button.setObjectName("set_button")
        self.set_button.clicked.connect(self.save_settings)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setObjectName("cancel_button")
        self.cancel_button.clicked.connect(self.close)
        button_layout.addWidget(self.cancel_button)
        set_drop_shadow(self.cancel_button)
        button_layout.addWidget(self.set_button)
        set_drop_shadow(self.set_button)
        layout.addLayout(button_layout)
        _set_rounded_window(self)
        _set_gradient_background(self)

    def shake_error_label(self):
        try:
            self.animation = QPropertyAnimation(self.error_label, b"pos")
            self.animation.setDuration(500)
            self.animation.setLoopCount(1)
            pos = self.error_label.pos()
            self.animation.setKeyValueAt(0.0, pos)
            self.animation.setKeyValueAt(0.1, pos + QPoint(10, 0))
            self.animation.setKeyValueAt(0.2, pos)
            self.animation.setKeyValueAt(0.3, pos + QPoint(-10, 0))
            self.animation.setKeyValueAt(0.4, pos)
            self.animation.setKeyValueAt(0.5, pos + QPoint(10, 0))
            self.animation.setKeyValueAt(0.6, pos)
            self.animation.setKeyValueAt(0.7, pos + QPoint(-10, 0))
            self.animation.setKeyValueAt(0.8, pos)
            self.animation.setKeyValueAt(0.9, pos + QPoint(10, 0))
            self.animation.setKeyValueAt(1.0, pos)
            self.animation.start()
        except Exception as e:
            print(f"Animation failed: {e}")

    def validate_code_input(self, text):
        if " " in text:
            self.code_input.setText(text.replace(" ", ""))
            self.error_label.setText("No Space")
            return
        if 0 < len(text) < 6:
            self.error_label.setText("6+ characters")
        else:
            self.error_label.setText("")

    def save_settings(self):
        code = self.code_input.text()
        if len(code) > 0 and len(code) < 6:
            self.error_label.setText("6+ characters")
            self.shake_error_label()
            return
        if " " in code:
            self.error_label.setText("No Space")
            self.shake_error_label()
            return
        self.main_window.save_code_to_json(code)
        self.close()

    def showEvent(self, event):
        if self.main_window:
            parent_pos = self.main_window.pos()
            parent_size = self.main_window.size()
            popup_size = self.size()
            new_x = parent_pos.x() + (parent_size.width() - popup_size.width()) / 2
            new_y = parent_pos.y() + (parent_size.height() - popup_size.height()) / 2
            self.move(int(new_x), int(new_y))
        super().showEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.resize_timer.start(100)

    def _apply_resize_styles(self):
        _set_rounded_window(self)
        _set_gradient_background(self)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.start_move_position = event.globalPos()
            self.window_position = self.pos()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self.start_move_position is not None:
            delta = event.globalPos() - self.start_move_position
            self.move(self.window_position + delta)
            event.accept()

    def mouseReleaseEvent(self, event):
        self.start_move_position = None
        event.accept()

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self._initialize_state()
        self._setup_ui()
        self._connect_signals()
        QTimer.singleShot(0, self._deferred_init_data)

    def _deferred_init_data(self):
        app_data_dir = get_app_data_dir()
        if app_data_dir:
            self.config_file = os.path.join(app_data_dir, "iMShare.json")
        else:
            self.config_file = None
        self.settings = self.load_settings()
        self.code = self.settings.get("code", None)
        if self.code is None:
            self.open_settings_popup()
            self.code = self.settings.get("code", None)
        QTimer.singleShot(100, self.load_initial_path)
        QTimer.singleShot(100, self.start_next_transfer)
        QTimer.singleShot(200, self.apply_effects)

    def apply_effects(self):
        set_drop_shadow(self.send_file_button)
        set_drop_shadow(self.file_queue_list)
        set_drop_shadow(self.file_name_label)
        set_drop_shadow(self.file_size_label)
        set_drop_shadow(self.path_label)
        set_drop_shadow(self.path_entry)
        set_drop_shadow(self.clear_path_button)
        set_drop_shadow(self.progress_bar)
        set_drop_shadow(self.time_remaining_label)
        set_drop_shadow(self.speed_label)
        set_drop_shadow(self.status_frame)
        set_drop_shadow(self.status_label)
        set_drop_shadow(self.output_text)

    def _initialize_state(self):
        self.window_position = None
        self.start_move_position = None
        self.title_bar_height = 30
        self.resize_timer = QTimer(self)
        self.resize_timer.setSingleShot(True)
        self.resize_timer.timeout.connect(self._apply_resize_styles)
        self.output_dir = os.getcwd()
        self.active_threads = []
        self.dot_count = 0
        self.current_status_message = ""
        self.is_sending = False
        self.file_queue = Queue()
        self.initial_path_loaded = False
        self.current_file = None
        self.output_visible = False
        self.dot_animation_timer = QTimer(self)
        self.path_entry_timer = QTimer(self)
        self.path_entry_timer.setSingleShot(True)
        self.clear_message_timer = QTimer(self)
        self.config_file = None
        self.settings = {}

    def _setup_ui(self):
        self.setObjectName("MainWindow")
        self.setWindowTitle("iMShare | Upload")
        self.setMinimumSize(800, 500)
        self.setWindowFlag(Qt.FramelessWindowHint)
        self.setAcceptDrops(True)
        self._setup_main_layout()
        self._setup_title_bar()
        self._setup_content_area()
        self.center_window()
        _set_rounded_window(self)
        _set_gradient_background(self, extra_widgets=[self.title_bar])

    def _setup_main_layout(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.main_layout)

    def _setup_title_bar(self):
        self.title_bar = QWidget(self)
        self.title_bar.setFixedHeight(self.title_bar_height)
        self.title_bar.setAttribute(Qt.WA_StyledBackground, True)
        self.title_bar.setObjectName("title_bar")
        title_layout = QHBoxLayout(self.title_bar)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(0)
        title_layout.addSpacing(90)
        self.title_label = QLabel("iMShare | Upload")
        self.title_label.setObjectName("title_label")
        self.title_label.setAlignment(Qt.AlignCenter)
        font = QFont()
        font.setBold(True)
        self.title_label.setFont(font)
        title_layout.addWidget(self.title_label)
        self.title_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.settings_button = QPushButton("⚙")
        self.settings_button.setObjectName("settings_button")
        self.settings_button.setFixedSize(30,30)
        title_layout.addWidget(self.settings_button)
        self.minimize_button = QPushButton("▬")
        self.minimize_button.setObjectName("minimize_button")
        self.minimize_button.setFixedSize(30,30)
        title_layout.addWidget(self.minimize_button)
        self.close_button = QPushButton("⬤")
        self.close_button.setObjectName("close_button")
        self.close_button.setFixedSize(30,30)
        title_layout.addWidget(self.close_button)
        self.main_layout.addWidget(self.title_bar)

    def _setup_content_area(self):
        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(40, 20, 20, 20)
        self._setup_queue_area(content_layout)
        self._setup_main_content_area(content_layout)
        self.main_layout.addLayout(content_layout)

    def _setup_queue_area(self, parent_layout):
        queue_area_layout = QVBoxLayout()
        self.send_file_button = QPushButton("Send File")
        self.send_file_button.setObjectName("send_file_button")
        queue_area_layout.addWidget(self.send_file_button)
        self.file_queue_list = QListWidget()
        self.file_queue_list.setObjectName("file_queue_list")
        self.file_queue_list.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.file_queue_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.file_queue_list.setVerticalScrollBar(ModernScrollBar())
        self.file_queue_list.setMaximumWidth(200)
        self.file_queue_list.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        self.queue_layout = QVBoxLayout()
        self.queue_layout.addWidget(self.file_queue_list)
        self.queue_layout.setAlignment(Qt.AlignTop)
        self.queue_layout.setStretch(0, 1)
        queue_area_layout.addLayout(self.queue_layout)
        parent_layout.addLayout(queue_area_layout)

    def _setup_main_content_area(self, parent_layout):
        main_content_layout = QVBoxLayout()
        main_content_layout.setAlignment(Qt.AlignTop)
        self._setup_file_info_area(main_content_layout)
        self._setup_path_area(main_content_layout)
        self._setup_progress_area(main_content_layout)
        spacer = QSpacerItem(20, 20, QSizePolicy.Minimum, QSizePolicy.Expanding)
        main_content_layout.addItem(spacer)
        self._setup_status_area(main_content_layout)
        self._setup_output_area(main_content_layout)
        parent_layout.addLayout(main_content_layout)

    def _setup_file_info_area(self, parent_layout):
        self.file_info_layout = QVBoxLayout()
        self.file_name_label = QLabel("No File Selected")
        self.file_name_label.setObjectName("file_name_label")
        self.file_name_label.setAlignment(Qt.AlignLeft)
        self.file_info_layout.addWidget(self.file_name_label)
        self.file_size_label = QLabel("")
        self.file_size_label.setObjectName("file_size_label")
        self.file_size_label.setAlignment(Qt.AlignCenter)
        self.file_info_layout.addWidget(self.file_size_label)
        file_info_wrapper_layout = QHBoxLayout()
        file_info_wrapper_layout.addSpacing(130)
        file_info_wrapper_layout.addLayout(self.file_info_layout)
        file_info_wrapper_layout.addStretch(1)
        parent_layout.addLayout(file_info_wrapper_layout)

    def _setup_path_area(self, parent_layout):
        path_layout = QHBoxLayout()
        self.path_label = QLabel("File Path:")
        self.path_label.setStyleSheet("color: white;")
        path_layout.addWidget(self.path_label)
        self.path_entry = QLineEdit()
        self.path_entry.setObjectName("path_entry")
        path_layout.addWidget(self.path_entry)
        self.clear_path_button = QPushButton("🗑")
        self.clear_path_button.setObjectName("clear_path_button")
        self.clear_path_button.setFixedWidth(30)
        path_layout.addWidget(self.clear_path_button)
        parent_layout.addLayout(path_layout)

    def _setup_progress_area(self, parent_layout):
        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("progress_bar")
        self.progress_bar.setFixedHeight(20)
        self.progress_bar.setValue(0)
        parent_layout.addWidget(self.progress_bar)
        self.progress_info_layout = QHBoxLayout()
        self.progress_info_layout.setAlignment(Qt.AlignCenter)
        self.time_remaining_label = QLabel("")
        self.time_remaining_label.setObjectName("time_remaining_label")
        self.time_remaining_label.setAlignment(Qt.AlignCenter)
        self.progress_info_layout.addWidget(self.time_remaining_label)
        self.speed_label = QLabel("")
        self.speed_label.setObjectName("speed_label")
        self.speed_label.setAlignment(Qt.AlignCenter)
        self.progress_info_layout.addWidget(self.speed_label)
        parent_layout.addLayout(self.progress_info_layout)

    def _setup_status_area(self, parent_layout):
        self.status_frame = QFrame()
        self.status_frame.setObjectName("status_frame")
        self.status_layout = QHBoxLayout(self.status_frame)
        self.output_expand_button = QPushButton("^")
        self.output_expand_button.setObjectName("output_expand_button")
        self.output_expand_button.setFixedSize(30, 30)
        self.status_layout.addWidget(self.output_expand_button, alignment=Qt.AlignLeft)
        self.status_label = QLabel("")
        self.status_label.setObjectName("status_label")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_layout.addWidget(self.status_label, stretch=1)
        parent_layout.addWidget(self.status_frame)

    def _setup_output_area(self, parent_layout):
        self.output_text = QTextEdit()
        self.output_text.setObjectName("output_text")
        self.output_text.setVerticalScrollBar(ModernScrollBar())
        self.output_text.setHorizontalScrollBar(ModernScrollBar())
        self.output_text.setFixedHeight(80)
        self.output_text.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.output_text.setVisible(self.output_visible)
        parent_layout.addWidget(self.output_text)

    def _connect_signals(self):
        self.settings_button.clicked.connect(self.open_settings_popup)
        self.minimize_button.clicked.connect(self.showMinimized)
        self.close_button.clicked.connect(self.close)
        self.send_file_button.clicked.connect(self.open_file_dialog)
        self.path_entry.textChanged.connect(self._on_path_entry_changed)
        self.clear_path_button.clicked.connect(self.clear_all)
        self.dot_animation_timer.timeout.connect(self.update_dots)
        self.path_entry_timer.timeout.connect(self._process_debounced_path_entry)
        self.clear_message_timer.timeout.connect(self.clear_message_timeout)
        self.output_expand_button.clicked.connect(self.toggle_output)

    def _on_path_entry_changed(self, text):
        if self.initial_path_loaded and text:
            self.path_entry_timer.start(500)

    def _process_debounced_path_entry(self):
        text = self.path_entry.text()
        if not text:
            return
        path = text.strip().strip('"')
        if os.path.exists(path):
            self.add_file_to_queue(path)
            self.path_entry.blockSignals(True)
            self.path_entry.clear()
            self.path_entry.blockSignals(False)

    def toggle_output(self):
        self.output_visible = not self.output_visible
        self.output_text.setVisible(self.output_visible)
        self.output_expand_button.setText("v" if self.output_visible else "^")

    def load_settings_and_code(self):
        self.settings = self.load_settings()
        self.code = self.settings.get("code", None)
        if self.code is None:
            self.open_settings_popup()
            self.code = self.settings.get("code", None)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            if os.path.exists(file_path):
                if os.path.isdir(file_path):
                    self.add_folder_to_queue(file_path)
                else:
                    self.add_file_to_queue(file_path)
        event.acceptProposedAction()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and event.y() < self.title_bar_height:
            self.start_move_position = event.globalPos()
            self.window_position = self.pos()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self.start_move_position is not None and event.y() < self.title_bar_height:
            delta = event.globalPos() - self.start_move_position
            self.move(self.window_position + delta)
            event.accept()

    def mouseReleaseEvent(self, event):
        self.start_move_position = None
        event.accept()

    def closeEvent(self, event):
        for thread in self.active_threads:
            if hasattr(thread, 'close_process'):
                thread.close_process()
        event.accept()
        
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.resize_timer.start(100)

    def _apply_resize_styles(self):
        _set_gradient_background(self, extra_widgets=[self.title_bar])
        _set_rounded_window(self)

    def get_folder_size(self, folder_path):
        total_size = 0
        for dirpath, dirnames, filenames in os.walk(folder_path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                if not os.path.islink(fp):
                    total_size += os.path.getsize(fp)
        return total_size
        
    def update_queue_display(self):
        self.file_queue_list.clear()
        for file_path, queue_id, _total_expected_files in list(self.file_queue.queue):
            try:
                if os.path.isdir(file_path):
                    file_size = format_file_size(self.get_folder_size(file_path))
                else:
                    file_size = format_file_size(os.path.getsize(file_path))
            except OSError:
                file_size = "N/A"
            item_widget = QueueListItem(os.path.basename(file_path), file_size, queue_id, self.remove_from_queue)
            item = QListWidgetItem()
            item.setSizeHint(item_widget.sizeHint())
            self.file_queue_list.addItem(item)
            self.file_queue_list.setItemWidget(item, item_widget)

    def _remove_item_from_queue_by_id(self, queue_id):
        temp_queue = Queue()
        while not self.file_queue.empty():
            file_path_from_queue, id_from_queue, total_expected_files_from_queue = self.file_queue.get()
            if id_from_queue != queue_id:
                temp_queue.put((file_path_from_queue, id_from_queue, total_expected_files_from_queue))
        self.file_queue = temp_queue
        self.update_queue_display()

    def remove_from_queue(self, file_path, queue_id):
        self._remove_item_from_queue_by_id(queue_id)

    def update_progress_bar(self, progress, is_hashing):
        self.progress_bar.setProperty("is_hashing", is_hashing)
        self.progress_bar.setValue(progress)
        self.progress_bar.style().unpolish(self.progress_bar)
        self.progress_bar.style().polish(self.progress_bar)

    def update_speed(self, speed):
        self.speed_label.setText(f"{speed}")

    def update_time_remaining(self, time_remaining):
        self.time_remaining_label.setText(f"{time_remaining}")

    def clear_path(self):
        self.path_entry.clear()
        self.file_name_label.setText("No File Selected")
        self.file_size_label.setText("")

    def on_path_editing_finished(self):
        text = self.path_entry.text()
        if not text:
            return
        path = text.strip().strip('"')
        if os.path.exists(path):
            self.add_file_to_queue(path)
            self.path_entry.clear()

    def clear_all(self):
        for thread in self.active_threads:
            if hasattr(thread, 'close_process'):
                thread.is_cancelled = True
                thread.close_process()
            if thread.isRunning():
                thread.wait()
        self.active_threads = []
        self.output_text.clear()
        self.clear_path()
        self.status_label.setText("Cleared!")
        self.status_label.setProperty("status", "cleared")
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)
        self.progress_bar.setValue(0)
        self.speed_label.setText("")
        self.time_remaining_label.setText("")
        self.dot_animation_timer.stop()
        self.clear_message_timer.start(3000)
        self.is_sending = False
        self.current_file = None
        self.start_next_transfer()

    def clear_message_timeout(self):
        self.status_label.setText("")
        self.status_label.setProperty("status", "")
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)
        self.clear_message_timer.stop()

    def update_animated_status(self, message, color):
        self.current_status_message = message
        self.status_label.setFont(QFont("Arial", 12, QFont.Normal))
        if "Loading" in message or "Uploading" in message:
            status_prop = "sending"
        elif "Ready to Upload" in message:
            status_prop = "ready"
        else:
            status_prop = ""
        self.status_label.setProperty("status", status_prop)
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)
        self.dot_count = 0
        self.update_dots()
        if "Loading..." in message or "Uploading file..." in message:
            self.dot_animation_timer.start(500)
        else:
            self.dot_animation_timer.stop()

    def update_dots(self):
        if "Loading..." in self.current_status_message or "Uploading file..." in self.current_status_message:
            dots = "." * (self.dot_count % 4)
            self.status_label.setText(f"{self.current_status_message}{dots}")
            self.dot_count += 1
        else:
            self.status_label.setText(self.current_status_message)

    def load_initial_path(self):
        path = get_clipboard_path()
        if path:
            self.path_entry.setText(quote_path(path))
            self.add_file_to_queue(path)
        self.initial_path_loaded = True

    def open_file_dialog(self):
        options = QFileDialog.Options()
        options |= QFileDialog.ExistingFiles | QFileDialog.Directory
        file_paths, _ = QFileDialog.getOpenFileNames(self, "Select Files or Folders", "", "All Files (*);;Folders (*)",
                                                    options=options)
        if file_paths:
            for path in file_paths:
                if os.path.isdir(path):
                    self.add_folder_to_queue(path)
                else:
                    self.add_file_to_queue(path)

    def add_folder_to_queue(self, folder_path):
        self.add_file_to_queue(folder_path)

    def add_file_to_queue(self, file_path, total_expected_files=0):
        unique_id = str(uuid.uuid4())
        if total_expected_files == 0:
            if os.path.isfile(file_path):
                total_expected_files = 1
            elif os.path.isdir(file_path):
                for root, _, files in os.walk(file_path):
                    total_expected_files += len(files)
        self.file_queue.put((file_path, unique_id, total_expected_files))
        self.update_queue_display()
        if self.code is not None:
            self.start_next_transfer()

    def start_next_transfer(self):
        if not self.file_queue.empty() and not self.is_sending:
            self.is_sending = True
            filepath, queue_id, total_expected_files = self.file_queue.get()
            self.current_file = filepath
            code_prefix = self.code
            thread = SendFileThread(filepath, code_prefix, self, queue_id, total_expected_files)
            self.active_threads.append(thread)
            thread.output_signal.connect(lambda line: update_output(self.output_text, line))
            thread.finished_signal.connect(
                lambda success: handle_command_completion(success, self.status_label, self.progress_bar, self))
            thread.progress_signal.connect(
                lambda progress: self.update_progress_bar(progress, thread.is_hashing))
            thread.hashing_progress_signal.connect(
                lambda progress: self.update_progress_bar(progress, thread.is_hashing))
            thread.hashing_finished_signal.connect(lambda: self.update_progress_bar(100, False))
            thread.speed_signal.connect(self.update_speed)
            thread.status_update_signal.connect(lambda message, color: self.update_animated_status(message, color))
            thread.time_remaining_signal.connect(self.update_time_remaining)
            thread.current_file_signal.connect(self.update_current_file)
            thread.queue_id_signal.connect(self.remove_item_from_queue)
            thread.thread_finished_signal.connect(self.remove_finished_thread)
            self.progress_bar.setValue(0)
            thread.start()

    def update_current_file(self, file_name, file_size):
        self.file_name_label.setText(file_name)
        self.file_size_label.setText(f"({file_size})")
        self.speed_label.setText("")
        self.setWindowTitle(f"iMShare - {truncate_filename(file_name, 40)}")

    def remove_finished_thread(self, thread):
        if thread in self.active_threads:
            self.active_threads.remove(thread)

    def remove_item_from_queue(self, queue_id):
        self._remove_item_from_queue_by_id(queue_id)

    def center_window(self):
        qr = self.frameGeometry()
        cp = QDesktopWidget().availableGeometry().center()
        qr.moveCenter(cp)
        self.move(qr.topLeft())

    def open_settings_popup(self):
        settings_dialog = SettingsPopup(self, self.code if self.code else "")
        settings_dialog.exec_()

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
        self.code = code
        if not self.config_file:
            self.start_next_transfer()
            return
        self.settings["code"] = code
        try:
            with open(self.config_file, 'w') as file:
                json.dump(self.settings, file, indent=4)
        except (IOError, OSError, TypeError) as e:
            print(f"Failed to save settings: {e}")
        self.start_next_transfer()

if __name__ == '__main__':
    handle_instance_check()
    if is_windows():
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("myappid")
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(resource_path("iMShare.ico")))
    style_file = resource_path("upload.qss")
    if os.path.exists(style_file):
        with open(style_file, "r") as f:
            app.setStyleSheet(f.read())
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
