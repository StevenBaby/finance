import sys
import requests

from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import QTimer, Qt

__version__ = "1.0.0"


class UsdCnyWidget(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("USD/CNY 实时汇率")
        self.setMinimumSize(340, 180)
        self.resize(400, 220)

        central = QWidget()
        self.setCentralWidget(central)

        layout = QVBoxLayout()
        layout.setSpacing(8)
        layout.setContentsMargins(24, 20, 24, 20)

        title = QLabel("美元 / 在岸人民币")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title)

        self.rate_label = QLabel("加载中...")
        self.rate_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.rate_label.setStyleSheet("font-size: 36px; color: #2c3e50;")
        layout.addWidget(self.rate_label)

        layout.addStretch()

        self.info_label = QLabel("")
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.info_label.setStyleSheet("font-size: 11px; color: #888;")
        layout.addWidget(self.info_label)

        central.setLayout(layout)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.fetch_rate)
        self.timer.start(5000)
        self.fetch_rate()

    def fetch_rate(self):
        try:
            r = requests.get(
                "https://hq.sinajs.cn/list=fx_susdcny",
                headers={"Referer": "https://finance.sina.com.cn"},
                timeout=5,
            )
            r.encoding = "gbk"
            data = r.text
            if not data.startswith("var"):
                return

            parts = data.split('"')[1].split(",")
            if len(parts) < 2:
                return

            price = parts[1]
            if price == "0.0000":
                return

            self.rate_label.setText(price)

            parsed = data.split('"')[1]
            fields = parsed.split(",")
            open_price = fields[2]
            high = fields[3]
            low = fields[4]
            prev_close = fields[8]
            self.info_label.setText(
                f"昨收 {prev_close}  今日开盘 {open_price}  最高 {high}  最低 {low}"
            )
        except Exception:
            pass


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = UsdCnyWidget()
    window.show()
    sys.exit(app.exec())
