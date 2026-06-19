import os
import sys
import time
from collections import deque

from PySide6.QtCore import Qt, QTimer, QPointF, QRectF
from PySide6.QtGui import (
    QFont,
    QColor,
    QPalette,
    QPixmap,
    QPainter,
    QPen,
    QBrush,
    QLinearGradient,
    QPainterPath,
    QIcon,
)
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QFrame,
    QSizePolicy,
)

from api import fetch_all_gold

__version__ = "2.4.1"


# 主题配色 —— 亮色质感金主题
BG_DARK = "#f4f6fb"
BG_PANEL = "#ffffff"
BG_PANEL_HOVER = "#f7f9fc"
GOLD = "#c8901a"
GOLD_BRIGHT = "#b88200"
ACCENT_GREEN = "#16a34a"
ACCENT_RED = "#dc2626"
TEXT_PRIMARY = "#1f2937"
TEXT_SECONDARY = "#6b7280"
BORDER = "#e2e8f0"


class Series:
    """一条走势序列"""

    def __init__(self, name: str, color: str):
        self.name = name
        self.color = color
        self.values: deque[float] = deque()
        self.visible = True

    def push(self, v: float):
        self.values.append(v)

    def latest(self) -> float:
        return self.values[-1] if self.values else 0.0


class SparklineChart(QFrame):
    """自绘走势图：支持多条曲线，新数据从右侧滚入。"""

    MAX_POINTS = 120

    def __init__(self):
        super().__init__()
        self.setObjectName("chart")
        self.setMinimumHeight(220)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet(
            f"QFrame#chart {{ background: {BG_PANEL}; border: 1px solid {BORDER};"
            f"border-radius: 10px; }}"
        )

        self.series: dict[str, Series] = {}
        self.timestamps: deque[float] = deque()

    def add_series(self, key: str, name: str, color: str):
        self.series[key] = Series(name, color)

    def push(self, key: str, value: float):
        if key not in self.series or not value:
            return
        s = self.series[key]
        s.push(value)
        if key == next(iter(self.series)):
            self.timestamps.append(time.time())
            if len(self.timestamps) > self.MAX_POINTS:
                self.timestamps.popleft()
        if len(s.values) > self.MAX_POINTS:
            s.values.popleft()
        self.update()

    def paintEvent(self, _ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width()
        h = self.height()
        # 顶部预留一行给标题/图例（图表外），不与 grid 重叠
        header_h = 22
        pad_l, pad_r, pad_t, pad_b = 56, 16, header_h + 8, 26
        plot_w = w - pad_l - pad_r
        plot_h = h - pad_t - pad_b

        # 标题（顶部居中，位于图表区域之外）
        p.setPen(QColor(TEXT_PRIMARY))
        p.setFont(QFont("Microsoft YaHei UI", 10, QFont.Weight.Bold))
        p.drawText(
            QRectF(0, 2, w, 18),
            Qt.AlignmentFlag.AlignCenter,
            "黄金价格走势  ·  实时滚动",
        )

        # 图例（右上角，图表区域之外）
        p.setFont(QFont("Microsoft YaHei UI", 8))
        leg_x = w - pad_r
        leg_y = 4
        legends = [s for s in self.series.values() if s.visible]
        # 从右向左排布
        for s in reversed(legends):
            text = s.name
            fm = p.fontMetrics()
            tw = fm.horizontalAdvance(text)
            item_w = tw + 22
            leg_x -= item_w
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(QColor(s.color)))
            p.drawRect(QRectF(leg_x, leg_y + 6, 12, 3))
            p.setPen(QColor(TEXT_PRIMARY))
            p.drawText(
                QRectF(leg_x + 16, leg_y, tw + 6, 16),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                text,
            )
            leg_x -= 8  # 间距

        # 网格 + Y 轴刻度
        p.setPen(QPen(QColor(BORDER), 1, Qt.PenStyle.DashLine))
        steps = 4
        for i in range(steps + 1):
            y = pad_t + plot_h * i / steps
            p.drawLine(QPointF(pad_l, y), QPointF(pad_l + plot_w, y))

        # 计算统一 Y 范围（按可见序列）
        all_vals = []
        for s in self.series.values():
            if s.visible and s.values:
                all_vals.extend(s.values)
        if not all_vals:
            p.setPen(QColor(TEXT_SECONDARY))
            p.drawText(
                QRectF(pad_l, pad_t, plot_w, plot_h),
                Qt.AlignmentFlag.AlignCenter,
                "等待行情数据…",
            )
            return
        vmin, vmax = min(all_vals), max(all_vals)
        span = vmax - vmin
        if span < 1e-6:
            span = max(abs(vmax) * 0.001, 1.0)
        vmin -= span * 0.12
        vmax += span * 0.12

        # Y 轴标签
        p.setPen(QColor(TEXT_SECONDARY))
        p.setFont(QFont("Microsoft YaHei UI", 8))
        for i in range(steps + 1):
            val = vmax - (vmax - vmin) * i / steps
            y = pad_t + plot_h * i / steps
            p.drawText(
                QRectF(0, y - 8, pad_l - 6, 16),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                f"{val:,.1f}",
            )

        # X 轴时间标签（首尾）
        if len(self.timestamps) >= 2:
            t0, t1 = self.timestamps[0], self.timestamps[-1]
            from datetime import datetime

            ts0 = datetime.fromtimestamp(t0).strftime("%H:%M:%S")
            ts1 = datetime.fromtimestamp(t1).strftime("%H:%M:%S")
            p.drawText(
                QRectF(pad_l, h - pad_b + 4, 120, 18), Qt.AlignmentFlag.AlignLeft, ts0
            )
            p.drawText(
                QRectF(pad_l + plot_w - 120, h - pad_b + 4, 120, 18),
                Qt.AlignmentFlag.AlignRight,
                ts1,
            )

        # 绘制每条曲线
        n = len(self.timestamps)
        for s in self.series.values():
            if not s.visible or len(s.values) < 2:
                continue
            vals = list(s.values)
            # 对齐长度
            m = min(len(vals), n)
            vals = vals[-m:]
            xs = n - m
            pts = []
            for i, v in enumerate(vals):
                x = pad_l + (xs + i) * plot_w / max(n - 1, 1)
                y = pad_t + plot_h * (1 - (v - vmin) / (vmax - vmin))
                pts.append(QPointF(x, y))

            # 渐变填充
            path = QPainterPath()
            path.moveTo(pts[0])
            for pt in pts[1:]:
                path.lineTo(pt)
            fill = QPainterPath(pts[0])
            for pt in pts[1:]:
                fill.lineTo(pt)
            fill.lineTo(QPointF(pts[-1].x(), pad_t + plot_h))
            fill.lineTo(QPointF(pts[0].x(), pad_t + plot_h))
            fill.closeSubpath()
            grad = QLinearGradient(0, pad_t, 0, pad_t + plot_h)
            c = QColor(s.color)
            c.setAlpha(48)
            grad.setColorAt(0, c)
            c2 = QColor(s.color)
            c2.setAlpha(0)
            grad.setColorAt(1, c2)
            p.fillPath(fill, QBrush(grad))

            # 折线
            pen = QPen(QColor(s.color), 2)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            p.setPen(pen)
            p.drawPath(path)

            # 最新点 + 数值
            p.setBrush(QBrush(QColor(s.color)))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(pts[-1], 3.5, 3.5)
            p.setPen(QColor(s.color))
            p.setFont(QFont("Microsoft YaHei UI", 8, QFont.Weight.Bold))
            p.drawText(
                QRectF(pts[-1].x() + 6, pts[-1].y() - 10, 80, 16),
                Qt.AlignmentFlag.AlignLeft,
                f"{vals[-1]:,.2f}",
            )


