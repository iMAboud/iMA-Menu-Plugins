import tkinter as tk
from tkinter import colorchooser
import ctypes
import random
import os
from PIL import Image, ImageDraw, ImageTk
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
        self._setup_multimonitor()
        master.attributes('-fullscreen', True, '-topmost', True, '-alpha', 0.7)
        master.configure(bg=COLOR_BLACK)
        ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)

        self.color = COLOR_WHITE
        self.size = 5
        self.start_coords = None
        self.is_drawing = False
        self.erase_mode = False
        self.mirror_mode = False
        self.drawing_tool = TOOL_BRUSH
        self.opacity = 0.7
        self.random_color_mode = False
        self.action_history = deque(maxlen=100)
        self.redo_history = deque(maxlen=100)
        self.current_stroke = []

        self._create_canvases()

        self.controls_frame = self._init_controls()
        self.controls_frame.place(x=-200, y=10)
        self.hide_timer = None
        self.hovering_controls = False
        self._bind_events()
        self.master.bind("<Motion>", self._check_mouse_position)
        self.master.bind("<Button-1>", self._check_drag_start)
        self.master.bind("<ButtonRelease-1>", self._check_drag_end)
        self.is_dragging = False

    def _create_canvases(self):
        """Create the background and drawing canvases."""
        self.bg_canvas = tk.Canvas(self.master, bg=COLOR_BLACK, highlightthickness=0)
        self.bg_canvas.pack(fill=tk.BOTH, expand=True)
        self.draw_canvas = tk.Canvas(self.bg_canvas, bg=COLOR_BLACK, highlightthickness=0)
        self.draw_canvas.pack(fill=tk.BOTH, expand=True)

    def _setup_multimonitor(self):
        """
        Sets up multi-monitor support for the application window.
        This function attempts to detect the monitor where the cursor is currently
        located and resizes and positions the application window to fill that monitor.
        This is a Windows-specific implementation using ctypes.
        """
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
            monitor = ctypes.windll.user32.MonitorFromPoint(point, 2)
            monitor_info = MONITORINFO()
            monitor_info.cbSize = ctypes.sizeof(monitor_info)
            ctypes.windll.user32.GetMonitorInfoA(monitor, ctypes.byref(monitor_info))
            x = monitor_info.rcMonitor.left
            y = monitor_info.rcMonitor.top
            width = monitor_info.rcMonitor.right - monitor_info.rcMonitor.left
            height = monitor_info.rcMonitor.bottom - monitor_info.rcMonitor.top
            self.master.geometry(f"{width}x{height}+{x}+{y}")
        except Exception as e:
            logging.error(f"Error in multi-monitor setup: {e}")
            pass

    def _check_drag_start(self, event):
        self.is_dragging = True

    def _check_drag_end(self, event):
        self.is_dragging = False

    def _check_mouse_position(self, event):
        if self.is_dragging:
            return
        if event.x <= 5 or self._is_mouse_over_controls(event):
            self._show_controls()
        elif self.controls_frame.winfo_x() == 0 and not self._is_mouse_over_controls(event):
            self._hide_controls()

    def _is_mouse_over_controls(self, event):
        x, y = event.x, event.y
        ctrl_x, ctrl_y = self.controls_frame.winfo_x(), self.controls_frame.winfo_y()
        width, height = self.controls_frame.winfo_width(), self.controls_frame.winfo_height()
        return ctrl_x <= x <= ctrl_x + width and ctrl_y <= y <= ctrl_y + height

    def _init_controls(self):
        """Initializes the control panel."""
        controls_frame = tk.Frame(self.master, bg=COLOR_BLACK)
        self._create_tool_buttons(controls_frame)
        self._create_size_slider(controls_frame)
        self._create_mode_buttons(controls_frame)
        self._create_action_buttons(controls_frame)
        return controls_frame

    def _create_tool_buttons(self, parent):
        """Create the drawing tool buttons."""
        self.tool_buttons = {}
        for tool, text in TOOLS.items():
            btn = self._create_icon_button(parent, tool, text, lambda t=tool: self._set_tool(t))
            btn.pack(padx=5, pady=5, fill='x')
            self.tool_buttons[tool] = btn

    def _create_size_slider(self, parent):
        """Create the size slider."""
        tk.Label(parent, text="Size:", bg=COLOR_BLACK, fg=COLOR_WHITE).pack(padx=5, pady=5, fill='x')
        self.size_scale = tk.Scale(parent, from_=1, to=100, orient=tk.VERTICAL, command=self._change_size,
                                   length=100, showvalue=1, sliderlength=15, highlightthickness=0,
                                   troughcolor=COLOR_BLACK, fg=COLOR_WHITE, bg=COLOR_BLACK)
        self.size_scale.set(self.size)
        self.size_scale.pack(padx=5, pady=5, fill='x')

    def _create_mode_buttons(self, parent):
        """Create the mode-switching buttons (erase, mirror, random color)."""
        self.erase_button = self._create_icon_button(parent, 'erase', "Erase", self._toggle_erase_mode)
        self.erase_button.pack(padx=5, pady=5, fill='x')
        self.mirror_button = self._create_icon_button(parent, 'mirror', "Mirror", self._toggle_mirror_mode)
        self.mirror_button.pack(padx=5, pady=5, fill='x')
        self.random_color_button = self._create_icon_button(parent, 'random', "RANDOM", self._toggle_random_color_mode)
        self.random_color_button.pack(padx=5, pady=5, fill='x')

    def _create_action_buttons(self, parent):
        """Create action buttons like clear and save."""
        self._create_icon_button(parent, 'clear', "Clear All", self._clear_all).pack(padx=5, pady=5, fill='x')
        self._create_icon_button(parent, 'save', "Save", self._save_options).pack(padx=5, pady=5, fill='x')

    def _show_controls(self, event=None):
        if self.hide_timer:
            self.master.after_cancel(self.hide_timer)
        self.controls_frame.place(x=0, y=10)
        self.hovering_controls = True

    def _hide_controls(self, event=None):
        self.hovering_controls = False
        self.hide_timer = self.master.after(300, lambda: self.controls_frame.place(x=-self.controls_frame.winfo_width(), y=10))

    def _create_icon_button(self, parent, icon_name, text, command):
        icon_path = os.path.join(self.icons_path, f'{icon_name}.ico')
        try:
            icon = ImageTk.PhotoImage(Image.open(icon_path))
            btn = tk.Button(parent, image=icon, command=lambda: [command(), self.draw_canvas.focus_set()],
                            bg=COLOR_BLACK, relief=tk.FLAT, bd=0)
            btn.image = icon
        except Exception as e:
            logging.warning(f"Could not load icon: {icon_path}. Error: {e}")
            btn = tk.Button(parent, text=text, command=lambda: [command(), self.draw_canvas.focus_set()],
                            bg=COLOR_BLACK, relief=tk.FLAT, bd=0, fg=COLOR_WHITE)
        return btn

    def _bind_events(self):
        self.draw_canvas.bind('<Button-1>', self._start_draw)
        self.draw_canvas.bind('<B1-Motion>', self._draw)
        self.draw_canvas.bind('<ButtonRelease-1>', self._stop_draw)
        self.draw_canvas.bind('<ButtonPress-3>', self._open_color_picker)
        self.master.bind('<Escape>', self._quit)
        self.master.bind('<MouseWheel>', self._on_mousewheel)
        self.master.bind('<Control-z>', self._undo)
        self.master.bind('<Control-y>', self._redo)

    def _set_tool(self, tool):
        self.drawing_tool = tool
        for t, button in self.tool_buttons.items():
            button.configure(bg=COLOR_GREEN if t == tool else COLOR_BLACK)

    def _toggle_erase_mode(self):
        self.erase_mode = not self.erase_mode
        self.color = COLOR_BLACK if self.erase_mode else COLOR_WHITE
        self.erase_button.configure(bg=COLOR_GREEN if self.erase_mode else COLOR_BLACK)

    def _toggle_mirror_mode(self):
        self.mirror_mode = not self.mirror_mode
        self.mirror_button.configure(bg=COLOR_GREEN if self.mirror_mode else COLOR_BLACK)

    def _toggle_random_color_mode(self):
        self.random_color_mode = not self.random_color_mode
        self.random_color_button.configure(bg=COLOR_GREEN if self.random_color_mode else COLOR_BLACK)

    def _start_draw(self, event):
        if self.random_color_mode:
            self.color = f'#{random.randint(0, 0xFFFFFF):06x}'
        self.is_drawing = True
        self.start_coords = event.x, event.y
        self.current_stroke = []

    def _draw(self, event):
        if not self.is_drawing:
            return
        x, y = event.x, event.y
        if self.drawing_tool == TOOL_BRUSH:
            self._draw_brush(self.start_coords, (x, y))
            self.start_coords = (x, y)
        else:
            self.draw_canvas.delete('preview_shape')
            draw_func = getattr(self, f'_draw_{self.drawing_tool}')
            draw_func(self.start_coords, (x, y), preview=True)
            if self.mirror_mode:
                mirror_start = (self.draw_canvas.winfo_width() - self.start_coords[0], self.start_coords[1])
                mirror_end = (self.draw_canvas.winfo_width() - x, y)
                draw_func(mirror_start, mirror_end, preview=True)

    def _stop_draw(self, event):
        self.is_drawing = False
        end_coords = event.x, event.y
        draw_func = getattr(self, f'_draw_{self.drawing_tool}')

        if self.drawing_tool == TOOL_BRUSH:
            if self.current_stroke:
                self.action_history.append(('_draw_brush', self.current_stroke))
        else:
            self.draw_canvas.delete('preview_shape')
            action = (draw_func, self.start_coords, end_coords, self.size, self.color)
            self.action_history.append(action)
            draw_func(self.start_coords, end_coords)
            if self.mirror_mode:
                mirror_start = (self.draw_canvas.winfo_width() - self.start_coords[0], self.start_coords[1])
                mirror_end = (self.draw_canvas.winfo_width() - end_coords[0], end_coords[1])
                mirror_action = (draw_func, mirror_start, mirror_end, self.size, self.color)
                self.action_history.append(mirror_action)
                draw_func(mirror_start, mirror_end)

        self.start_coords = None
        self.current_stroke = []
        self.redo_history.clear()

    def _draw_line(self, start, end, preview=False):
        tag = 'preview_shape' if preview else ''
        return self.draw_canvas.create_line(*start, *end, fill=self.color, width=self.size, tags=tag)

    def _draw_circle(self, start, end, preview=False):
        tag = 'preview_shape' if preview else ''
        x0, y0 = start
        x1, y1 = end
        r = ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5
        return self.draw_canvas.create_oval(x0 - r, y0 - r, x0 + r, y0 + r, outline=self.color, width=self.size, tags=tag)

    def _draw_square(self, start, end, preview=False):
        tag = 'preview_shape' if preview else ''
        x0, y0 = start
        x1, y1 = end
        dx, dy = x1 - x0, y1 - y0
        side = max(abs(dx), abs(dy))
        x2 = x0 + side * (1 if dx >= 0 else -1)
        y2 = y0 + side * (1 if dy >= 0 else -1)
        return self.draw_canvas.create_rectangle(x0, y0, x2, y2, outline=self.color, width=self.size, tags=tag)

    def _draw_brush(self, start, end):
        color = COLOR_BLACK if self.erase_mode else self.color
        width = self.size * 2 if self.erase_mode else self.size
        line_id = self.draw_canvas.create_line(*start, *end, fill=color, width=width, capstyle=tk.ROUND, smooth=True)
        self.current_stroke.append({'points': (*start, *end), 'color': color, 'width': width})
        if self.mirror_mode:
            mirror_start = (self.draw_canvas.winfo_width() - start[0], start[1])
            mirror_end = (self.draw_canvas.winfo_width() - end[0], end[1])
            mirror_id = self.draw_canvas.create_line(*mirror_start, *mirror_end, fill=color, width=width, capstyle=tk.ROUND, smooth=True)
            self.current_stroke.append({'points': (*mirror_start, *mirror_end), 'color': color, 'width': width})

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
        self.draw_canvas.delete('all')
        self.action_history.clear()
        self.redo_history.clear()

    def _redraw_canvas(self):
        self.draw_canvas.delete('all')
        for action in self.action_history:
            if action[0] == '_draw_brush':
                for stroke in action[1]:
                    self.draw_canvas.create_line(stroke['points'], fill=stroke['color'], width=stroke['width'], capstyle=tk.ROUND, smooth=True)
            else:
                draw_func, start, end, size, color = action
                # Temporarily set properties for redraw
                original_color, self.color = self.color, color
                original_size, self.size = self.size, size
                draw_func(start, end)
                self.color, self.size = original_color, original_size

    def _undo(self, event=None):
        if self.action_history:
            self.redo_history.append(self.action_history.pop())
            self._redraw_canvas()

    def _redo(self, event=None):
        if self.redo_history:
            self.action_history.append(self.redo_history.pop())
            self._redraw_canvas()

    def _on_mousewheel(self, event):
        delta = 0.05 if event.delta > 0 else -0.05
        self.opacity = max(0.1, min(1.0, self.opacity + delta))
        self.master.attributes('-alpha', self.opacity)

    def _save_options(self):
        win = tk.Toplevel(self.master)
        win.title("Save Options")
        win.transient(self.master)
        win.grab_set()
        win.focus_set()
        tk.Button(win, text="Save PNG (Transparent)", command=lambda: self._save_image('transparent')).pack(padx=20, pady=10)
        tk.Button(win, text="Save PNG (White Background)", command=lambda: self._save_image('white')).pack(padx=20, pady=10)

    def _save_image(self, background='transparent'):
        self.master.withdraw()
        self.master.update_idletasks()
        width = self.draw_canvas.winfo_width()
        height = self.draw_canvas.winfo_height()
        image = Image.new('RGBA', (width, height), (255, 255, 255, 255) if background == 'white' else (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)

        for action in self.action_history:
            if action[0] == '_draw_brush':
                for stroke in action[1]:
                    draw.line(stroke['points'], fill=stroke['color'], width=int(stroke['width']), joint='curve')
            else:
                draw_func, start, end, size, color = action
                if draw_func == self._draw_line:
                    draw.line((*start, *end), fill=color, width=size)
                elif draw_func == self._draw_circle:
                    x0, y0 = start
                    x1, y1 = end
                    r = ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5
                    draw.ellipse((x0 - r, y0 - r, x0 + r, y0 + r), outline=color, width=size)
                elif draw_func == self._draw_square:
                    x0, y0 = start
                    x1, y1 = end
                    dx, dy = x1 - x0, y1 - y0
                    side = max(abs(dx), abs(dy))
                    x2 = x0 + side * (1 if dx >= 0 else -1)
                    y2 = y0 + side * (1 if dy >= 0 else -1)
                    draw.rectangle((x0, y0, x2, y2), outline=color, width=size)
        
        file_path = "drawing.png"
        image.save(file_path)
        self.master.deiconify()

    def _quit(self, event=None):
        self.master.quit()


if __name__ == "__main__":
    root = tk.Tk()
    DrawingApp(root)
    root.mainloop()
