from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QStyle,
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QFont, QIcon, QPixmap, QPainter, QColor

from core.models import Unit, Lesson


class CourseOverviewView(QWidget):
    lesson_selected = Signal(str)

    def __init__(self, course_manager, progress_manager, parent=None):
        super().__init__(parent)
        self.course_manager = course_manager
        self.progress_manager = progress_manager

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        title_label = QLabel(
            self.course_manager.get_course_title() or "Language Course"
        )
        title_font = QFont("Arial", 18, QFont.Bold)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.main_layout.addWidget(title_label)

        xp_label_text = f"Total XP: {self.progress_manager.get_total_xp()}"
        self.xp_label = QLabel(xp_label_text)
        self.xp_label.setFont(QFont("Arial", 10))
        self.xp_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.main_layout.addWidget(self.xp_label)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_content_widget = QWidget()
        self.units_layout = QVBoxLayout(self.scroll_content_widget)
        self.units_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll_area.setWidget(self.scroll_content_widget)

        self.main_layout.addWidget(self.scroll_area)
        self.populate_units()

    def populate_units(self):
        while self.units_layout.count():
            child = self.units_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        units = self.course_manager.get_units()
        all_course_units_for_unlock_check = self.course_manager.get_units()

        for unit in units:
            unit_groupbox = QGroupBox(unit.title)
            unit_groupbox.setFont(QFont("Arial", 14, QFont.DemiBold))
            unit_layout = QVBoxLayout()

            for lesson in unit.lessons:
                lesson_button_text = f"{lesson.title}"
                is_completed = self.progress_manager.is_lesson_completed(
                    lesson.lesson_id, self.course_manager
                )
                current_unit_lessons = unit.lessons
                is_unlocked = self.progress_manager.is_lesson_unlocked(
                    lesson.lesson_id,
                    current_unit_lessons,
                    all_course_units_for_unlock_check,
                    self.course_manager,
                )

                lesson_button = QPushButton(lesson.title)
                lesson_button.setFont(QFont("Arial", 11))
                lesson_button.setMinimumHeight(40)

                button_style = "QPushButton { text-align: left; padding: 5px; }"

                icon = None
                if is_completed:
                    pixmap = QPixmap(16, 16)
                    pixmap.fill(Qt.transparent)
                    painter = QPainter(pixmap)
                    painter.setFont(QFont("Arial", 12, QFont.Bold))
                    painter.setPen(QColor("green"))
                    painter.drawText(pixmap.rect(), Qt.AlignCenter, "✓")
                    painter.end()
                    icon = QIcon(pixmap)
                elif is_unlocked:
                    icon = self.style().standardIcon(QStyle.SP_MediaPlay)
                else:
                    icon = self.style().standardIcon(QStyle.SP_DialogNoButton)

                if icon:
                    lesson_button.setIcon(icon)

                lesson_button.setText(lesson_button_text)
                lesson_button.setStyleSheet(button_style)

                if is_unlocked and not is_completed:
                    lesson_button.clicked.connect(
                        lambda checked=False, lid=lesson.lesson_id: self.lesson_selected.emit(
                            lid
                        )
                    )
                elif is_completed:
                    lesson_button.clicked.connect(
                        lambda checked=False, lid=lesson.lesson_id: self.lesson_selected.emit(
                            lid
                        )
                    )

                unit_layout.addWidget(lesson_button)

            unit_groupbox.setLayout(unit_layout)
            self.units_layout.addWidget(unit_groupbox)

        self.xp_label.setText(f"Total XP: {self.progress_manager.get_total_xp()}")

    def refresh_view(self):
        self.populate_units()