class Card(QFrame):
    """单张行情卡片"""

    def __init__(self, title: str, unit: str, accent: str = GOLD):
        super().__init__()
        self.setObjectName("card")
        self.accent = accent
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        layout = QVBoxLayout(self)
        layout.setSpacing(2)
        layout.setContentsMargins(18, 14, 18, 14)

        head = QHBoxLayout()
        self.title_label = QLabel(title)
        self.title_label.setObjectName("cardTitle")
        head.addWidget(self.title_label)
        head.addStretch()
        self.unit_label = QLabel(unit)
        self.unit_label.setObjectName("cardUnit")
        head.addWidget(self.unit_label)
        layout.addLayout(head)

        self.price_label = QLabel("--")
        self.price_label.setObjectName("cardPrice")
        layout.addWidget(self.price_label)

        self.change_label = QLabel("")
        self.change_label.setObjectName("cardChange")
        layout.addWidget(self.change_label)

        self.implied_label = QLabel("")
        self.implied_label.setObjectName("cardImplied")
        layout.addWidget(self.implied_label)

        self.extra_label = QLabel("")
        self.extra_label.setObjectName("cardExtra")
        layout.addWidget(self.extra_label)

    def set_accent(self, accent: str):
        self.accent = accent
        self.setStyleSheet(self._style())

    def _style(self) -> str:
        return f"""
            QFrame#card {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 {BG_PANEL}, stop:1 {BG_PANEL_HOVER});
                border: 1px solid {BORDER};
                border-left: 3px solid {self.accent};
                border-radius: 10px;
            }}
            QLabel#cardTitle {{
                color: {TEXT_SECONDARY};
                font-size: 12px;
                letter-spacing: 1px;
            }}
            QLabel#cardUnit {{
                color: {TEXT_SECONDARY};
                font-size: 11px;
            }}
            QLabel#cardPrice {{
                color: {GOLD_BRIGHT};
                font-size: 30px;
                font-weight: bold;
                padding-top: 2px;
            }}
            QLabel#cardChange {{
                font-size: 12px;
                font-weight: bold;
            }}
            QLabel#cardExtra {{
                color: {TEXT_SECONDARY};
                font-size: 10px;
            }}
            QLabel#cardImplied {{
                color: #0ea5e9;
                font-size: 11px;
                font-weight: bold;
                padding-top: 1px;
            }}
        """

    def update_price(
        self, price: str, change_str: str, extra: str, up: bool, implied: str = ""
    ):
        self.price_label.setText(price)
        color = ACCENT_GREEN if up else ACCENT_RED if up is False else TEXT_SECONDARY
        self.change_label.setText(change_str)
        self.change_label.setStyleSheet(
            f"QLabel#cardChange {{ color: {color}; font-size: 12px; font-weight: bold; }}"
        )
        self.implied_label.setText(implied)
        self.extra_label.setText(extra)
        self.setStyleSheet(self._style())


