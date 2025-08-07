import pyautogui
import pyperclip
import tkinter as tk
from pynput import mouse, keyboard
from colorama import init, Fore, Style
import ctypes
import os
import sys
import math
import logging

# --- Constants ---
# GUI
CANVAS_WIDTH = 200
CANVAS_HEIGHT = 200
PIXEL_MODE_PIXEL_SIZE = 32
NORMAL_MODE_REGION_SIZE = 100
UPDATE_INTERVAL = 50  # ms
POSITION_UPDATE_INTERVAL = 10 #ms
WINDOW_OFFSET = 10

# Colors
TRANSPARENT_COLOR = "white"
OUTLINE_COLOR = "black"

# Modes
MODE_NORMAL = 'normal'
MODE_PIXEL = 'pixel'

# --- End Constants ---

init()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class ColorWindow:
    def __init__(self):
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.attributes('-topmost', True)
        self.root.attributes("-transparentcolor", TRANSPARENT_COLOR)
        self.canvas_width = CANVAS_WIDTH
        self.canvas_height = CANVAS_HEIGHT
        self.canvas = tk.Canvas(self.root, width=self.canvas_width, height=self.canvas_height, bg=TRANSPARENT_COLOR, highlightthickness=0)
        self.canvas.pack()
        self.circle = self.canvas.create_oval(0, 0, self.canvas_width, self.canvas_height, fill=TRANSPARENT_COLOR, outline=OUTLINE_COLOR, width=2)
        self.highlighted_pixel = None
        self.root.bind("<ButtonPress-1>", self.start_drag)
        self.root.bind("<B1-Motion>", self.drag)
        self.mode = MODE_NORMAL
        self.last_x = None
        self.last_y = None
        self.update_position()

    def start_drag(self, event):
        self.drag_start_x = event.x
        self.drag_start_y = event.y
        self.last_x = self.root.winfo_pointerx()
        self.last_y = self.root.winfo_pointery()

    def drag(self, event):
        dx = self.root.winfo_pointerx() - self.last_x
        dy = self.root.winfo_pointery() - self.last_y
        x = self.root.winfo_x() + dx
        y = self.root.winfo_y() + dy
        self.root.geometry(f"+{x}+{y}")
        self.last_x = self.root.winfo_pointerx()
        self.last_y = self.root.winfo_pointery()

    def update_position(self):
        x, y = pyautogui.position()
        screen_width, screen_height = pyautogui.size()

        if self.last_x == x and self.last_y == y:
             self.root.after(POSITION_UPDATE_INTERVAL, self.update_position)
             return
        
        self.last_x = x
        self.last_y = y

        offset_x = WINDOW_OFFSET
        offset_y = WINDOW_OFFSET
        if y + self.canvas_height + offset_y > screen_height:
            offset_y = -self.canvas_height - WINDOW_OFFSET
        
        if x + self.canvas_width + offset_x > screen_width:
             offset_x = -self.canvas_width - WINDOW_OFFSET

        self.root.geometry(f"+{x + offset_x}+{y + offset_y}")
        self.root.after(POSITION_UPDATE_INTERVAL, self.update_position)

    def update_canvas_size(self, width, height):
        self.canvas_width = width
        self.canvas_height = height
        self.canvas.config(width=self.canvas_width, height=self.canvas_height)
        self.canvas.delete("all")
        if self.mode == MODE_NORMAL:
            self.circle = self.canvas.create_oval(0, 0, self.canvas_width, self.canvas_height, fill=TRANSPARENT_COLOR, outline=OUTLINE_COLOR, width=2)

    def update_color(self):
        try:
            if self.mode == MODE_NORMAL:
                self._update_normal_mode()
            elif self.mode == MODE_PIXEL:
                self._update_pixel_mode()
        except Exception as e:
            logging.error(f"Error updating color: {e}")
        finally:
            self.root.after(UPDATE_INTERVAL, self.update_color)

    def _update_normal_mode(self):
        x, y = pyautogui.position()
        self.canvas.delete(self.highlighted_pixel) if self.highlighted_pixel else None
        screenshot = pyautogui.screenshot(region=(x - NORMAL_MODE_REGION_SIZE // 2, y - NORMAL_MODE_REGION_SIZE // 2, NORMAL_MODE_REGION_SIZE, NORMAL_MODE_REGION_SIZE))
        pixel_color = screenshot.getpixel((NORMAL_MODE_REGION_SIZE // 2, NORMAL_MODE_REGION_SIZE // 2))
        hex_color = '#{:02x}{:02x}{:02x}'.format(*pixel_color)
        self.canvas.itemconfig(self.circle, fill=hex_color)
        self.root.config(bg=hex_color)

    def _update_pixel_mode(self):
        x, y = pyautogui.position()
        self.canvas.delete("all")
        radius = min(self.canvas_width, self.canvas_height) / 2
        center_x = self.canvas_width / 2
        center_y = self.canvas_height / 2

        screenshot_size = int(radius * 2)
        screenshot_x = int(x - radius)
        screenshot_y = int(y - radius)
        screenshot = pyautogui.screenshot(region=(screenshot_x, screenshot_y, screenshot_size, screenshot_size))

        for px_y in range(0, self.canvas_height, PIXEL_MODE_PIXEL_SIZE):
            for px_x in range(0, self.canvas_width, PIXEL_MODE_PIXEL_SIZE):
                dist_x = px_x - center_x + PIXEL_MODE_PIXEL_SIZE / 2
                dist_y = px_y - center_y + PIXEL_MODE_PIXEL_SIZE / 2
                dist_center = math.sqrt(dist_x**2 + dist_y**2)

                if dist_center <= radius:
                    screenshot_px_x = int((px_x / self.canvas_width) * screenshot_size)
                    screenshot_px_y = int((px_y / self.canvas_height) * screenshot_size)
                    pixel_color = screenshot.getpixel((screenshot_px_x, screenshot_px_y))
                    hex_color = '#{:02x}{:02x}{:02x}'.format(*pixel_color)
                    self.canvas.create_rectangle(px_x, px_y, px_x + PIXEL_MODE_PIXEL_SIZE, px_y + PIXEL_MODE_PIXEL_SIZE, fill=hex_color, outline="")

        highlight_size = PIXEL_MODE_PIXEL_SIZE * 2
        highlight_x = center_x - highlight_size // 2
        highlight_y = center_y - highlight_size // 2

        pixel_color = screenshot.getpixel((screenshot_size // 2, screenshot_size // 2))
        hex_color = '#{:02x}{:02x}{:02x}'.format(*pixel_color)

        if self.highlighted_pixel:
           self.canvas.delete(self.highlighted_pixel)

        self.highlighted_pixel = self.canvas.create_rectangle(highlight_x, highlight_y, highlight_x + highlight_size, highlight_y + highlight_size, fill=hex_color, outline=TRANSPARENT_COLOR, width=2)
        self.canvas.create_oval(0, 0, self.canvas_width, self.canvas_height, outline=TRANSPARENT_COLOR, width=2)
        self.root.config(bg=hex_color)

    def stop(self):
        self.root.quit()

def print_colored(text, color):
    colored_text = f"{getattr(Fore, color.upper(), '')}{text}{Style.RESET_ALL}"
    print(colored_text)


def get_color_hex():
    title = "iMColor"
    print_colored(title.center(110), 'white')
    print_colored("Right-click to copy HEX".center(110), 'cyan')
    color_window = ColorWindow()
    color_window.update_color()

    def on_click(x, y, button, pressed):
        if pressed and button == mouse.Button.right:
            try:
                screenshot = pyautogui.screenshot(region=(x, y, 1, 1))
                pixel_color = screenshot.getpixel((0, 0))
                hex_color = '#{:02x}{:02x}{:02x}'.format(*pixel_color)
                pyperclip.copy(hex_color)
                print_colored(f"Hex code: {hex_color} copied to clipboard.".center(110), hex_color)
            except Exception as e:
                logging.error(f"Error copying color: {e}")
    
    def on_scroll(x, y, dx, dy):
        if dy > 0:  
            color_window.mode = MODE_PIXEL
            color_window.update_canvas_size(CANVAS_WIDTH, CANVAS_HEIGHT)
        elif dy < 0:  
            color_window.mode = MODE_NORMAL
            color_window.update_canvas_size(CANVAS_WIDTH, CANVAS_HEIGHT)

    def on_press(key):
        if key == keyboard.Key.esc:
            mouse_listener.stop()
            keyboard_listener.stop()
            color_window.stop()

    mouse_listener = mouse.Listener(on_click=on_click, on_scroll=on_scroll)
    keyboard_listener = keyboard.Listener(on_press=on_press)
    mouse_listener.start()
    keyboard_listener.start()

    color_window.root.mainloop()

    mouse_listener.join()
    keyboard_listener.join()


if __name__ == "__main__":
    if os.path.splitext(sys.argv[0])[1] != '.pyw':
        ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 6)
    get_color_hex()
