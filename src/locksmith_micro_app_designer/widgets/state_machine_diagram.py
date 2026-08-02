# -*- encoding: utf-8 -*-
"""StateMachineDiagram: TEL lifecycle visualization for exported credentials.

Color-coded by transition *driver* (`via_command` / `via_reaction` /
`via_workflow` / `trigger: "automatic"`), not `tel_primitive` -- that field
was deleted (authoring spec §6.3, primitives-are-given AMENDMENT-WAVE
BLOCK, 2026-08-01/02): the TEL records state, not transition, so the
transition's driver is what the protocol actually lets an edge declare.
A transition may declare several drivers at once (legal -- e.g. a licence
suspended by a regulator command *or* on premium lapse), rendered as
`"multi"`; a transition with none declared is a defect
(`missing_transition_driver`) and is rendered as `"none"`, distinctly from
every legal kind, so it reads as a defect rather than silently as blank.
Pure QGraphicsScene; no external SVG.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Union

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QPen, QPolygonF
from PySide6.QtWidgets import QGraphicsScene, QGraphicsView


_DRIVER_COLOR: dict[str, str] = {
    "command": "#D97757",
    "reaction": "#0ABFB0",
    "workflow": "#5B8DEF",
    "automatic": "#A36AE6",
    "multi": "#D6A419",
    "none": "#E94B7B",
}

# Neutral anchor color for a state with no incoming transition. Under the
# "issuance is initialization, not a transition" ruling (owner, 2026-08-01)
# an initial state is not itself driven by anything -- it isn't a defect,
# so it does not borrow the "none" driver's alarm color.
_ANCHOR_COLOR = "#8A8F98"


def edge_style(transition: dict) -> dict:
    """Pure function: `{"driver": str, "colour": str}` for one transition
    dict (the `$defs/transition` shape). Keyed off which of the four driver
    kinds the transition declares -- `via_command`/`via_reaction` (lists),
    `via_workflow` (string), `trigger: "automatic"` -- not off `tel_primitive`,
    which no longer exists on a transition.

    An empty `via_command`/`via_reaction` list does not count as declared
    (matches the schema's "at least one" `missing_transition_driver` rule),
    and `trigger: "manual"` names no command, so it is not one of the four
    driver kinds either.
    """
    drivers: list[str] = []
    if transition.get("via_command"):
        drivers.append("command")
    if transition.get("via_reaction"):
        drivers.append("reaction")
    if transition.get("via_workflow"):
        drivers.append("workflow")
    if transition.get("trigger") == "automatic":
        drivers.append("automatic")

    if len(drivers) > 1:
        driver = "multi"
    elif len(drivers) == 1:
        driver = drivers[0]
    else:
        driver = "none"
    return {"driver": driver, "colour": _DRIVER_COLOR[driver]}


def _tint(hex_color: str, alpha: float) -> str:
    """Mix a hex color with white at the given alpha — returns hex string."""
    h = hex_color.lstrip("#")
    r = int(h[0:2], 16)
    g = int(h[2:4], 16)
    b = int(h[4:6], 16)
    r = int(255 - (255 - r) * alpha)
    g = int(255 - (255 - g) * alpha)
    b = int(255 - (255 - b) * alpha)
    return f"#{r:02X}{g:02X}{b:02X}"


@dataclass
class StateTransition:
    from_state: Union[str, list[str]]
    to_state: str
    via_command: list[str] = field(default_factory=list)
    via_reaction: list[str] = field(default_factory=list)
    via_workflow: str = ""
    trigger: str = ""

    def driver_spec(self) -> dict:
        """The subset of `$defs/transition` fields `edge_style` needs."""
        return {
            "via_command": self.via_command,
            "via_reaction": self.via_reaction,
            "via_workflow": self.via_workflow,
            "trigger": self.trigger,
        }


class StateMachineDiagram(QGraphicsView):
    NODE_W = 110
    NODE_H = 44
    H_GAP = 70
    BASE_Y = 60

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setStyleSheet("background:#fff;border:0;")
        self._state_count = 0

    @property
    def state_count(self) -> int:
        return self._state_count

    def _expand(self, transitions: list[StateTransition]) -> list[tuple[str, str, dict]]:
        out: list[tuple[str, str, dict]] = []
        for t in transitions:
            srcs = t.from_state if isinstance(t.from_state, list) else [t.from_state]
            style = edge_style(t.driver_spec())
            for src in srcs:
                out.append((src, t.to_state, style))
        return out

    def render(self, transitions: list[StateTransition]) -> None:
        self._scene.clear()
        self._node_fills: dict[str, str] = {}
        self._label_specs: list[dict] = []
        expanded = self._expand(transitions)
        seen: list[str] = []
        for src, dst, _ in expanded:
            for s in (src, dst):
                if s and s not in seen:
                    seen.append(s)
        self._state_count = len(seen)

        for src, dst, style in expanded:
            self._node_fills.setdefault(dst, style["colour"])
        for s in seen:
            if s not in self._node_fills:
                # Initial state — no incoming transition (issuance is
                # initialization, not a transition), so it gets the neutral
                # anchor color rather than any driver's colour.
                self._node_fills[s] = _ANCHOR_COLOR

        positions: dict[str, QPointF] = {}
        for i, s in enumerate(seen):
            x = 20 + i * (self.NODE_W + self.H_GAP)
            y = self.BASE_Y
            positions[s] = QPointF(x, y)
            fill_color = self._node_fills[s]
            tinted = _tint(fill_color, 0.20)
            self._scene.addRect(
                QRectF(x, y, self.NODE_W, self.NODE_H),
                QPen(QColor(fill_color), 1.5),
                QBrush(QColor(tinted)),
            )
            label_font = QFont()
            label_font.setPointSize(10)
            label_font.setBold(True)
            text = self._scene.addText(s, label_font)
            text.setDefaultTextColor(QColor("#1A1C20"))
            text.setPos(x + 8, y + 10)

        for src, dst, style in expanded:
            if src not in positions or dst not in positions:
                continue
            start = positions[src]
            end = positions[dst]
            color = QColor(style["colour"])
            pen = QPen(color, 2)
            if src == dst:
                self._scene.addEllipse(
                    QRectF(start.x() + self.NODE_W / 2 - 18, start.y() - 28, 36, 28),
                    pen,
                    QBrush(Qt.NoBrush),
                )
                continue
            x1 = start.x() + self.NODE_W
            y1 = start.y() + self.NODE_H / 2
            x2 = end.x()
            y2 = end.y() + self.NODE_H / 2
            self._scene.addLine(x1, y1, x2, y2, pen)
            angle = math.atan2(y2 - y1, x2 - x1)
            ahx = x2 - 10 * math.cos(angle - math.pi / 6)
            ahy = y2 - 10 * math.sin(angle - math.pi / 6)
            ahx2 = x2 - 10 * math.cos(angle + math.pi / 6)
            ahy2 = y2 - 10 * math.sin(angle + math.pi / 6)
            poly = QPolygonF(
                [QPointF(x2, y2), QPointF(ahx, ahy), QPointF(ahx2, ahy2)]
            )
            self._scene.addPolygon(poly, pen, QBrush(color))

            label_text = style["driver"]
            chip_w = max(34, len(label_text) * 7 + 12)
            chip_h = 16
            mid_x = (x1 + x2) / 2
            mid_y = (y1 + y2) / 2 - chip_h - 4
            tinted_bg = _tint(style["colour"], 0.22)
            self._scene.addRect(
                QRectF(mid_x - chip_w / 2, mid_y, chip_w, chip_h),
                QPen(color, 1),
                QBrush(QColor(tinted_bg)),
            )
            label_font = QFont()
            label_font.setPointSize(8)
            label_font.setBold(True)
            text = self._scene.addText(label_text, label_font)
            text.setDefaultTextColor(color)
            text.setPos(mid_x - len(label_text) * 3.2, mid_y - 2)
            self._label_specs.append({
                "text": label_text,
                "color": style["colour"],
                "chip": True,
            })

    def node_fill_map(self) -> dict[str, str]:
        return dict(getattr(self, "_node_fills", {}))

    def transition_label_specs(self) -> list[dict]:
        return list(getattr(self, "_label_specs", []))
