import sys
import os
import ctypes
import logging
from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QPixmap, QImage
import requests
from PIL import Image, UnidentifiedImageError
from io import BytesIO
import pyperclip

# --- Constants ---
# --- UI ---
WINDOW_TITLE_LOADING = "Loading..."
WINDOW_TITLE_UPLOADER = "Imgur Uploader"
LOADING_TEXT = "Loading..."
BASE_STYLE = "QWidget { background-color: #2b2b2b; border-radius: 15px; color: #f0f0f0; font-family: 'Arial'; }"
PREVIEW_BORDER_STYLE = "border: 2px solid #555;"
STATUS_SUCCESS_STYLE = "QLabel { background-color: #4CAF50; color: white; border-radius: 10px; padding: 5px 10px; font-size: 20px; }"
PREVIEW_SIZE = (150, 150)
SPLASH_TIMEOUT = 300
STATUS_TIMEOUT = 1000
SUCCESS_ICON = "✔"

# --- API ---
IMGUR_API_URL = "https://api.imgur.com/3/image"
IMGUR_CLIENT_ID = "07d8ebac38608e9" # This should ideally be stored more securely

# --- End Constants ---

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class SplashScreen(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(WINDOW_TITLE_LOADING)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet(BASE_STYLE)
        self.layout = QVBoxLayout(self)
        self.layout.setAlignment(Qt.AlignCenter)
        loading_label = QLabel(LOADING_TEXT, self)
        loading_label.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(loading_label)
        self.center_window()

    def center_window(self):
        qr = self.frameGeometry()
        cp = QApplication.desktop().screenGeometry().center()
        qr.moveCenter(cp)
        self.move(qr.topLeft())

    def close_self(self):
        self.close()

    def show_and_close(self, timeout=SPLASH_TIMEOUT):
        self.show()
        QTimer.singleShot(timeout, self.close_self)
        QTimer.singleShot(timeout + 10, self.release)

    def release(self):
         self.deleteLater()

class ImgurUploader(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle(WINDOW_TITLE_UPLOADER)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet(BASE_STYLE)

        self.layout = QVBoxLayout(self)
        self.layout.setAlignment(Qt.AlignCenter)

        self.preview_label = QLabel(self)
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setFixedSize(PREVIEW_SIZE[0], PREVIEW_SIZE[1])
        self.layout.addWidget(self.preview_label)
        self.preview_label.setStyleSheet(PREVIEW_BORDER_STYLE)

        self.upload_status_label = QLabel(self)
        self.upload_status_label.setAlignment(Qt.AlignCenter)
        self.upload_status_label.hide()
        self.layout.addWidget(self.upload_status_label)
        self.show()

        self.upload_worker = ImageUploadWorker()
        self.upload_worker.finished_signal.connect(self.handle_upload_complete)

        self.image_path = None
        QTimer.singleShot(10, self.start_upload)
        self.center_window()


    def center_window(self):
        qr = self.frameGeometry()
        cp = QApplication.desktop().screenGeometry().center()
        qr.moveCenter(cp)
        self.move(qr.topLeft())

    def start_upload(self):
        clipboard_text = pyperclip.paste()
        self.image_path = clipboard_text.strip().strip('"')

        if not self.image_path or not os.path.exists(self.image_path):
             logging.warning("No valid image path found in clipboard.")
             self.close()
             return

        QTimer.singleShot(10, self.load_preview_image)
        self.upload_worker.set_image_path(self.image_path)
        self.upload_worker.start()

    def load_preview_image(self):
        try:
            image = Image.open(self.image_path)
            image.thumbnail(PREVIEW_SIZE)
            img_byte_array = BytesIO()
            image.save(img_byte_array, format="PNG")
            qimage = QImage.fromData(img_byte_array.getvalue())
            pixmap = QPixmap.fromImage(qimage)
            self.preview_label.setPixmap(pixmap)
        except UnidentifiedImageError:
            logging.error(f"Cannot identify image file: {self.image_path}")
            self.close()
        except Exception as e:
            logging.error(f"Error loading preview image: {e}")
            self.close()

    def handle_upload_complete(self, link):
        if link:
            pyperclip.copy(link)
            self.show_upload_status()
        else:
            logging.error("Upload failed, no link received.")
            self.close()

    def show_upload_status(self):
        self.upload_status_label.setText(SUCCESS_ICON)
        self.upload_status_label.setStyleSheet(STATUS_SUCCESS_STYLE)
        self.upload_status_label.show()
        QTimer.singleShot(STATUS_TIMEOUT, self.close)

class ImageUploadWorker(QThread):
    finished_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.image_path = None

    def set_image_path(self, image_path):
        self.image_path = image_path

    def run(self):
        if not self.image_path:
            self.finished_signal.emit(None)
            return

        try:
            with open(self.image_path, 'rb') as f:
                response = requests.post(
                    IMGUR_API_URL,
                    headers={"Authorization": f"Client-ID {IMGUR_CLIENT_ID}"},
                    files={"image": f}
                )
            response.raise_for_status()
            data = response.json()

            if data.get('success') and 'link' in data.get('data', {}):
                self.finished_signal.emit(data['data']['link'])
            else:
                logging.error(f"Imgur API response indicates failure: {data}")
                self.finished_signal.emit(None)

        except requests.exceptions.RequestException as e:
            logging.error(f"Network error during upload: {e}")
            self.finished_signal.emit(None)
        except Exception as e:
            logging.error(f"An unexpected error occurred during upload: {e}")
            self.finished_signal.emit(None)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    splash = SplashScreen()
    splash.show_and_close()
    uploader = ImgurUploader()
    sys.exit(app.exec_())
