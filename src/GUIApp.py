import math
import sys

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QGroupBox, QSizePolicy,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPainter, QPen, QBrush, QColor, QFont

from .constants import AC_MODE, AC_SPEED

# ── Color palette (dark industrial HMI) ──────────────────────────────────────
C = {
    "bg":     "#0d1117",
    "panel":  "#161b22",
    "group":  "#21262d",
    "border": "#30363d",
    "text":   "#e6edf3",
    "muted":  "#8b949e",
    "yellow": "#d4a017",
    "green":  "#3fb950",
    "red":    "#f85149",
    "blue":   "#58a6ff",
    "orange": "#f0883e",
}

_MODE_REV  = {v: k for k, v in AC_MODE.items()}
_SPEED_REV = {v: k for k, v in AC_SPEED.items()}


# ── 2D Excavator diagram ──────────────────────────────────────────────────────

class ExcavatorView(QWidget):
    BOOM_LEN   = 110
    STICK_LEN  = 85
    BUCKET_LEN = 32

    def __init__(self, parent=None):
        super().__init__(parent)
        self._joints = [45.0, -80.0, -30.0]
        self._depth  = 0.0
        self.setMinimumSize(280, 260)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_data(self, joints: list, depth: float):
        self._joints = joints[:3] if len(joints) >= 3 else [45.0, -80.0, -30.0]
        self._depth  = depth
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        p.fillRect(0, 0, w, h, QColor(C["bg"]))

        # Ground line
        gy = h - 28
        p.setPen(QPen(QColor(C["muted"]), 1, Qt.PenStyle.DashLine))
        p.drawLine(0, gy, w, gy)

        cx, cy = int(w * 0.38), gy - 28   # body pivot

        # Tracks
        p.setPen(QPen(QColor("#3a3a3a"), 1))
        p.setBrush(QBrush(QColor("#2a2a2a")))
        p.drawRoundedRect(cx - 55, gy - 14, 110, 18, 4, 4)
        p.setBrush(QBrush(QColor("#3a3a3a")))
        for rx in range(cx - 48, cx + 52, 18):
            p.drawEllipse(rx - 6, gy - 12, 12, 12)

        # Body / cab
        p.setPen(QPen(QColor("#8a6f00"), 2))
        p.setBrush(QBrush(QColor(C["yellow"])))
        p.drawRoundedRect(cx - 38, cy - 22, 76, 36, 6, 6)
        # Cab window
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor("#1a1a2e")))
        p.drawRoundedRect(cx + 2, cy - 17, 26, 20, 3, 3)

        # Arm pivot
        px, py = cx - 14, cy - 10

        # Joint angles: cumulative absolute angles from horizontal
        a0 = math.radians(self._joints[0])
        a1 = math.radians(self._joints[0] + self._joints[1])
        a2 = math.radians(self._joints[0] + self._joints[1] + self._joints[2])

        bx = px + self.BOOM_LEN  * math.cos(a0);  by = py - self.BOOM_LEN  * math.sin(a0)
        sx = bx + self.STICK_LEN * math.cos(a1);  sy = by - self.STICK_LEN * math.sin(a1)
        ex = sx + self.BUCKET_LEN* math.cos(a2);  ey = sy - self.BUCKET_LEN* math.sin(a2)

        # Boom
        pen = QPen(QColor(C["yellow"]), 10, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.drawLine(int(px), int(py), int(bx), int(by))
        # Stick
        pen.setWidth(7); pen.setColor(QColor("#b89000"))
        p.setPen(pen)
        p.drawLine(int(bx), int(by), int(sx), int(sy))
        # Bucket arm
        pen.setWidth(5); pen.setColor(QColor("#888"))
        p.setPen(pen)
        p.drawLine(int(sx), int(sy), int(ex), int(ey))
        # Bucket tip bar
        perp = a2 + math.pi / 2
        p.drawLine(int(ex + 12*math.cos(perp)), int(ey - 12*math.sin(perp)),
                   int(ex - 12*math.cos(perp)), int(ey + 12*math.sin(perp)))

        # Joint dots
        p.setPen(QPen(QColor("#444"), 1))
        p.setBrush(QBrush(QColor("#666")))
        for jx, jy in [(px, py), (bx, by), (sx, sy)]:
            p.drawEllipse(int(jx) - 5, int(jy) - 5, 10, 10)

        # Depth line + label
        if ey < gy:
            p.setPen(QPen(QColor(C["blue"]), 1, Qt.PenStyle.DotLine))
            p.drawLine(int(ex), int(ey), int(ex), gy)
            p.setPen(QColor(C["blue"]))
            p.setFont(QFont("Monospace", 8))
            p.drawText(int(ex) + 4, int((ey + gy) // 2), f"{self._depth:.2f} m")

        # Label
        p.setPen(QColor(C["muted"]))
        p.setFont(QFont("Monospace", 8))
        p.drawText(8, 14, "EXCAVATOR")


# ── Monitor panel (diagram + numeric readout) ─────────────────────────────────

class MonitorPanel(QGroupBox):
    def __init__(self, parent=None):
        super().__init__("모니터링", parent)
        layout = QVBoxLayout()
        layout.setSpacing(6)

        self._view = ExcavatorView()
        layout.addWidget(self._view)

        grid = QGridLayout()
        grid.setSpacing(4)
        self._lbl = {}
        for row, (key, label) in enumerate([
            ("j0", "붐  (J1)"),
            ("j1", "스틱 (J2)"),
            ("j2", "버킷 (J3)"),
            ("depth", "깊이"),
        ]):
            ql = QLabel(label)
            ql.setStyleSheet(f"color:{C['muted']};font-size:11px;")
            qv = QLabel("---")
            qv.setStyleSheet(f"color:{C['yellow']};font-size:12px;font-weight:bold;")
            qv.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            grid.addWidget(ql, row, 0)
            grid.addWidget(qv, row, 1)
            self._lbl[key] = qv

        layout.addLayout(grid)
        self.setLayout(layout)

    def update_data(self, joints: list, depth: float):
        self._view.set_data(joints, depth)
        j = joints if len(joints) >= 3 else [0.0, 0.0, 0.0]
        self._lbl["j0"].setText(f"{j[0]:.1f}°")
        self._lbl["j1"].setText(f"{j[1]:.1f}°")
        self._lbl["j2"].setText(f"{j[2]:.1f}°")
        self._lbl["depth"].setText(f"{depth:.2f} m")


# ── STT + LLM status panel ────────────────────────────────────────────────────

class STTPanel(QGroupBox):
    _ANIM = ["●○○", "○●○", "○○●"]

    def __init__(self, shm, parent=None):
        super().__init__("음성 입력 / LLM 상태", parent)
        self._shm  = shm
        self._tick = 0

        layout = QVBoxLayout()
        layout.setSpacing(8)

        # STT text display
        self._stt_lbl = QLabel("대기 중...")
        self._stt_lbl.setWordWrap(True)
        self._stt_lbl.setMinimumHeight(52)
        self._stt_lbl.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self._stt_lbl.setStyleSheet(f"""
            QLabel {{
                background-color: {C['panel']};
                color: {C['text']};
                border: 1px solid {C['border']};
                border-radius: 6px;
                padding: 8px;
                font-size: 13px;
            }}
        """)
        layout.addWidget(self._stt_lbl)

        # STT trigger button
        self._stt_btn = QPushButton("🎤  음성 입력")
        self._stt_btn.setFixedHeight(44)
        self._stt_btn.setStyleSheet(self._idle_style())
        self._stt_btn.clicked.connect(self._on_trigger)
        layout.addWidget(self._stt_btn)

        # LLM processing label
        self._llm_lbl = QLabel("")
        self._llm_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._llm_lbl.setFixedHeight(22)
        self._llm_lbl.setStyleSheet(f"color:{C['orange']};font-size:12px;font-weight:bold;")
        layout.addWidget(self._llm_lbl)

        self.setLayout(layout)

        self._anim_timer = QTimer()
        self._anim_timer.setInterval(400)
        self._anim_timer.timeout.connect(self._refresh)
        self._anim_timer.start()

    # ── styles ────────────────────────────────────────────────────────────────

    def _idle_style(self):
        return (f"QPushButton{{background:#1a3a2a;color:{C['green']};"
                f"border:2px solid {C['green']};border-radius:8px;"
                f"font-size:14px;font-weight:bold;}}"
                f"QPushButton:hover{{background:#264d38;}}")

    def _rec_style(self):
        return (f"QPushButton{{background:#4a1a1a;color:{C['red']};"
                f"border:2px solid {C['red']};border-radius:8px;"
                f"font-size:14px;font-weight:bold;}}")

    # ── slots ─────────────────────────────────────────────────────────────────

    def _on_trigger(self):
        if not self._shm.stt_active:
            self._shm.stt_trigger.set()

    def _refresh(self):
        # STT input display
        text = self._shm.llm_input
        if text:
            self._stt_lbl.setText(text)

        # Recording state
        if self._shm.stt_active:
            self._stt_btn.setText("⏹  녹음 중...")
            self._stt_btn.setStyleSheet(self._rec_style())
        else:
            self._stt_btn.setText("🎤  음성 입력")
            self._stt_btn.setStyleSheet(self._idle_style())

        # LLM processing animation
        if self._shm.llm_processing:
            self._tick += 1
            dots = self._ANIM[self._tick % 3]
            self._llm_lbl.setText(f"{dots}  LLM 처리 중...")
        else:
            self._tick = 0
            self._llm_lbl.setText("")


# ── Headlight panel ───────────────────────────────────────────────────────────

class HeadlightPanel(QGroupBox):
    def __init__(self, shm, parent=None):
        super().__init__("헤드라이트", parent)
        self._shm = shm

        layout = QHBoxLayout()
        layout.setSpacing(8)

        self._dot = QLabel("●")
        self._dot.setStyleSheet(f"color:{C['muted']};font-size:20px;")
        self._lbl = QLabel("OFF")
        self._lbl.setStyleSheet(f"color:{C['muted']};font-size:13px;font-weight:bold;min-width:32px;")

        self._off_btn = QPushButton("OFF")
        self._on_btn  = QPushButton("ON")
        for btn in (self._off_btn, self._on_btn):
            btn.setFixedSize(72, 36)

        self._off_btn.clicked.connect(lambda: self._set("off"))
        self._on_btn.clicked.connect(lambda: self._set("on"))

        layout.addWidget(self._dot)
        layout.addWidget(self._lbl)
        layout.addStretch()
        layout.addWidget(self._off_btn)
        layout.addWidget(self._on_btn)
        self.setLayout(layout)
        self._refresh()

    def _set(self, state: str):
        self._shm.set_headlight(state)
        self._refresh()

    def _refresh(self):
        on = self._shm.get_headlight() == 1
        color = C["yellow"] if on else C["muted"]
        self._dot.setStyleSheet(f"color:{color};font-size:20px;")
        self._lbl.setText("ON" if on else "OFF")
        self._lbl.setStyleSheet(f"color:{color};font-size:13px;font-weight:bold;min-width:32px;")

        self._off_btn.setStyleSheet(
            f"background:#3a1a1a;color:{C['red']};border:1px solid {C['red']};border-radius:6px;"
            if not on else "")
        self._on_btn.setStyleSheet(
            f"background:#3a2e00;color:{C['yellow']};border:1px solid {C['yellow']};border-radius:6px;"
            if on else "")


# ── AC control panel ──────────────────────────────────────────────────────────

class ACPanel(QGroupBox):
    _MODE_LABELS  = ["자동", "냉방", "난방", "송풍", "제습"]
    _MODE_KEYS    = ["auto", "cool", "heat", "fan", "dry"]
    _SPEED_LABELS = ["자동", "약", "중", "강"]
    _SPEED_KEYS   = ["auto", "low", "medium", "high"]

    def __init__(self, shm, parent=None):
        super().__init__("에어컨 제어", parent)
        self._shm = shm
        self._mode_btns  = []
        self._speed_btns = []

        layout = QGridLayout()
        layout.setSpacing(8)

        # ── Row 0: Power + Temperature ────────────────────────────────────────
        self._pwr_dot = QLabel("●")
        self._pwr_dot.setStyleSheet(f"color:{C['muted']};font-size:20px;")
        self._pwr_lbl = QLabel("OFF")
        self._pwr_lbl.setStyleSheet(f"color:{C['muted']};font-size:13px;font-weight:bold;")

        self._off_btn = QPushButton("POWER OFF")
        self._on_btn  = QPushButton("POWER ON")
        for btn in (self._off_btn, self._on_btn):
            btn.setFixedHeight(36)

        self._temp_minus   = QPushButton("−")
        self._temp_plus    = QPushButton("+")
        self._temp_display = QLabel("24°C")
        self._temp_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._temp_display.setStyleSheet(
            f"color:{C['yellow']};font-size:22px;font-weight:bold;min-width:70px;")

        for btn in (self._temp_minus, self._temp_plus):
            btn.setFixedSize(36, 36)

        self._off_btn.clicked.connect(lambda: self._set_power(False))
        self._on_btn.clicked.connect(lambda: self._set_power(True))
        self._temp_minus.clicked.connect(lambda: self._change_temp(-1))
        self._temp_plus.clicked.connect(lambda: self._change_temp(+1))

        row0 = QHBoxLayout()
        row0.setSpacing(8)
        row0.addWidget(self._pwr_dot)
        row0.addWidget(self._pwr_lbl)
        row0.addStretch()
        row0.addWidget(self._off_btn)
        row0.addWidget(self._on_btn)
        row0.addSpacing(20)
        row0.addWidget(self._temp_minus)
        row0.addWidget(self._temp_display)
        row0.addWidget(self._temp_plus)
        layout.addLayout(row0, 0, 0, 1, -1)

        # ── Row 1: Mode ───────────────────────────────────────────────────────
        layout.addWidget(self._muted_lbl("모드:"), 1, 0)
        for col, (label, key) in enumerate(zip(self._MODE_LABELS, self._MODE_KEYS), start=1):
            btn = self._toggle_btn(label, lambda _, k=key: self._set_mode(k))
            self._mode_btns.append(btn)
            layout.addWidget(btn, 1, col)

        # ── Row 2: Fan speed + Swing ──────────────────────────────────────────
        layout.addWidget(self._muted_lbl("풍속:"), 2, 0)
        for col, (label, key) in enumerate(zip(self._SPEED_LABELS, self._SPEED_KEYS), start=1):
            btn = self._toggle_btn(label, lambda _, k=key: self._set_speed(k))
            self._speed_btns.append(btn)
            layout.addWidget(btn, 2, col)

        layout.addWidget(self._muted_lbl("스윙:"), 2, 5)
        self._swing_off = self._toggle_btn("OFF", lambda: self._set_swing("off"))
        self._swing_on  = self._toggle_btn("ON",  lambda: self._set_swing("on"))
        layout.addWidget(self._swing_off, 2, 6)
        layout.addWidget(self._swing_on,  2, 7)

        self.setLayout(layout)
        self._refresh()

    # ── helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _muted_lbl(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color:{C['muted']};font-size:11px;")
        return lbl

    @staticmethod
    def _toggle_btn(label: str, slot) -> QPushButton:
        btn = QPushButton(label)
        btn.setFixedHeight(32)
        btn.clicked.connect(slot)
        return btn

    # ── AC commands (write directly to SharedMemory) ──────────────────────────

    def _set_power(self, on: bool):
        self._shm.set_ac_power("on" if on else "off")
        self._refresh()

    def _change_temp(self, delta: int):
        ac = self._shm.get_ac_state()
        try:
            self._shm.set_ac_temperature(ac["temp"] + delta)
        except ValueError:
            pass
        self._refresh()

    def _set_mode(self, key: str):
        self._shm.set_ac_mode(key)
        self._refresh()

    def _set_speed(self, key: str):
        self._shm.set_ac_fan_speed(key)
        self._refresh()

    def _set_swing(self, state: str):
        self._shm.set_ac_swing(state)
        self._refresh()

    # ── refresh UI to match SharedMemory ─────────────────────────────────────

    def _refresh(self):
        ac = self._shm.get_ac_state()
        on = ac["power"] == 1

        color = C["blue"] if on else C["muted"]
        self._pwr_dot.setStyleSheet(f"color:{color};font-size:20px;")
        self._pwr_lbl.setText("ON" if on else "OFF")
        self._pwr_lbl.setStyleSheet(f"color:{color};font-size:13px;font-weight:bold;")

        self._off_btn.setStyleSheet(
            f"background:#3a1a1a;color:{C['red']};border:1px solid {C['red']};border-radius:6px;"
            if not on else "")
        self._on_btn.setStyleSheet(
            f"background:#1a2a4a;color:{C['blue']};border:1px solid {C['blue']};border-radius:6px;"
            if on else "")

        self._temp_display.setText(f"{ac['temp']}°C")

        cur_mode  = _MODE_REV.get(ac["mode"], "auto")
        cur_speed = _SPEED_REV.get(ac["speed"], "auto")

        for btn, key in zip(self._mode_btns, self._MODE_KEYS):
            btn.setStyleSheet(
                f"background:#1a2a3a;color:{C['blue']};border:1px solid {C['blue']};border-radius:6px;"
                if key == cur_mode else "")

        for btn, key in zip(self._speed_btns, self._SPEED_KEYS):
            btn.setStyleSheet(
                f"background:#1a2a3a;color:{C['blue']};border:1px solid {C['blue']};border-radius:6px;"
                if key == cur_speed else "")

        swing_on = ac["swing"] == 1
        self._swing_off.setStyleSheet(
            f"background:#3a1a1a;color:{C['red']};border:1px solid {C['red']};border-radius:6px;"
            if not swing_on else "")
        self._swing_on.setStyleSheet(
            f"background:#1a2a4a;color:{C['blue']};border:1px solid {C['blue']};border-radius:6px;"
            if swing_on else "")


# ── Main window ───────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    _GLOBAL_STYLE = f"""
        QMainWindow, QWidget {{
            background-color: {C['bg']};
            color: {C['text']};
            font-family: 'Segoe UI', 'Noto Sans KR', sans-serif;
            font-size: 12px;
        }}
        QGroupBox {{
            background-color: {C['group']};
            border: 1px solid {C['border']};
            border-radius: 8px;
            margin-top: 12px;
            padding: 8px;
            font-size: 11px;
            font-weight: bold;
            color: {C['muted']};
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            subcontrol-position: top left;
            padding: 0 8px;
            left: 12px;
        }}
        QPushButton {{
            background-color: {C['panel']};
            color: {C['text']};
            border: 1px solid {C['border']};
            border-radius: 6px;
            padding: 4px 12px;
            font-size: 12px;
        }}
        QPushButton:hover {{
            background-color: #30363d;
            border-color: {C['blue']};
        }}
        QPushButton:pressed {{
            background-color: #3c444d;
        }}
    """

    def __init__(self, shm):
        super().__init__()
        self._shm = shm
        self.setWindowTitle("VOLVO HMI")
        self.setMinimumSize(920, 680)
        self.setStyleSheet(self._GLOBAL_STYLE)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setSpacing(10)
        root.setContentsMargins(12, 12, 12, 12)

        # Header bar
        hdr = QLabel("■  VOLVO HMI  —  굴착기 제어 시스템")
        hdr.setStyleSheet(
            f"color:{C['yellow']};font-size:15px;font-weight:bold;"
            f"padding:8px 12px;background:{C['panel']};border-radius:6px;")
        root.addWidget(hdr)

        # Top section
        top = QHBoxLayout()
        top.setSpacing(10)

        self._monitor = MonitorPanel()
        self._monitor.setMaximumWidth(330)
        top.addWidget(self._monitor)

        right = QVBoxLayout()
        right.setSpacing(10)
        self._stt_panel = STTPanel(shm)
        right.addWidget(self._stt_panel)
        self._hl_panel = HeadlightPanel(shm)
        right.addWidget(self._hl_panel)
        right.addStretch()
        top.addLayout(right)

        root.addLayout(top)

        # Bottom: AC control
        self._ac_panel = ACPanel(shm)
        root.addWidget(self._ac_panel)

        # 100 ms poll timer for monitor + headlight + AC sync
        self._timer = QTimer()
        self._timer.setInterval(100)
        self._timer.timeout.connect(self._poll)
        self._timer.start()

    def _poll(self):
        status = self._shm.get_all()
        self._monitor.update_data(
            status.get("joints", [0.0, 0.0, 0.0]),
            status.get("depth", 0.0),
        )
        self._hl_panel._refresh()
        self._ac_panel._refresh()

    def closeEvent(self, event):
        self._shm.is_running = False
        super().closeEvent(event)


# ── Entry point ───────────────────────────────────────────────────────────────

def launch_gui(shm) -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    win = MainWindow(shm)
    win.show()
    return app.exec()
