import tkinter as tk
from tkinter import colorchooser, filedialog
import ctypes
import random
import os
from PIL import Image, ImageDraw, ImageTk, ImageOps
from collections import deque
import sys
import logging

# --- Constants ---
# Paths
if getattr(sys, 'frozen', False):
    BASE_PATH = sys._MEIPASS
else:
    BASE_PATH = os.path.dirname(os.path.abspath(__file__))
ICONS_PATH = os.path.join(BASE_PATH, "draw-icons")

# Colors
COLOR_BLACK = 'black'
COLOR_WHITE = 'white'
COLOR_GREEN = 'green'
TRANSPARENT = (0, 0, 0, 0)

# Tools
TOOL_BRUSH = 'brush'
TOOL_CIRCLE = 'circle'
TOOL_SQUARE = 'square'
TOOL_LINE = 'line'
TOOLS = {
    TOOL_BRUSH: 'Brush',
    TOOL_CIRCLE: 'Circle',
    TOOL_SQUARE: 'Square',
    TOOL_LINE: 'Line'
}
# --- End Constants ---

class DrawingApp:
    def __init__(self, master):
        self.master = master
        self.icons_path = ICONS_PATH

        # Get screen dimensions for the current monitor
        self.screen_width, self.screen_height = self._get_monitor_dimensions()
        master.geometry(f"{self.screen_width}x{self.screen_height}+0+0")

        master.overrideredirect(True)
        master.attributes('-topmost', True)
        master.attributes("-transparentcolor", COLOR_BLACK)
        master.configure(bg=COLOR_BLACK)

        ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)

        self.color = COLOR_WHITE
        self.size = 5
        self.start_coords = None
        self.is_drawing = False
        self.erase_mode = False
        self.mirror_mode = False
        self.drawing_tool = TOOL_BRUSH
        self.random_color_mode = False

        # --- Off-screen buffer setup ---
        self.image = Image.new("RGBA", (self.screen_width, self.screen_height), TRANSPARENT)
        self.draw = ImageDraw.Draw(self.image)
        self.photo_image = ImageTk.PhotoImage(self.image)

        # --- History for Undo/Redo ---
        self.action_history = deque([self.image.copy()], maxlen=100)
        self.redo_history = deque(maxlen=100)

        self._create_canvas()

        self.controls_frame = self._init_controls()
        self.controls_frame.place(x=-200, y=10)
        self.hide_timer = None
        self.hovering_controls = False
        self._bind_events()
        self.master.bind("<Motion>", self._check_mouse_position)
        self.is_dragging = False

    def _get_monitor_dimensions(self):
        """Gets the dimensions of the monitor where the cursor is located."""
        try:
            class POINT(ctypes.Structure):
                _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
            class RECT(ctypes.Structure):
                _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                            ("right", ctypes.c_long), ("bottom", ctypes.c_long)]
            class MONITORINFO(ctypes.Structure):
                _fields_ = [("cbSize", ctypes.c_ulong), ("rcMonitor", RECT),
                            ("rcWork", RECT), ("dwFlags", ctypes.c_ulong)]
            point = POINT()
            ctypes.windll.user32.GetCursorPos(ctypes.byref(point))
            monitor = ctypes.windll.user32.MonitorFromPoint(point, 2) # MONITOR_DEFAULTTONEAREST
            monitor_info = MONITORINFO()
            monitor_info.cbSize = ctypes.sizeof(monitor_info)
            ctypes.windll.user32.GetMonitorInfoA(monitor, ctypes.byref(monitor_info))
            width = monitor_info.rcMonitor.right - monitor_info.rcMonitor.left
            height = monitor_info.rcMonitor.bottom - monitor_info.rcMonitor.top
            return width, height
        except Exception as e:
            logging.error(f"Error in multi-monitor setup: {e}")
            # Fallback to primary screen dimensions
            return self.master.winfo_screenwidth(), self.master.winfo_screenheight()

    def _create_canvas(self):
        """Create the main canvas and display the initial image."""
        self.canvas = tk.Canvas(self.master, bg=COLOR_BLACK, highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas_image = self.canvas.create_image(0, 0, anchor="nw", image=self.photo_image)

    def _update_canvas(self, image_to_display=None):
        """Update the canvas with the provided image or the main image."""
        img = image_to_display if image_to_display else self.image
        self.photo_image = ImageTk.PhotoImage(img)
        self.canvas.itemconfig(self.canvas_image, image=self.photo_image)

    def _check_mouse_position(self, event):
        if self.is_dragging: return
        if event.x <= 5 or self._is_mouse_over_controls(event): self._show_controls()
        elif self.controls_frame.winfo_x() == 0 and not self._is_mouse_over_controls(event): self._hide_controls()

    def _is_mouse_over_controls(self, event):
        x, y = event.x, event.y
        ctrl_x, ctrl_y = self.controls_frame.winfo_x(), self.controls_frame.winfo_y()
        width, height = self.controls_frame.winfo_width(), self.controls_frame.winfo_height()
        return ctrl_x <= x <= ctrl_x + width and ctrl_y <= y <= ctrl_y + height

    def _init_controls(self):
        controls_frame = tk.Frame(self.master, bg=COLOR_BLACK)
        self._create_tool_buttons(controls_frame)
        self._create_size_slider(controls_frame)
        self._create_mode_buttons(controls_frame)
        self._create_action_buttons(controls_frame)
        return controls_frame

    def _create_tool_buttons(self, parent):
        self.tool_buttons = {}
        for tool, text in TOOLS.items():
            btn = self._create_icon_button(parent, tool, text, lambda t=tool: self._set_tool(t))
            btn.pack(padx=5, pady=5, fill='x')
            self.tool_buttons[tool] = btn

    def _create_size_slider(self, parent):
        tk.Label(parent, text="Size:", bg=COLOR_BLACK, fg=COLOR_WHITE).pack(padx=5, pady=5, fill='x')
        self.size_scale = tk.Scale(parent, from_=1, to=100, orient=tk.VERTICAL, command=self._change_size, length=100, showvalue=1, sliderlength=15, highlightthickness=0, troughcolor=COLOR_BLACK, fg=COLOR_WHITE, bg=COLOR_BLACK)
        self.size_scale.set(self.size)
        self.size_scale.pack(padx=5, pady=5, fill='x')

    def _create_mode_buttons(self, parent):
        self.erase_button = self._create_icon_button(parent, 'erase', "Erase", self._toggle_erase_mode)
        self.erase_button.pack(padx=5, pady=5, fill='x')
        self.mirror_button = self._create_icon_button(parent, 'mirror', "Mirror", self._toggle_mirror_mode)
        self.mirror_button.pack(padx=5, pady=5, fill='x')
        self.random_color_button = self._create_icon_button(parent, 'random', "RANDOM", self._toggle_random_color_mode)
        self.random_color_button.pack(padx=5, pady=5, fill='x')

    def _create_action_buttons(self, parent):
        self._create_icon_button(parent, 'clear', "Clear All", self._clear_all).pack(padx=5, pady=5, fill='x')
        self._create_icon_button(parent, 'save', "Save", self._save_image).pack(padx=5, pady=5, fill='x')

    def _show_controls(self, event=None):
        if self.hide_timer: self.master.after_cancel(self.hide_timer)
        self.controls_frame.place(x=0, y=10)
        self.hovering_controls = True

    def _hide_controls(self, event=None):
        self.hovering_controls = False
        self.hide_timer = self.master.after(300, lambda: self.controls_frame.place(x=-self.controls_frame.winfo_width(), y=10))

    def _create_icon_button(self, parent, icon_name, text, command):
        icon_path = os.path.join(self.icons_path, f'{icon_name}.ico')
        try:
            icon = ImageTk.PhotoImage(Image.open(icon_path))
            btn = tk.Button(parent, image=icon, command=lambda: [command(), self.canvas.focus_set()], bg=COLOR_BLACK, relief=tk.FLAT, bd=0)
            btn.image = icon
        except Exception as e:
            logging.warning(f"Could not load icon: {icon_path}. Error: {e}")
            btn = tk.Button(parent, text=text, command=lambda: [command(), self.canvas.focus_set()], bg=COLOR_BLACK, relief=tk.FLAT, bd=0, fg=COLOR_WHITE)
        return btn

    def _bind_events(self):
        self.canvas.bind('<Button-1>', self._start_draw)
        self.canvas.bind('<B1-Motion>', self._draw)
        self.canvas.bind('<ButtonRelease-1>', self._stop_draw)
        self.canvas.bind('<ButtonPress-3>', self._open_color_picker)
        self.master.bind('<Escape>', self._quit)
        self.master.bind('<Control-z>', self._undo)
        self.master.bind('<Control-y>', self._redo)

    def _set_tool(self, tool):
        self.drawing_tool = tool
        for t, button in self.tool_buttons.items():
            button.configure(bg=COLOR_GREEN if t == tool else COLOR_BLACK)

    def _toggle_erase_mode(self):
        self.erase_mode = not self.erase_mode
        self.erase_button.configure(bg=COLOR_GREEN if self.erase_mode else COLOR_BLACK)

    def _toggle_mirror_mode(self):
        self.mirror_mode = not self.mirror_mode
        self.mirror_button.configure(bg=COLOR_GREEN if self.mirror_mode else COLOR_BLACK)

    def _toggle_random_color_mode(self):
        self.random_color_mode = not self.random_color_mode
        self.random_color_button.configure(bg=COLOR_GREEN if self.random_color_mode else COLOR_BLACK)

    def _start_draw(self, event):
        if self.random_color_mode: self.color = f'#{random.randint(0, 0xFFFFFF):06x}'
        self.is_drawing = True
        self.start_coords = event.x, event.y
        self.redo_history.clear()

    def _draw(self, event):
        if not self.is_drawing: return
        x, y = event.x, event.y

        draw_color = TRANSPARENT if self.erase_mode else self.color

        if self.drawing_tool == TOOL_BRUSH:
            self.draw.line([self.start_coords, (x, y)], fill=draw_color, width=self.size, joint='curve')
            if self.mirror_mode:
                mirror_start = (self.screen_width - self.start_coords[0], self.start_coords[1])
                mirror_end = (self.screen_width - x, y)
                self.draw.line([mirror_start, mirror_end], fill=draw_color, width=self.size, joint='curve')
            self.start_coords = (x, y)
            self._update_canvas()
        else: # Shape tools
            temp_image = self.image.copy()
            temp_draw = ImageDraw.Draw(temp_image)
            getattr(self, f'_draw_{self.drawing_tool}')(temp_draw, self.start_coords, (x, y), draw_color, self.size)
            if self.mirror_mode:
                mirror_start = (self.screen_width - self.start_coords[0], self.start_coords[1])
                mirror_end = (self.screen_width - x, y)
                getattr(self, f'_draw_{self.drawing_tool}')(temp_draw, mirror_start, mirror_end, draw_color, self.size)
            self._update_canvas(temp_image)

    def _stop_draw(self, event):
        if not self.is_drawing: return
        self.is_drawing = False
        end_coords = event.x, event.y
        draw_color = TRANSPARENT if self.erase_mode else self.color

        if self.drawing_tool != TOOL_BRUSH:
            getattr(self, f'_draw_{self.drawing_tool}')(self.draw, self.start_coords, end_coords, draw_color, self.size)
            if self.mirror_mode:
                mirror_start = (self.screen_width - self.start_coords[0], self.start_coords[1])
                mirror_end = (self.screen_width - end_coords[0], end_coords[1])
                getattr(self, f'_draw_{self.drawing_tool}')(self.draw, mirror_start, mirror_end, draw_color, self.size)

        self.action_history.append(self.image.copy())
        self.start_coords = None
        self._update_canvas()

    def _draw_line(self, draw_context, start, end, color, width):
        draw_context.line([start, end], fill=color, width=width)

    def _draw_circle(self, draw_context, start, end, color, width):
        r = ((end[0] - start[0]) ** 2 + (end[1] - start[1]) ** 2) ** 0.5
        draw_context.ellipse([start[0] - r, start[1] - r, start[0] + r, start[1] + r], outline=color, width=width)

    def _draw_square(self, draw_context, start, end, color, width):
        draw_context.rectangle([start, end], outline=color, width=width)

    def _open_color_picker(self, event):
        if event.num == 3:
            color_data = colorchooser.askcolor(title="Pick a color", color=self.color)
            if color_data and color_data[1]:
                self.color = color_data[1]
                self.erase_mode = False
                self.erase_button.configure(bg=COLOR_BLACK)

    def _change_size(self, value):
        self.size = int(value)

    def _clear_all(self):
        self.action_history.append(self.image.copy())
        self.redo_history.clear()
        self.image = Image.new("RGBA", (self.screen_width, self.screen_height), TRANSPARENT)
        self.draw = ImageDraw.Draw(self.image)
        self._update_canvas()

    def _undo(self, event=None):
        if len(self.action_history) > 1:
            self.redo_history.append(self.action_history.pop())
            self.image = self.action_history[-1].copy()
            self.draw = ImageDraw.Draw(self.image)
            self._update_canvas()

    def _redo(self, event=None):
        if self.redo_history:
            self.image = self.redo_history.pop().copy()
            self.action_history.append(self.image.copy())
            self.draw = ImageDraw.Draw(self.image)
            self._update_canvas()

    def _save_image(self):
        file_path = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG files", "*.png"), ("All files", "*.*")])
        if not file_path: return
        
        # Create a white background image
        white_bg = Image.new("RGBA", self.image.size, "WHITE")
        # Composite the drawing over the white background
        final_image = Image.alpha_composite(white_bg, self.image)

        final_image.save(file_path)

    def _quit(self, event=None):
        self.master.quit()

if __name__ == "__main__":
    root = tk.Tk()
    DrawingApp(root)
    root.mainloop()
