import sys
import os
import re
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton,
    QFileDialog, QVBoxLayout, QHBoxLayout, QSlider
)
from PyQt6.QtGui import QPixmap, QPainter
from PyQt6.QtCore import Qt, QPoint
from PIL import Image


OUTPUT_DIR = "Output"


def get_next_output_number():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    numbers = []
    for f in os.listdir(OUTPUT_DIR):
        match = re.match(r"output(\d+)\.jpg", f, re.IGNORECASE)
        if match:
            numbers.append(int(match.group(1)))

    return max(numbers, default=0) + 1


class ImageEditor(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Logo Placement Tool")
        self.setFixedSize(900, 700)

        self.bg_pixmap = None
        self.logo_pixmap = None
        self.logo_pos = QPoint(200, 200)
        self.logo_scale = 1.0
        self.dragging = False

        self.label = QLabel(self)
        self.label.setFixedSize(800, 500)
        self.label.setStyleSheet("background-color: #ddd")

        self.load_bg_btn = QPushButton("Load Showroom Image")
        self.load_logo_btn = QPushButton("Load Logo")
        self.save_btn = QPushButton("Save Output")

        self.scale_slider = QSlider(Qt.Orientation.Horizontal)
        self.scale_slider.setMinimum(10)
        self.scale_slider.setMaximum(200)
        self.scale_slider.setValue(100)

        self.scale_slider.valueChanged.connect(self.change_scale)
        self.load_bg_btn.clicked.connect(self.load_background)
        self.load_logo_btn.clicked.connect(self.load_logo)
        self.save_btn.clicked.connect(self.save_image)

        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.load_bg_btn)
        btn_layout.addWidget(self.load_logo_btn)
        btn_layout.addWidget(self.save_btn)

        layout = QVBoxLayout()
        layout.addWidget(self.label)
        layout.addWidget(QLabel("Logo Size"))
        layout.addWidget(self.scale_slider)
        layout.addLayout(btn_layout)

        self.setLayout(layout)

    def load_background(self):
        file, _ = QFileDialog.getOpenFileName(self, "Select Showroom Image")
        if file:
            self.bg_pixmap = QPixmap(file).scaled(
                self.label.size(), Qt.AspectRatioMode.KeepAspectRatio
            )
            self.update_canvas()

    def load_logo(self):
        file, _ = QFileDialog.getOpenFileName(self, "Select Logo Image")
        if file:
            self.logo_pixmap = QPixmap(file)
            self.update_canvas()

    def change_scale(self, value):
        self.logo_scale = value / 100
        self.update_canvas()

    def update_canvas(self):
        if not self.bg_pixmap:
            return

        canvas = QPixmap(self.bg_pixmap)
        painter = QPainter(canvas)

        if self.logo_pixmap:
            scaled_logo = self.logo_pixmap.scaled(
                int(self.logo_pixmap.width() * self.logo_scale),
                int(self.logo_pixmap.height() * self.logo_scale),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            painter.drawPixmap(self.logo_pos, scaled_logo)

        painter.end()
        self.label.setPixmap(canvas)

    def mousePressEvent(self, event):
        if self.logo_pixmap:
            self.dragging = True
            self.offset = event.position().toPoint() - self.logo_pos

    def mouseMoveEvent(self, event):
        if self.dragging:
            self.logo_pos = event.position().toPoint() - self.offset
            self.update_canvas()

    def mouseReleaseEvent(self, event):
        self.dragging = False

    def save_image(self):
        if not self.bg_pixmap or not self.logo_pixmap:
            return

        output_number = get_next_output_number()
        output_path = os.path.join(OUTPUT_DIR, f"output{output_number}.jpg")

        # Convert background
        bg_image = Image.fromqpixmap(self.bg_pixmap).convert("RGB")

        # Convert logo (force RGBA for transparency)
        logo_image = Image.fromqpixmap(self.logo_pixmap).convert("RGBA")

        logo_w = int(logo_image.width * self.logo_scale)
        logo_h = int(logo_image.height * self.logo_scale)
        logo_image = logo_image.resize((logo_w, logo_h), Image.LANCZOS)

        bg_image.paste(
            logo_image,
            (self.logo_pos.x(), self.logo_pos.y()),
            logo_image  # transparency mask
        )

        bg_image.save(output_path, "JPEG", quality=95)
        print(f"Saved: {output_path}")



if __name__ == "__main__":
    app = QApplication(sys.argv)
    editor = ImageEditor()
    editor.show()
    sys.exit(app.exec())
