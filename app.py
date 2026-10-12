"""KanaShift v0.5 — first-run setup for 1–6 installed input modes."""
from __future__ import annotations

import json
import logging
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path

# Qt warning does not indicate a failed IME switch; leave other Qt errors visible.
os.environ.setdefault("QT_LOGGING_RULES", "qt.gui.icc.warning=false")

from PySide6.QtCore import QObject, Qt, QSettings, QTimer, Signal
from PySide6.QtGui import QColor, QCursor, QFont, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication, QComboBox, QDialog, QFrame, QGridLayout, QHBoxLayout,
    QLabel, QLineEdit, QMenu, QMessageBox, QPushButton, QScrollArea, QSystemTrayIcon,
    QVBoxLayout, QWidget, QGraphicsDropShadowEffect,
)

from hotkeys_windows import CapsQHook
from ime_windows import (
    IMEError, current_hkl, current_language, cycle_windows_language,
    foreground_target, get_target_window, japanese_fallback_key,
    japanese_matches, japanese_set, korean_is_hangul, korean_set,
    korean_toggle_key, request_hkl,
)
from layout_profiles import (
    LayoutInfo, available_layouts, default_name, hkl_number, hkl_string,
    initial_slots, installed_slots, mode_options, sanitized_slots,
    first_run_slots, needs_first_run_setup,
)

APP = "KanaShift"
MAX_SLOTS = 6
COLORS = ["#C9BBFF", "#9FDBF7", "#FFC3DD", "#FFE0A9", "#C0E7CE", "#F3C6FF"]

THEME = """
QWidget { color: #F5F2FF; font-family: 'Segoe UI', 'Yu Gothic UI', 'Microsoft YaHei UI', 'Malgun Gothic'; font-size: 13px; }
QFrame#hud { background: #191B2B; border: 1px solid #3F405B; border-radius: 25px; }
QLabel#eyebrow { color:#BCB5EE; font-size:11px; font-weight:650; }
QLabel#hero { color:#F8F6FF; font-size:27px; font-weight:700; }
QLabel#subtitle { color:#9FA4C1; font-size:12px; }
QFrame#choice { background:#24283C; border:1px solid #41465F; border-radius:18px; }
QFrame#choice:hover { background:#30344C; }
QFrame#choice[selected='true'] { background:#353451; border:2px solid #AE9EFF; }
QFrame#choice[missing='true'] { background:#1D2131; border:1px solid #454052; }
QLabel#glyph { font-size:32px; font-weight:650; background:transparent; }
QLabel#choiceTitle { font-size:17px; font-weight:650; background:transparent; }
QLabel#choiceSub { color:#9BA4BD; font-size:11px; background:transparent; }
QLabel#number { color:#A6A8C8; font-size:12px; background:transparent; }
QLabel#footer { color:#989AB9; font-size:11px; }
QLabel#keycap { color:#CDCEEC; background:#2B2F47; border-radius:7px; padding:7px; font-size:11px; }
QDialog#prefs { background:#171A28; }
QLabel#sectionTitle { font-size:21px; font-weight:700; }
QLabel#hint { color:#A4AAC6; font-size:12px; }
QFrame#slotRow { background:#23273A; border-radius:14px; }
QLineEdit, QComboBox { background:#30364C; border:1px solid #50546A; border-radius:9px; padding:8px; min-height:24px; selection-background-color:#7B6FD9; }
QLineEdit:focus, QComboBox:focus { border:1px solid #B5A7FF; }
QComboBox QAbstractItemView { background:#22273A; color:#F9F7FF; selection-background-color:#60558E; }
QPushButton { background:#363B54; border:1px solid #4B536C; border-radius:10px; padding:10px 14px; color:#F1EFFF; }
QPushButton:hover { background:#49516C; }
QPushButton:disabled { color:#72758C; background:#292B3B; border-color:#383B4D; }
QPushButton#primary { background:#8275E5; color:white; font-weight:700; border:0; }
QPushButton#primary:hover { background:#9D92F4; }
QPushButton#mini { padding:7px 10px; min-width:24px; }
QScrollArea { border:0; background:transparent; }
QScrollArea > QWidget > QWidget { background:transparent; }
"""