class GoldWidget(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Gold Pulse · 实时金价")
        self.setMinimumSize(820, 600)
        self.resize(1000, 720)

        # 窗口图标（兼容源码运行与 PyInstaller 打包）
        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "app.ico")
        if not os.path.exists(icon_path):
            base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
            icon_path = os.path.join(base, "assets", "app.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        # 窗口整体背景
        self.setStyleSheet(f"""
            QMainWindow {{
                background: qradialgradient(cx:0.3, cy:0.0, radius:1.4,
                    stop:0 #ffffff, stop:1 {BG_DARK});
            }}
        """)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setSpacing(14)
        root.setContentsMargins(22, 18, 22, 18)

        # 顶部标题栏
        root.addLayout(self._build_header())

        # 三张价格卡片
        cards_row = QHBoxLayout()
        cards_row.setSpacing(12)
        self.card_london = Card("伦敦金 XAU", "USD/oz", accent="#b88200")
        self.card_newyork = Card("纽约金 COMEX", "USD/oz", accent="#0ea5e9")
        self.card_shanghai = Card("上海金 沪金连续", "CNY/g", accent="#16a34a")
        for c in (self.card_london, self.card_newyork, self.card_shanghai):
            cards_row.addWidget(c)
        root.addLayout(cards_row)

        # 走势图（填充下方空间，新数据从右侧滚入）
        self.chart = SparklineChart()
        self.chart.add_series("london", "伦敦金(折算 CNY/g)", "#b88200")
        self.chart.add_series("newyork", "纽约金(折算 CNY/g)", "#0ea5e9")
        self.chart.add_series("shanghai", "上海金 CNY/g", "#16a34a")
        root.addWidget(self.chart, 1)

        # 底部状态栏
        self.status_label = QLabel("● 连接中...")
        self.status_label.setObjectName("status")
        self.status_label.setStyleSheet(
            f"QLabel#status {{ color: {TEXT_SECONDARY}; font-size: 11px; }}"
        )
        root.addWidget(self.status_label)

        # 定时刷新（5 秒，含伦敦金/纽约金/上海金/汇率）
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(5000)
        self.refresh()

    def _build_header(self) -> QHBoxLayout:
        box = QHBoxLayout()
        title = QLabel("GOLD  PULSE")
        title.setStyleSheet(
            f"color: {GOLD_BRIGHT}; font-size: 26px; font-weight: bold; letter-spacing: 4px;"
        )
        sub = QLabel("实时黄金行情 · 三大市场联动")
        sub.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 11px;")
        box.addWidget(title)
        box.addSpacing(14)
        box.addWidget(sub)
        box.addStretch()

        self.usdcny_label = QLabel("USD/CNY --")
        self.usdcny_label.setStyleSheet(
            f"color: {TEXT_PRIMARY}; font-size: 13px; padding: 4px 10px;"
            f"border: 1px solid {BORDER}; border-radius: 6px;"
        )
        box.addWidget(self.usdcny_label)
        return box

    def _update_card(self, card: "Card", item: dict | None, prev_label: str):
        """根据 api 返回的单品种数据更新卡片，返回最新价供走势图使用。

        prev_label: 昨收/昨结的中文标签
        """
        if not item:
            return None
        price = item["price"]
        prev_close = item["prev_close"]
        high = item["high"]
        low = item["low"]
        diff = item["diff"]
        pct = item["pct"]
        card.update_price(
            f"{price:,.2f}",
            f"{'▲' if diff>=0 else '▼'} {abs(diff):.2f}  ({pct:+.2f}%)",
            f"{prev_label} {prev_close:.2f}  高 {high}  低 {low}",
            diff >= 0,
            implied=item.get("implied", ""),
        )
        return price

    def refresh(self):
        try:
            result = fetch_all_gold()
            if not result:
                self.status_label.setText("● 等待数据...")
                return

            usdcny = result["usdcny"]
            implied_cny_g = result["implied_cny_g"]
            implied_source = result["implied_source"]

            if usdcny:
                self.usdcny_label.setText(f"USD/CNY {usdcny:.4f}")

            # 伦敦金（走势图用折算 CNY/g）
            v = self._update_card(self.card_london, result["london"], "昨结")
            if v:
                self.chart.push("london", implied_cny_g if implied_cny_g else v)

            # 纽约金（走势图用折算 CNY/g）
            v = self._update_card(self.card_newyork, result["newyork"], "昨收")
            if v:
                self.chart.push("newyork", implied_cny_g if implied_cny_g else v)

            # 上海金（走势图用原价 CNY/g）
            sh = result["shanghai"]
            if sh and sh["price"]:
                self._update_card(self.card_shanghai, sh, "昨收")
                self.chart.push("shanghai", sh["price"])
            elif implied_cny_g:
                # 沪金接口失败，回退折算价
                self.card_shanghai.update_price(
                    f"{implied_cny_g:,.2f}",
                    "—",
                    f"由 {implied_source} + USD/CNY 折算  (1oz=31.1035g)",
                    None,
                    implied="（沪金接口暂不可用，显示折算价）",
                )
                self.chart.push("shanghai", implied_cny_g)

            self.status_label.setText("● 实时连接中  · 每 5 秒刷新")
            self.status_label.setStyleSheet(
                f"QLabel#status {{ color: {ACCENT_GREEN}; font-size: 11px; }}"
            )
        except Exception as e:
            self.status_label.setText(f"● 更新失败: {e}")
            self.status_label.setStyleSheet(
                f"QLabel#status {{ color: {ACCENT_RED}; font-size: 11px; }}"
            )


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # 全局字体
    font = QFont("Microsoft YaHei UI", 12)
    app.setFont(font)

    window = GoldWidget()
    window.show()
    sys.exit(app.exec())
