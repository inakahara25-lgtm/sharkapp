import ctypes
import math
import os
import random
import textwrap
import traceback
import tkinter as tk
from pathlib import Path

VERSION = "8"

# Make Windows give us real screen pixels (avoids blurry scaling)
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

DEFAULT_NAME = "Hammer"
NAME_FILE = Path.home() / ".shark_tank_name.txt"
MESSAGES_FILE = Path.home() / "sharkpet_messages.txt"   # your own messages
LOG_FILE = Path.home() / "sharkpet_log.txt"             # errors end up here
KEY = "#010203"        # this exact color becomes see-through (and click-through)
SHARK_SCALE = 18       # shark size on the desktop; bigger = bigger shark
TANK_W, TANK_H = 560, 340

# trick name: (length in frames, swim-speed multiplier)
TRICKS = {
    "roll":     (45, 1.0),
    "spin":     (40, 0.4),
    "leap":     (50, 1.2),
    "backflip": (55, 1.0),
    "hop":      (54, 1.0),
    "dash":     (25, 5.0),
    "dance":    (70, 0.3),
    "moonwalk": (60, -0.9),
    "chase":    (60, 0.0),
    "shimmy":   (45, 0.0),
    "playdead": (100, 0.1),
}

# names shown in the "Pick a trick" menu
TRICK_LABELS = {
    "roll": "Barrel roll", "spin": "Spin", "leap": "Leap",
    "backflip": "Backflip", "hop": "Bunny hop", "dash": "Zoom!",
    "dance": "Dance", "moonwalk": "Moonwalk", "chase": "Chase tail",
    "shimmy": "Shimmy", "playdead": "Play dead",
}

# little things he says when he starts a trick
TRICK_SAYS = {
    "backflip": "Wheee!",
    "hop": "Boing!",
    "dash": "Zoom!",
    "dance": "\u266a \u266b \u266a",
    "moonwalk": "Smooth.",
    "chase": "Get back here, tail!",
    "playdead": "x_x",
}

# tricks that set the body angle themselves (no swim tilt on top)
ANGLE_TRICKS = ("spin", "leap", "backflip", "chase", "dance")

# things he says now and then (you can replace these with your own, see the
# "Edit messages..." option in the right-click menu)
MESSAGES = [
    "You got this!",
    "Keep going, you're doing great!",
    "Believe in yourself!",
    "One step at a time.",
    "Small progress is still progress.",
    "Take a deep breath.",
    "Don't forget to drink some water!",
    "Stretch break?",
    "You're stronger than you think.",
    "Proud of you!",
    "Today is a good day to try.",
    "Mistakes mean you're learning.",
    "Keep swimming!",
    "Dream big, swim bigger!",
    "Every expert was once a beginner.",
    "You've handled tough days before.",
    "Rest is productive too.",
    "You're doing better than you think.",
    "Don't stop now, you're amazing!",
    "Go get 'em!",
]


def load_name():
    try:
        name = NAME_FILE.read_text(encoding="utf-8").strip()
        return name or DEFAULT_NAME
    except OSError:
        return DEFAULT_NAME


def save_name(name):
    try:
        NAME_FILE.write_text(name, encoding="utf-8")
    except OSError:
        pass


def load_messages():
    """Your own messages if you made a file, otherwise the built-in ones."""
    try:
        lines = [ln.strip() for ln in
                 MESSAGES_FILE.read_text(encoding="utf-8").splitlines()]
        lines = [ln for ln in lines if ln and not ln.startswith("#")]
        if lines:
            return lines
    except OSError:
        pass
    return MESSAGES


def log_error(text):
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(text + "\n")
    except OSError:
        pass


def fit_scale(w, h):
    """Shark size that fits a window of this size."""
    return max(8, min(w / 31, h / 19))


def step_bubbles(c, bubbles):
    """Move and draw bubbles on canvas c; return the ones still on screen."""
    for b in bubbles:
        b[1] -= b[3]
        b[0] += math.sin(b[1] / 15) * 0.5
        c.create_oval(b[0] - b[2], b[1] - b[2], b[0] + b[2], b[1] + b[2],
                      outline="white", tags="dynamic")
    return [b for b in bubbles if b[1] > -10]