def make_icon(size: int = 64) -> QIcon:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    p = QPainter(pixmap)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QColor("#9D8FFB"))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawRoundedRect(2, 2, size - 4, size - 4, 16, 16)
    p.setPen(QPen(QColor("#FFFFFF"), 4, Qt.PenStyle.SolidLine,
                  Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    p.drawLine(int(size*.34), int(size*.27), int(size*.34), int(size*.74))
    p.drawLine(int(size*.34), int(size*.52), int(size*.67), int(size*.28))
    p.drawLine(int(size*.34), int(size*.52), int(size*.67), int(size*.74))
    p.end()
    return QIcon(pixmap)


class StartupSplash(QWidget):
    """Lightweight startup screen shown while the tray and keyboard hook load."""

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint |
                            Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedSize(370, 168)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        panel = QFrame()
        panel.setObjectName("startup")
        panel.setStyleSheet("""
            QFrame#startup { background:#1D2032; border:1px solid #68628A;
                             border-radius:24px; }
            QLabel#loadingTitle { color:#F6F1FF; font-size:20px; font-weight:700; }
            QLabel#loadingText { color:#BEB4E9; font-size:13px; }
        """)
        content = QVBoxLayout(panel)
        content.setContentsMargins(28, 25, 28, 25)
        content.setSpacing(10)
        heading = QLabel("KanaShift")
        heading.setObjectName("loadingTitle")
        content.addWidget(heading)
        self.status = QLabel("Loading....")
        self.status.setObjectName("loadingText")
        content.addWidget(self.status)
        outer.addWidget(panel)
        self._step = 0
        self._animation = QTimer(self)
        self._animation.timeout.connect(self._tick)
        self._animation.start(220)

    def _tick(self):
        self._step = (self._step + 1) % 4
        self.status.setText("Loading" + "." * (1 + self._step))

    def showEvent(self, event):
        super().showEvent(event)
        screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        if screen:
            area = screen.availableGeometry()
            self.move(area.center().x() - self.width()//2,
                      area.center().y() - self.height()//2)

    def finish(self):
        self._animation.stop()
        self.close()


class Dispatcher(QObject):
    hotkey = Signal(int)


@dataclass(frozen=True)
class TileData:
    slot: dict[str, str]
    glyph: str
    title: str
    subtitle: str
    color: str
    missing: bool = False


class ModeTile(QFrame):
    activated = Signal(object)

    def __init__(self, data: TileData, number: int):
        super().__init__()
        self.data = data
        self.setObjectName("choice")
        self.setProperty("selected", False)
        self.setProperty("missing", data.missing)
        self.setMinimumHeight(120)
        self.setCursor(Qt.CursorShape.PointingHandCursor if not data.missing else Qt.CursorShape.ArrowCursor)
        main = QHBoxLayout(self)
        main.setContentsMargins(20, 13, 17, 13)
        main.setSpacing(15)
        glyph = QLabel(data.glyph)
        glyph.setObjectName("glyph")
        glyph.setStyleSheet(f"color:{data.color};background:transparent;")
        glyph.setFixedWidth(46)
        main.addWidget(glyph)
        content = QVBoxLayout()
        content.setSpacing(5)
        name = QLabel(data.title)
        name.setObjectName("choiceTitle")
        sub = QLabel(data.subtitle if not data.missing else "입력기 없음 · 설정에서 변경")
        sub.setObjectName("choiceSub")
        content.addWidget(name)
        content.addWidget(sub)
        main.addLayout(content, 1)
        num = QLabel(str(number))
        num.setObjectName("number")
        main.addWidget(num, 0, Qt.AlignmentFlag.AlignTop)

    def set_active(self, value: bool) -> None:
        self.setProperty("selected", value)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and not self.data.missing:
            self.activated.emit(self.data.slot)
        super().mousePressEvent(e)


class SettingsDialog(QDialog):
    changed = Signal(object)

    def __init__(self, slots: list[dict[str, str]], parent=None, *, first_run: bool = False):
        super().__init__(parent)
        self.first_run = first_run
        self.setObjectName("prefs")
        self.setStyleSheet(THEME)
        self.setWindowTitle("KanaShift · 첫 설정" if first_run else "KanaShift 설정")
        self.setWindowIcon(make_icon())
        self.setMinimumSize(850, 520)
        self.resize(960, 635)
        self.slots = [dict(x) for x in slots]
        self.layouts: list[LayoutInfo] = []
        self.refresh_layouts(rebuild=False)

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 23)
        root.setSpacing(13)
        head = QHBoxLayout()
        heading = QVBoxLayout()
        h = QLabel("사용할 입력기를 선택하세요" if first_run else "입력기 슬롯 설정")
        h.setObjectName("sectionTitle")
        heading.addWidget(h)
        self.installed_info = QLabel("")
        self.installed_info.setObjectName("hint")
        heading.addWidget(self.installed_info)
        if first_run:
            description = QLabel("최대 6개까지 추가할 수 있습니다.")
            description.setObjectName("hint")
            heading.addWidget(description)
        self._update_installed_info()
        head.addLayout(heading)
        head.addStretch(1)
        refresh = QPushButton("↻  입력기 다시 검색")
        refresh.clicked.connect(self.refresh_layouts)
        head.addWidget(refresh)
        root.addLayout(head)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        self.list_v = QVBoxLayout(container)
        self.list_v.setSpacing(10)
        self.list_v.setContentsMargins(2, 4, 5, 4)
        self.list_v.addStretch(1)
        scroll.setWidget(container)
        root.addWidget(scroll, 1)

        foot = QHBoxLayout()
        self.add_button = QPushButton("+  입력기 추가" if first_run else "+  슬롯 추가")
        self.add_button.clicked.connect(self.add_slot)
        foot.addWidget(self.add_button)
        foot.addStretch()
        tip = QLabel("Developed by Lutté Laurent")
        tip.setObjectName("hint")
        tip.setWordWrap(True)
        foot.addWidget(tip, 1)
        if first_run:
            cancel = QPushButton("종료")
            cancel.clicked.connect(self.reject)
            foot.addWidget(cancel)
        close = QPushButton("설정 완료 · 시작하기" if first_run else "저장하고 닫기")
        close.setObjectName("primary")
        close.clicked.connect(self.accept)
        foot.addWidget(close)
        root.addLayout(foot)
        self._rebuild()

    def refresh_layouts(self, rebuild: bool = True):
        self.layouts = available_layouts()
        # Installed input methods only. Slots from removed layouts never appear.
        if self.first_run:
            matches = {x.hkl for x in self.layouts}
            self.slots = [s for s in sanitized_slots(self.slots) if s["hkl"] in matches]
            if not self.slots:
                self.slots = first_run_slots(self.layouts)
        else:
            self.slots = installed_slots(self.slots, self.layouts)
        if rebuild:
            self._update_installed_info()
            self._rebuild()

    def _update_installed_info(self):
        count = len(self.layouts)
        self.installed_info.setText(
            f"Windows에서 사용 가능한 입력기 {count}개 · 슬롯 최대 6개"
        )

    def _layout_for(self, hkl: str) -> LayoutInfo | None:
        return next((x for x in self.layouts if x.hkl == hkl), None)

    def _rebuild(self):
        while self.list_v.count():
            item = self.list_v.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for i, slot in enumerate(self.slots):
            self.list_v.addWidget(self._build_row(i, slot))
        self.list_v.addStretch(1)
        self.add_button.setEnabled(len(self.slots) < MAX_SLOTS)

    def _build_row(self, i: int, slot: dict[str, str]) -> QWidget:
        outer = QFrame()
        outer.setObjectName("slotRow")
        row = QHBoxLayout(outer)
        row.setContentsMargins(13, 12, 13, 12)
        row.setSpacing(10)
        no = QLabel(f"{i+1:02d}")
        no.setFixedWidth(25)
        no.setStyleSheet("font-weight:700;color:#CDBEFF")
        row.addWidget(no)
        layout = QComboBox()
        layout.setMinimumWidth(240)
        layout.setToolTip("Windows에서 사용 가능한 입력기")
        for x in self.layouts:
            layout.addItem(x.display, x.hkl)
        layout.setCurrentIndex(max(0, layout.findData(slot["hkl"])))
        layout.currentIndexChanged.connect(lambda _, idx=i, cb=layout: self._set_layout(idx, cb.currentData()))
        row.addWidget(layout, 4)
        mode = QComboBox()
        mode.setMinimumWidth(155)
        mode.setToolTip("해당 입력기에서 전환할 입력 모드")
        family = self._layout_for(slot["hkl"])
        for mode_key, text in mode_options(family.family if family else "standard"):
            mode.addItem(text, mode_key)
        ix = mode.findData(slot["mode"])
        if ix < 0:
            mode.addItem("이전 모드 (현재 입력기와 불일치)", slot["mode"])
            ix = mode.count()-1
        mode.setCurrentIndex(ix)
        mode.currentIndexChanged.connect(lambda _, idx=i, cb=mode: self._set_mode(idx, cb.currentData()))
        row.addWidget(mode, 3)
        name = QLineEdit(slot.get("name", ""))
        name.setMaxLength(32)
        name.setPlaceholderText("표시 이름")
        name.setToolTip("HUD에 표시되는 사용자 지정 이름")
        name.editingFinished.connect(lambda idx=i, ed=name: self._set_name(idx, ed.text()))
        row.addWidget(name, 3)
        up = QPushButton("↑")
        up.setObjectName("mini")
        up.setEnabled(i > 0)
        up.clicked.connect(lambda _, idx=i: self._move(idx, -1))
        row.addWidget(up)
        down = QPushButton("↓")
        down.setObjectName("mini")
        down.setEnabled(i < len(self.slots)-1)
        down.clicked.connect(lambda _, idx=i: self._move(idx, 1))
        row.addWidget(down)
        remove = QPushButton("×")
        remove.setObjectName("mini")
        remove.setToolTip("슬롯 삭제")
        remove.setEnabled(len(self.slots) > 1)
        remove.clicked.connect(lambda _, idx=i: self._remove(idx))
        row.addWidget(remove)
        return outer

    def _set_layout(self, i: int, hkl: str) -> None:
        if not hkl:
            return
        layout = self._layout_for(hkl)
        if not layout:
            return
        mode = mode_options(layout.family)[0][0]
        self.slots[i] = {"hkl":hkl, "mode":mode, "name":default_name(layout, mode)}
        self._rebuild()

    def _set_mode(self, i: int, mode: str) -> None:
        if mode is None:
            return
        slot = self.slots[i]
        layout = self._layout_for(slot["hkl"])
        previous_default = default_name(layout, slot["mode"]) if layout else ""
        if layout and (not slot.get("name") or slot["name"] == previous_default):
            slot["name"] = default_name(layout, mode)
        slot["mode"] = mode
        self._rebuild()

    def _set_name(self, i: int, name: str) -> None:
        self.slots[i]["name"] = name.strip()[:32]

    def _move(self, i: int, offset: int) -> None:
        j = i + offset
        self.slots[i], self.slots[j] = self.slots[j], self.slots[i]
        self._rebuild()

    def _remove(self, i: int) -> None:
        if len(self.slots) > 1:
            self.slots.pop(i)
            self._rebuild()

    def add_slot(self):
        if len(self.slots) >= MAX_SLOTS:
            return
        used = {x["hkl"] for x in self.slots}
        candidate = next((x for x in self.layouts if x.hkl not in used), None)
        candidate = candidate or (self.layouts[0] if self.layouts else None)
        if candidate:
            self.slots.append({"hkl":candidate.hkl, "mode":"default", "name":candidate.name})
            self._rebuild()

    def _notify(self):
        self.changed.emit([dict(x) for x in self.slots])

    def accept(self):
        if not self.slots:
            QMessageBox.warning(self, "입력기를 선택하세요", "입력기를 하나 이상 등록해 주세요.")
            return
        self._notify()
        super().accept()


class Overlay(QDialog):
    picked = Signal(object)
    settings_requested = Signal()

    def __init__(self, slots: list[dict[str, str]]):
        super().__init__()
        self.slots = [dict(x) for x in slots]
        self.tiles: list[ModeTile] = []
        self.index = 0
        self.columns = 3
        self.page = "main"
        self.ask_slot: dict[str,str] | None = None
        self.target_hwnd = 0
        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint |
                            Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.NoDropShadowWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setStyleSheet(THEME)
        self.panel = QFrame(self)
        self.panel.setObjectName("hud")
        self.panel.setFixedSize(790, 435)
        shadow = QGraphicsDropShadowEffect(self.panel)
        shadow.setBlurRadius(70)
        shadow.setOffset(0, 18)
        shadow.setColor(QColor(0, 0, 0, 150))
        self.panel.setGraphicsEffect(shadow)
        body = QVBoxLayout(self.panel)
        body.setContentsMargins(32, 27, 32, 24)
        body.setSpacing(16)
        head = QHBoxLayout()
        label_box = QVBoxLayout()
        label_box.setSpacing(5)
        brand = QLabel("KANASHIFT   /   INPUT HUD")
        brand.setObjectName("eyebrow")
        label_box.addWidget(brand)
        self.heading = QLabel("입력 언어 선택")
        self.heading.setObjectName("hero")
        label_box.addWidget(self.heading)
        head.addLayout(label_box)
        head.addStretch(1)
        config = QPushButton("⚙  설정")
        config.clicked.connect(self._open_settings)
        head.addWidget(config)
        body.addLayout(head)
        self.hint = QLabel("1-6번 또는 방향키로 선택")
        self.hint.setObjectName("subtitle")
        body.addWidget(self.hint)
        self.grid = QGridLayout()
        self.grid.setSpacing(13)
        body.addLayout(self.grid, 1)
        foot = QHBoxLayout()
        info = QLabel("Enter 선택   ·   Esc 닫기")
        info.setObjectName("footer")
        foot.addWidget(info)
        foot.addStretch(1)
        hotkey = QLabel("CapsLock + Q")
        hotkey.setObjectName("keycap")
        foot.addWidget(hotkey)
        body.addLayout(foot)
        self._main()

    def _open_settings(self):
        self.hide()
        self.settings_requested.emit()

    def set_slots(self, slots):
        self.slots = [dict(x) for x in slots]
        if not self.isVisible():
            self._main()

    def _center(self):
        self.panel.move((self.width()-self.panel.width())//2,
                        (self.height()-self.panel.height())//2)

    def resizeEvent(self, event):
        self._center()
        super().resizeEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(8, 10, 18, 133))
        painter.end()
        super().paintEvent(event)

    def open_hud(self, target: int):
        self.target_hwnd = target
        screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        if not screen:
            return
        self.setGeometry(screen.geometry())
        self._main()
        self._center()
        self.show()
        self.raise_()
        self.activateWindow()
        self.setFocus()

    def _render(self, data: list[TileData]):
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.tiles = []
        self.columns = 3 if len(data) > 4 else (1 if len(data) == 1 else 2)
        dimensions = ((640, 405) if len(data) == 1 else
                      (790, 420) if len(data) == 2 else
                      (790, 550) if len(data) <= 4 else (990, 555))
        self.panel.setFixedSize(*dimensions)
        self._center()
        for i, item in enumerate(data):
            tile = ModeTile(item, i+1)
            tile.activated.connect(self._select_slot)
            self.tiles.append(tile)
            self.grid.addWidget(tile, i // self.columns, i % self.columns)
        self._highlight(0)

    def _main(self):
        self.page = "main"
        self.ask_slot = None
        self.heading.setText("입력 언어 선택")
        self.hint.setText("숫자키 · 방향키 · 마우스로 선택")
        installed = {layout.hkl: layout for layout in available_layouts()}
        display = []
        for i, slot in enumerate(self.slots):
            layout = installed.get(slot["hkl"])
            name = slot.get("name") or (default_name(layout, slot["mode"]) if layout else "사용할 수 없음")
            mode_text = next((text for key, text in mode_options(layout.family if layout else "standard")
                              if key == slot["mode"]), "입력기 변경")
            sub = f"{layout.tag}  ·  {mode_text}" if layout else ""
            display.append(TileData(slot, layout.symbol if layout else "!", name, sub,
                                    COLORS[i%len(COLORS)], layout is None))
        self._render(display)

    def _width_select(self, slot: dict[str, str]):
        self.page = "ask"
        self.ask_slot = slot
        self.heading.setText("가타카나 문자 폭")
        self.hint.setText("전각 또는 반각을 선택하세요")
        self._render([
            TileData({**slot, "mode":"ja_katakana_full"}, "カ", "전각", "アイウエオ", COLORS[2]),
            TileData({**slot, "mode":"ja_katakana_half"}, "ｶ", "반각", "ｱｲｳｴｵ", COLORS[3]),
        ])

    def _highlight(self, index: int):
        if not self.tiles:
            return
        index %= len(self.tiles)
        if self.tiles[index].data.missing:
            valid = next((i for i, card in enumerate(self.tiles) if not card.data.missing), None)
            if valid is None:
                return
            index = valid
        self.index = index
        for i, tile in enumerate(self.tiles):
            tile.set_active(i == index)

    def _select_slot(self, slot: dict[str,str]):
        if self.page == "main" and slot["mode"] == "ja_katakana_ask":
            self._width_select(slot)
        else:
            self.hide()
            self.picked.emit(dict(slot))

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key.Key_Escape:
            if self.page == "ask":
                self._main()
            else:
                self.hide()
            return
        if not self.tiles:
            return
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            tile = self.tiles[self.index]
            if not tile.data.missing:
                self._select_slot(tile.data.slot)
            return
        if Qt.Key.Key_1 <= key <= Qt.Key.Key_6:
            index = int(key) - int(Qt.Key.Key_1)
            if index < len(self.tiles) and not self.tiles[index].data.missing:
                self._select_slot(self.tiles[index].data.slot)
            return
        change = {Qt.Key.Key_Left: -1, Qt.Key.Key_Right: 1,
                  Qt.Key.Key_Up: -self.columns, Qt.Key.Key_Down: self.columns}
        if key in change:
            self._highlight(self.index + change[key])
            return
        super().keyPressEvent(event)


class KanaShiftApp(QObject):
    def __init__(self, qt_app: QApplication):
        super().__init__()
        self.app = qt_app
        self.store = QSettings("LuteTools", "KanaShift")
        layouts = available_layouts()
        saved = self.store.value("profiles/slots_json", "", str)
        try:
            saved_list = sanitized_slots(json.loads(saved)) if saved else []
        except (ValueError, TypeError):
            saved_list = []
        self.needs_setup = needs_first_run_setup(saved_list, layouts)
        self.slots = (first_run_slots(layouts) if self.needs_setup
                      else installed_slots(saved_list, layouts))
        if not saved_list:
            # Import the v0.2 Katakana width preference on first v0.3 launch.
            old = self.store.value("width/katakana", "ask", str)
            mapped = {"full":"ja_katakana_full", "half":"ja_katakana_half",
                      "ask":"ja_katakana_ask"}.get(old, "ja_katakana_ask")
            for item in self.slots:
                if item["mode"] == "ja_katakana_ask":
                    item["mode"] = mapped
                    layout = next((x for x in layouts if x.hkl == item["hkl"]), None)
                    if layout:
                        item["name"] = default_name(layout, mapped)
        if not self.slots:
            raise RuntimeError("Windows에서 사용 가능한 입력기 목록을 찾지 못했습니다.")
        self.overlay = Overlay(self.slots)
        self.overlay.picked.connect(self.apply)
        self.overlay.settings_requested.connect(self.show_settings)
        self.settings: SettingsDialog | None = None
        self.dispatcher = Dispatcher()
        self.dispatcher.hotkey.connect(self.toggle)
        self.last_hotkey = 0.0
        self.job = 0
        self.tray = QSystemTrayIcon(make_icon(), qt_app)
        self.tray.setToolTip("KanaShift · CapsLock + Q")
        menu = QMenu()
        menu.addAction("언어 선택   CapsLock + Q", self.show_hud)
        menu.addAction("설정", self.show_settings)
        menu.addSeparator()
        menu.addAction("종료", self.shutdown)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self.on_tray)
        self.tray.show()
        self.hook = CapsQHook(lambda _: self.dispatcher.hotkey.emit(get_target_window()))
        self._hook_started = False
        self.app.aboutToQuit.connect(self.hook.stop)

    def start_hook(self):
        if self._hook_started:
            return
        try:
            self.hook.start()
            self._hook_started = True
        except Exception as e:
            self.warn(f"Hotkey 연결 실패: {e}")

    def show_first_run(self):
        """Configure only the desired 1–6 slots before enabling the hotkey."""
        if not self.needs_setup:
            self.start_hook()
            return
        dlg = SettingsDialog(self.slots, first_run=True)
        self.settings = dlg
        dlg.changed.connect(self.update_slots)
        dlg.accepted.connect(self._first_run_completed)
        dlg.rejected.connect(self.shutdown)
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()

    def _first_run_completed(self):
        self.needs_setup = False
        self.settings = None
        self.start_hook()

    def on_tray(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show_hud()

    def warn(self, message):
        logging.warning(message)
        self.tray.showMessage(APP, message, QSystemTrayIcon.MessageIcon.Warning, 6000)

    def toggle(self, hwnd):
        now = time.monotonic()
        if now-self.last_hotkey < .3:
            return
        self.last_hotkey = now
        if self.overlay.isVisible():
            self.overlay.hide()
        else:
            self.show_hud(hwnd)

    def show_hud(self, hwnd: int=0):
        if self.needs_setup:
            if self.settings is None or not self.settings.isVisible():
                self.show_first_run()
            return
        if self.settings and self.settings.isVisible():
            self.settings.hide()
        target = hwnd or get_target_window()
        if not target:
            self.warn("입력할 창을 먼저 선택해 주세요.")
            return
        # Pick up Windows input-method additions/removals without restarting.
        current = installed_slots(self.slots, available_layouts())
        if current != self.slots:
            self.slots = current
            self.overlay.set_slots(current)
        self.overlay.open_hud(target)

    def show_settings(self):
        if self.needs_setup:
            if self.settings is None or not self.settings.isVisible():
                self.show_first_run()
            return
        self.overlay.hide()
        if self.settings:
            self.settings.close()
        self.settings = SettingsDialog(self.slots)
        self.settings.changed.connect(self.update_slots)
        self.settings.show()
        self.settings.raise_()
        self.settings.activateWindow()

    def update_slots(self, slots):
        values = sanitized_slots(slots)
        if not values:
            return
        self.slots = values[:MAX_SLOTS]
        self.store.setValue("profiles/slots_json", json.dumps(self.slots, ensure_ascii=False))
        self.store.sync()
        self.overlay.set_slots(self.slots)

    def apply(self, slot):
        self.job += 1
        job = self.job
        hwnd = self.overlay.target_hwnd
        try:
            target = hkl_number(slot["hkl"])
            if hkl_string(current_hkl(hwnd)) != hkl_string(target):
                request_hkl(hwnd, target)
            foreground_target(hwnd)
        except (IMEError, ValueError) as e:
            self.warn(str(e))
            return
        QTimer.singleShot(130, lambda: self._check_layout(job, hwnd, slot, 0))

    def _check_layout(self, job: int, hwnd: int, slot, tries: int):
        if job != self.job:
            return
        target = hkl_number(slot["hkl"])
        if hkl_string(current_hkl(hwnd)) == hkl_string(target):
            foreground_target(hwnd)
            QTimer.singleShot(85, lambda: self._apply_mode(job, hwnd, slot))
            return
        if tries == 2:
            try:
                request_hkl(hwnd, target, to_root=True)
            except IMEError as e:
                self.warn(str(e))
                return
        if tries >= 5:
            self._fallback_cycle(job, hwnd, slot, 0)
            return
        QTimer.singleShot(135, lambda: self._check_layout(job, hwnd, slot, tries+1))

    def _fallback_cycle(self, job, hwnd, slot, count):
        if job != self.job:
            return
        target = hkl_number(slot["hkl"])
        if hkl_string(current_hkl(hwnd)) == hkl_string(target):
            self._apply_mode(job, hwnd, slot)
            return
        limit = len(available_layouts())+1
        if count >= limit:
            self.warn("입력기 전환 실패")
            return
        if not cycle_windows_language(hwnd):
            self.warn("Hotkey를 전달하지 못했습니다.")
            return
        QTimer.singleShot(240, lambda: self._fallback_cycle(job, hwnd, slot, count+1))

    def _apply_mode(self, job, hwnd, slot):
        if job != self.job:
            return
        if not foreground_target(hwnd):
            self.warn("원래 입력 창으로 돌아가지 못했습니다.")
            return
        mode = slot["mode"]
        if mode == "default":
            return
        if mode in ("ko_hangul", "ko_latin"):
            expected = mode == "ko_hangul"
            if korean_set(hwnd, expected):
                return
            if not korean_toggle_key(hwnd):
                self.warn("한국어 한/영 전환키를 전달하지 못했습니다.")
                return
            QTimer.singleShot(180, lambda: self._verify_korean(job, hwnd, expected))
            return
        if mode.startswith("ja_"):
            kind = {"ja_hiragana":"hiragana", "ja_katakana_full":"katakana_full",
                    "ja_katakana_half":"katakana_half"}.get(mode)
            if not kind:
                return
            if japanese_set(hwnd, kind):
                return
            self._japanese_fallback(job, hwnd, kind, 0)

    def _verify_korean(self, job, hwnd, expected):
        if job == self.job and korean_is_hangul(hwnd) != expected:
            self.warn("한국어 입력 모드를 확인하지 못했습니다. Microsoft IME에서 확인하세요.")

    def _japanese_fallback(self, job, hwnd, kind, n):
        if job != self.job:
            return
        if japanese_matches(hwnd, kind):
            return
        limit = 3 if kind == "katakana_half" else 1
        if n >= limit:
            self.warn("일본어 문자 모드 전환을 확인하지 못했습니다. Microsoft 일본어 IME에서 확인해 주세요.")
            return
        if not japanese_fallback_key(hwnd, kind):
            self.warn("일본어 IME 키 입력 실패")
            return
        QTimer.singleShot(150, lambda: self._japanese_fallback(job, hwnd, kind, n+1))

    def shutdown(self):
        self.job += 1
        self.hook.stop()
        self.overlay.close()
        if self.settings:
            self.settings.close()
        self.tray.hide()
        self.app.quit()


def main():
    if sys.platform != "win32":
        print("Windows 전용 프로그램입니다.", file=sys.stderr)
        return 1
    app = QApplication(sys.argv)
    app.setApplicationName(APP)
    app.setWindowIcon(make_icon())
    app.setQuitOnLastWindowClosed(False)
    splash = StartupSplash()
    splash.show()
    running = {}  # keep a strong reference for the lifetime of the Qt loop

    def initialize():
        try:
            running["manager"] = KanaShiftApp(app)
        except Exception as error:
            logging.exception("KanaShift startup failed")
            splash.finish()
            QMessageBox.critical(None, "KanaShift 실행 오류", str(error))
            QTimer.singleShot(0, app.quit)
        else:
            # Finish loading, then ask for only the desired slots on first run.
            # Existing valid profiles skip the wizard and activate the hotkey.
            def startup_ready():
                splash.finish()
                running["manager"].show_first_run()
            QTimer.singleShot(380, startup_ready)

    # Let Qt paint the loading screen before input-hook initialization.
    QTimer.singleShot(40, initialize)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