# =====================================================================
#  The shark
# =====================================================================
class Shark:
    def __init__(self, w, h, name):
        self.name = name
        self.mode = "free"     # "free" = desktop, or "tank"
        self.x = w // 2        # position in the current canvas's coordinates
        self.y = h // 2
        self.dir = 1
        self.speed = 1.8
        self.phase = 0.0
        self.s = SHARK_SCALE
        self.last_h = h
        self.tx = None
        self.ty = None

        # trick state
        self.trick = None
        self.trick_t = 0
        self.trick_dir = 1
        self.cooldown = 120
        self.jump_h = 0
        self.roll = 1.0
        self.angle = 0.0
        self.y_off = 0.0
        self.amp = 0.5
        self.x_off = 0.0
        self.pending_bubbles = []

        # speech bubble state
        self.say_text = None
        self.say_t = 0
        self.say_cooldown = 45       # says hi about a second after launch
        self.greeted = False
        self._last_said = None

    # ---- speech ----
    def say(self, text=None):
        if text is None:
            choices = [m for m in load_messages() if m != self._last_said]
            text = random.choice(choices or load_messages())
        self._last_said = text
        self.say_text = text
        self.say_t = min(220, 100 + 4 * len(text))     # frames on screen

    def tick_speech(self):
        if self.say_text:
            self.say_t -= 1
            if self.say_t <= 0:
                self.say_text = None
                self.say_cooldown = random.randint(900, 2700)   # ~30-90 s
        elif self.say_cooldown > 0:
            self.say_cooldown -= 1
        elif not self.greeted:
            self.greeted = True
            self.say(f"Hi, I'm {self.name}!")
        else:
            self.say()

    def draw_speech(self, c, x, cy):
        if not self.say_text:
            return
        s = self.s
        fs = max(9, int(s * 0.65))
        font = ("Arial", fs, "bold")
        text = textwrap.fill(self.say_text, 20)
        name_fs = max(9, int(s * 0.7))

        # above his name tag, or below him if there's no room at the top
        above = True
        t = c.create_text(x, cy - s * 2.4 - name_fs * 1.3 - 16, text=text,
                          anchor="s", justify="center", fill="#222222",
                          font=font, tags="dynamic")
        x0, y0, x1, y1 = c.bbox(t)
        if y0 - 8 < 0:
            c.delete(t)
            above = False
            t = c.create_text(x, cy + s * 2.3 + 16, text=text, anchor="n",
                              justify="center", fill="#222222", font=font,
                              tags="dynamic")
            x0, y0, x1, y1 = c.bbox(t)

        # keep the bubble inside the window
        cw = c.winfo_width()
        dx = 0
        if x0 - 8 < 2:
            dx = 2 - (x0 - 8)
        elif x1 + 8 > cw - 2:
            dx = (cw - 2) - (x1 + 8)
        if dx:
            c.move(t, dx, 0)
            x0, x1 = x0 + dx, x1 + dx

        c.create_rectangle(x0 - 8, y0 - 5, x1 + 8, y1 + 5, fill="white",
                           outline="#555555", width=2, tags="dynamic")
        # little tail pointing at the shark
        tx = min(max(x, x0 + 10), x1 - 10)
        if above:
            base, tip, cover = y1 + 5, y1 + 16, y1 + 4
        else:
            base, tip, cover = y0 - 5, y0 - 16, y0 - 4
        c.create_polygon(tx - 6, cover, tx + 6, cover,
                         tx, tip - (1 if above else -1),
                         fill="white", outline="", tags="dynamic")
        c.create_line(tx - 6, base, tx, tip, fill="#555555", width=2,
                      tags="dynamic")
        c.create_line(tx + 6, base, tx, tip, fill="#555555", width=2,
                      tags="dynamic")
        c.tag_raise(t)

    # ---- tricks ----
    def start_trick(self, name=None, force=False):
        if self.trick and not force:
            return
        self.trick = name or random.choice(list(TRICKS))
        self.trick_t = 0
        self.trick_dir = self.dir
        if self.trick in ("leap", "backflip"):
            self.jump_h = max(0, min(self.y - self.s * 3.5, self.last_h * 0.25))
            self.burst()
        if self.trick in TRICK_SAYS and not self.say_text:
            self.say(TRICK_SAYS[self.trick])

    def burst(self):
        for _ in range(6):
            self.pending_bubbles.append(
                (self.x + random.randint(-15, 15),
                 self.y + random.randint(-10, 10)))

    def pick_target(self, w, h, floor):
        mx, my = self.s * 4, self.s * 3.4
        for _ in range(10):
            self.tx = random.uniform(mx, max(mx + 1, w - mx))
            if abs(self.tx - self.x) > self.s * 6:
                break
        self.ty = random.uniform(my, max(my + 1, h - floor - my))

    # ---- per-frame update ----
    def update(self, w, h, floor, s, held=False):
        self.last_h = h
        self.s = s
        unit = s / 18
        self.tick_speech()

        if held:  # being carried: dangle by the head and wiggle
            self.phase += 0.7
            self.amp = 1.0
            self.roll, self.y_off, self.x_off = 1.0, 0.0, 0.0
            self.angle = -self.dir * (1.1 + 0.15 * math.sin(self.phase * 0.5))
            self.trick = None
            self.tx = None
            return

        swish, self.amp = 0.18, 0.5
        speed_mult = 1.0
        self.roll, self.angle, self.y_off = 1.0, 0.0, 0.0
        self.x_off = 0.0

        if self.trick:
            frames, speed_mult = TRICKS[self.trick]
            p = self.trick_t / frames
            if self.trick == "roll":
                self.roll = math.cos(4 * math.pi * p)
            elif self.trick == "spin":
                self.angle = self.trick_dir * 2 * math.pi * p
            elif self.trick == "leap":
                self.y_off = -math.sin(math.pi * p) * self.jump_h
                self.angle = -self.trick_dir * 0.7 * math.cos(math.pi * p)
            elif self.trick == "shimmy":
                swish, self.amp = 0.7, 1.0
            elif self.trick == "backflip":
                self.angle = -self.trick_dir * 2 * math.pi * p
                self.y_off = -math.sin(math.pi * p) * self.jump_h * 0.8
            elif self.trick == "playdead":
                swish, self.amp = 0.03, 0.1          # limp tail
                if p < 0.15:                         # flop over...
                    self.roll = math.cos(math.pi * p / 0.15)
                elif p < 0.85:                       # ...lie there...
                    self.roll = -1.0
                else:                                # ...and pop back up
                    self.roll = -math.cos(math.pi * (p - 0.85) / 0.15)
                self.y_off = -math.sin(math.pi * p) * self.s * 0.5
            elif self.trick == "chase":
                swish, self.amp = 0.5, 0.9
                phi = 2 * math.pi * 3 * p            # three quick circles
                self.angle = self.trick_dir * phi
                self.x_off = self.s * 1.2 * math.sin(phi)
                self.y_off = -self.s * 1.2 * (1 - math.cos(phi))
            elif self.trick == "dash":
                swish, self.amp = 0.5, 0.7
                if self.trick_t % 3 == 0:            # trail of bubbles
                    self.pending_bubbles.append(
                        (self.x - self.dir * 3.5 * self.s, self.y))
            elif self.trick == "dance":
                swish, self.amp = 0.5, 0.9
                self.angle = math.sin(2 * math.pi * p * 4) * 0.5
                self.y_off = math.sin(2 * math.pi * p * 8) * self.s * 0.15
            elif self.trick == "moonwalk":
                swish, self.amp = 0.25, 0.6
                self.y_off = math.sin(2 * math.pi * p * 3) * self.s * 0.1
            elif self.trick == "hop":
                swish = 0.3
                self.y_off = -abs(math.sin(3 * math.pi * p)) * self.s * 1.8
            self.trick_t += 1
            if self.trick_t >= frames:
                if self.trick in ("leap", "backflip", "hop"):
                    self.burst()
                self.trick = None
                self.cooldown = random.randint(90, 240)
        elif self.cooldown > 0:
            self.cooldown -= 1
        elif random.random() < 0.01:
            self.start_trick()

        # wander toward random spots
        if self.tx is None or abs(self.tx - self.x) < self.s:
            self.pick_target(w, h, floor)
        if not self.trick:
            self.dir = 1 if self.tx > self.x else -1

        vx = self.dir * self.speed * speed_mult * unit
        vy = (max(-1, min(1, (self.ty - self.y) / (self.s * 3)))
              * self.speed * 0.5 * abs(speed_mult) * unit)
        self.phase += swish
        self.x += vx
        self.y += vy

        # tilt nose up/down a little when swimming up/down
        if self.trick not in ANGLE_TRICKS:
            self.angle += self.dir * (vy / (self.speed * unit)) * 0.5

        # occasionally blow a bubble from the mouth
        if not self.trick and random.random() < 0.015:
            self.pending_bubbles.append((self.x + self.dir * 3.5 * self.s,
                                         self.y))

        mx, my = self.s * 4, self.s * 3.4
        self.x = max(mx, min(max(mx, w - mx), self.x))
        self.y = max(my, min(max(my, h - floor - my), self.y))

    def draw(self, c):
        s, d, x = self.s, self.dir, self.x + self.x_off
        cy = self.y + self.y_off
        w = math.sin(self.phase) * self.amp
        cos_a, sin_a = math.cos(self.angle), math.sin(self.angle)

        def tp(rx, ry):
            X, Y = d * rx * s, ry * self.roll * s
            return (x + X * cos_a - Y * sin_a, cy + X * sin_a + Y * cos_a)

        def pts(coords):
            out = []
            for rx, ry in coords:
                out += list(tp(rx, ry))
            return out

        belly_up = self.roll < 0
        body_col = "#e3e8ee" if belly_up else "#7b8794"
        fin_col = "#c5ccd6" if belly_up else "#5f6b78"

        c.create_polygon(pts([(-2.7, w), (-3.9, -1.1 + w * 1.5),
                              (-3.4, w * 1.3), (-3.6, 0.7 + w * 1.3)]),
                         fill=fin_col, outline="", tags="dynamic")
        c.create_polygon(pts([(0.8, -0.6), (0.2, -1.9), (-0.4, -0.6)]),
                         fill=fin_col, outline="", tags="dynamic")
        c.create_polygon(pts([(0.8, 0.6), (0.2, 1.9), (-0.4, 0.6)]),
                         fill=fin_col, outline="", tags="dynamic")
        c.create_polygon(pts([(2.5, -0.4), (1.5, -0.7), (0, -0.65),
                              (-1.5, -0.35), (-2.8, -0.15 + w),
                              (-2.8, 0.15 + w), (-1.5, 0.35),
                              (0, 0.65), (1.5, 0.7), (2.5, 0.4)]),
                         fill=body_col, outline="", smooth=True, tags="dynamic")
        c.create_polygon(pts([(2.4, -0.3), (2.7, -1.4), (3.3, -1.5),
                              (3.5, -1.2), (3.5, 1.2), (3.3, 1.5),
                              (2.7, 1.4), (2.4, 0.3)]),
                         fill=body_col, outline="", tags="dynamic")
        if not belly_up:
            r = max(2, s / 6)
            for ey in (-1.25, 1.25):
                ex_, ey_ = tp(3.3, ey)
                c.create_oval(ex_ - r, ey_ - r, ex_ + r, ey_ + r,
                              fill="black", outline="", tags="dynamic")

        c.create_text(x, cy - s * 2.4, text=self.name, fill="white",
                      font=("Arial", max(9, int(s * 0.7)), "bold"),
                      tags="dynamic")
        self.draw_speech(c, x, cy)


# =====================================================================
#  The fish tank window (closing it quits the app)
# =====================================================================
class TankWindow:
    def __init__(self, app, screen_w, screen_h):
        self.win = tk.Toplevel(app.win)
        self.win.title("Hammerhead Tank")
        self.win.minsize(300, 200)
        self.win.attributes("-topmost", True)
        self.w, self.h = TANK_W, TANK_H
        self.win.geometry(f"{self.w}x{self.h}+"
                          f"{max(0, screen_w - self.w - 40)}+"
                          f"{max(0, screen_h - self.h - 120)}")

        self.canvas = tk.Canvas(self.win, width=self.w, height=self.h,
                                bg="#1e90b8", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.bubbles = []

        self.draw_scenery()
        self.canvas.bind("<Configure>", self.on_resize)
        self.win.protocol("WM_DELETE_WINDOW", app.close)
        # keep the desktop shark layer above the tank window
        self.win.bind("<FocusIn>", lambda e: app.win.after(20, app.win.lift))

    @property
    def sand_h(self):
        return self.h * 0.12

    def on_resize(self, event):
        if event.width < 100 or event.height < 100:
            return  # minimizing can report a tiny size; ignore it
        self.w, self.h = event.width, event.height
        self.draw_scenery()

    def draw_scenery(self):
        c = self.canvas
        w, h = self.w, self.h
        c.delete("static")
        sand_top = h - self.sand_h
        k = h / 340

        c.create_rectangle(0, sand_top, w, h, fill="#e6d3a3",
                           outline="", tags="static")
        for fx in (0.11, 0.39, 0.77, 0.90):
            sx = w * fx
            for i in range(3):
                off = i * 8
                c.create_line(sx + off, sand_top + 5,
                              sx + off - 6, sand_top - (40 + i * 10) * k,
                              sx + off + 4, sand_top - (70 + i * 10) * k,
                              smooth=True, width=4, fill="#2e8b57",
                              tags="static")
        for fx in (0.25, 0.59):
            rx = w * fx
            c.create_oval(rx, sand_top - 8, rx + 30, sand_top + 14,
                          fill="#808080", outline="", tags="static")
        c.tag_lower("static")

    def add_bubble(self, x, y):
        self.bubbles.append([x, y, random.randint(2, 5),
                             random.uniform(0.8, 1.8)])

    def step(self):
        if random.random() < 0.05:
            self.add_bubble(random.randint(20, max(21, int(self.w) - 20)),
                            self.h - self.sand_h)
        self.bubbles = step_bubbles(self.canvas, self.bubbles)


# =====================================================================
#  The app: desktop layer + tank + dragging + menu
# =====================================================================
class SharkApp:
    def __init__(self, root):
        self.win = root
        self.win.title("Shark Pet")
        self.win.overrideredirect(True)                 # no title bar
        self.win.attributes("-topmost", True)           # float above everything
        self.win.attributes("-transparentcolor", KEY)   # Windows only

        self.sw = root.winfo_screenwidth()
        self.sh = root.winfo_screenheight()
        self.win.geometry(f"{self.sw}x{self.sh}+0+0")

        self.canvas = tk.Canvas(root, width=self.sw, height=self.sh,
                                bg=KEY, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        self.shark = Shark(self.sw, self.sh, load_name())
        self.free_bubbles = []
        self.tank = None
        self.job = None
        self.error_count = 0

        # dragging state
        self.held = False
        self.moved = 0.0
        self.press = (0, 0)
        self.grab_off = (0, 0)

        # right-click menu state
        self.menu_win = None
        self.menu_job = None
        self.menu_out = 0

        self.bind_canvas(self.canvas, "free")
        self.open_tank()
        self.animate()

    # ---------- windows ----------
    def bind_canvas(self, canvas, mode):
        canvas.bind("<ButtonPress-1>", lambda e: self.on_press(e, mode))
        canvas.bind("<B1-Motion>", self.on_drag)
        canvas.bind("<ButtonRelease-1>", self.on_release)
        canvas.bind("<Double-Button-1>", lambda e: self.on_double(e, mode))
        canvas.bind("<Button-3>", self.on_right_click)

    def open_tank(self):
        if self.tank is not None:
            return
        self.tank = TankWindow(self, self.sw, self.sh)
        self.bind_canvas(self.tank.canvas, "tank")

    def eject(self, pos=None):
        """Put the shark back on the desktop (at pos, or screen center)."""
        sh = self.shark
        sh.mode = "free"
        sh.x, sh.y = pos if pos else (self.sw // 2, self.sh // 2)
        sh.tx = None
        sh.pending_bubbles.clear()

    # ---------- coordinate helpers ----------
    def canvas_for(self, mode):
        if mode == "tank" and self.tank is not None:
            return self.tank.canvas
        return self.canvas

    def to_screen(self, x, y, mode):
        c = self.canvas_for(mode)
        return x + c.winfo_rootx(), y + c.winfo_rooty()

    def to_local(self, sx, sy, mode):
        c = self.canvas_for(mode)
        return sx - c.winfo_rootx(), sy - c.winfo_rooty()

    def in_tank(self, cx, cy):
        t = self.tank
        if t is None or t.win.state() != "normal":
            return False
        x0, y0 = t.canvas.winfo_rootx(), t.canvas.winfo_rooty()
        return (x0 <= cx < x0 + t.canvas.winfo_width()
                and y0 <= cy < y0 + t.canvas.winfo_height())

    # ---------- mouse: pick up, carry, drop ----------
    def hit(self, event, mode):
        sh = self.shark
        return (sh.mode == mode and abs(event.x - sh.x) < sh.s * 4
                and abs(event.y - sh.y) < sh.s * 2)

    def on_press(self, event, mode):
        if not self.hit(event, mode):
            return
        sh = self.shark
        sx, sy = self.to_screen(sh.x, sh.y, sh.mode)
        self.held = True
        self.moved = 0.0
        self.press = (event.x_root, event.y_root)
        self.grab_off = (sx - event.x_root, sy - event.y_root)
        sh.trick = None

    def on_drag(self, event):
        if not self.held:
            return
        cx, cy = event.x_root, event.y_root
        self.moved = max(self.moved,
                         math.hypot(cx - self.press[0], cy - self.press[1]))
        if self.moved < 4:  # ignore tiny jitters so plain clicks don't move him
            return
        sh = self.shark
        new_mode = "tank" if self.in_tank(cx, cy) else "free"
        if new_mode != sh.mode:
            sh.mode = new_mode
            sh.pending_bubbles.clear()
        sh.x, sh.y = self.to_local(cx + self.grab_off[0],
                                   cy + self.grab_off[1], new_mode)

    def on_release(self, event):
        if not self.held:
            return
        self.held = False
        sh = self.shark
        sh.tx = None       # pick a fresh swimming target
        sh.burst()         # click or drop = a puff of bubbles

    def on_double(self, event, mode):
        if self.hit(event, mode):
            self.held = False
            self.rename()

    # ---------- right-click menu (drawn by the app itself) ----------
    def on_right_click(self, event):
        self.open_menu(event.x_root, event.y_root, "main")

    def menu_items(self, page, x, y):
        sh = self.shark
        if page == "tricks":
            items = [("Surprise me!", lambda: sh.start_trick(force=True)),
                     None]
            for name, label in TRICK_LABELS.items():
                items.append((label,
                              lambda n=name: sh.start_trick(n, True)))
            items += [None, ("<  Back", lambda: self.open_menu(x, y, "main"))]
            return items
        return [("Rename...", self.rename),
                ("Cheer me on!", sh.say),
                None,
                ("Do a random trick", lambda: sh.start_trick(force=True)),
                ("Pick a trick  >",
                 lambda: self.open_menu(x, y, "tricks")),
                None,
                ("Edit messages...", self.edit_messages),
                None,
                ("Quit", self.close)]

    def open_menu(self, mx, my, page="main"):
        self.close_menu()
        items = self.menu_items(page, mx, my)

        pop = tk.Toplevel(self.win)
        pop.overrideredirect(True)
        pop.attributes("-topmost", True)
        frame = tk.Frame(pop, bg="#555555", padx=1, pady=1)
        frame.pack()
        inner = tk.Frame(frame, bg="white")
        inner.pack()
        for item in items:
            if item is None:
                tk.Frame(inner, height=1, bg="#cccccc").pack(fill="x", pady=3)
                continue
            label, cmd = item
            lab = tk.Label(inner, text=label, anchor="w", bg="white",
                           fg="#222222", padx=16, pady=4, width=18,
                           font=("Segoe UI", 10))
            lab.pack(fill="x")
            lab.bind("<Enter>", lambda e, w=lab: w.config(bg="#d6e8ff"))
            lab.bind("<Leave>", lambda e, w=lab: w.config(bg="white"))
            lab.bind("<Button-1>", lambda e, c=cmd: self.run_menu_item(c))
        tk.Label(inner, text=f"SharkPet v{VERSION}", anchor="w", bg="white",
                 fg="#999999", padx=16, pady=3,
                 font=("Segoe UI", 8)).pack(fill="x")

        # open it right under the cursor, kept on the screen
        pop.update_idletasks()
        x = min(mx - 6, self.sw - pop.winfo_width() - 4)
        y = min(my - 6, self.sh - pop.winfo_height() - 4)
        pop.geometry(f"+{max(0, x)}+{max(0, y)}")
        pop.lift()
        self.menu_win = pop
        self.menu_out = 0
        self.menu_job = self.win.after(150, self.check_menu)

    def check_menu(self):
        """Close the menu once the mouse has been away from it for a moment."""
        pop = self.menu_win
        if pop is None:
            return
        px, py = pop.winfo_pointerxy()
        x0, y0 = pop.winfo_rootx(), pop.winfo_rooty()
        inside = (x0 - 6 <= px < x0 + pop.winfo_width() + 6
                  and y0 - 6 <= py < y0 + pop.winfo_height() + 6)
        self.menu_out = 0 if inside else self.menu_out + 1
        if self.menu_out >= 4:
            self.close_menu()
            return
        self.menu_job = self.win.after(150, self.check_menu)

    def close_menu(self):
        if self.menu_job:
            self.win.after_cancel(self.menu_job)
            self.menu_job = None
        if self.menu_win is not None:
            self.menu_win.destroy()
            self.menu_win = None

    def run_menu_item(self, cmd):
        self.close_menu()
        self.win.after(10, cmd)

    def edit_messages(self):
        """Open a text file (one message per line) so you can write your own."""
        try:
            if not MESSAGES_FILE.exists():
                MESSAGES_FILE.write_text(
                    "# One message per line. Lines starting with # are ignored.\n"
                    "# Save the file and he'll start using your messages.\n"
                    + "\n".join(MESSAGES) + "\n", encoding="utf-8")
            os.startfile(str(MESSAGES_FILE))      # Windows
        except Exception:
            log_error(traceback.format_exc())

    # ---------- rename ----------
    def rename(self):
        dlg = tk.Toplevel(self.win)
        dlg.title("Name your shark")
        dlg.attributes("-topmost", True)
        dlg.resizable(False, False)
        tk.Label(dlg, text="What's his name?").pack(padx=20, pady=(15, 5))
        var = tk.StringVar(value=self.shark.name)
        entry = tk.Entry(dlg, textvariable=var, width=24)
        entry.pack(padx=20)

        def ok(event=None):
            new = var.get().strip()[:20]
            if new:
                self.shark.name = new
                save_name(new)
            dlg.destroy()

        entry.bind("<Return>", ok)
        dlg.bind("<Escape>", lambda e: dlg.destroy())
        tk.Button(dlg, text="OK", width=8, command=ok).pack(pady=10)

        dlg.update_idletasks()
        x = (self.sw - dlg.winfo_width()) // 2
        y = (self.sh - dlg.winfo_height()) // 2
        dlg.geometry(f"+{x}+{y}")
        entry.focus_force()
        entry.select_range(0, "end")
        dlg.grab_set()

    # ---------- main loop ----------
    def animate(self):
        try:
            self.step()
        except Exception:
            # never let one bad frame freeze the shark; note it in the log
            self.error_count += 1
            if self.error_count <= 20:
                log_error(traceback.format_exc())
        self.job = self.win.after(30, self.animate)

    def step(self):
        sh = self.shark
        if sh.mode == "tank" and self.tank is None:
            self.eject()
        tank_shown = (self.tank is not None
                      and self.tank.win.state() == "normal")

        # if the tank is just minimized, he stays inside and waits
        if sh.mode == "free":
            sh.update(self.sw, self.sh, 0,
                      SHARK_SCALE * max(1.0, self.sh / 1080), self.held)
        elif tank_shown:
            t = self.tank
            sh.update(t.w, t.h, t.sand_h, fit_scale(t.w, t.h), self.held)

        for bx, by in sh.pending_bubbles:
            if sh.mode == "free":
                self.free_bubbles.append([bx, by, random.randint(2, 5),
                                          random.uniform(0.8, 1.8)])
            else:
                self.tank.add_bubble(bx, by)
        sh.pending_bubbles.clear()

        # desktop layer
        oc = self.canvas
        oc.delete("dynamic")
        self.free_bubbles = step_bubbles(oc, self.free_bubbles)
        if sh.mode == "free":
            sh.draw(oc)

        # tank window (skipped while minimized)
        if tank_shown:
            tc = self.tank.canvas
            tc.delete("dynamic")
            self.tank.step()
            if sh.mode == "tank":
                sh.draw(tc)

    def close(self):
        self.close_menu()
        if self.job:
            self.win.after_cancel(self.job)
        self.win.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = SharkApp(root)
    root.report_callback_exception = (
        lambda exc, val, tb: log_error("".join(
            traceback.format_exception(exc, val, tb))))
    root.mainloop()
