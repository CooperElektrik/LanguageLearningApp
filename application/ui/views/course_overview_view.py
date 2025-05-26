from PySide6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QPushButton, QScrollArea, 
                               QFrame, QGroupBox, QHBoxLayout)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QFont, QIcon # For icons if desired

from core.models import Unit, Lesson # Assuming core is accessible

class CourseOverviewView(QWidget):
    lesson_selected = Signal(str)  # Emits lesson_id

    def __init__(self, course_manager, progress_manager, parent=None):
        super().__init__(parent)
        self.course_manager = course_manager
        self.progress_manager = progress_manager
        
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        title_label = QLabel(self.course_manager.get_course_title() or "Language Course")
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
        # Clear existing widgets first
        while self.units_layout.count():
            child = self.units_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        units = self.course_manager.get_units()
        all_course_units_for_unlock_check = self.course_manager.get_units() # For unlock logic

        for unit in units:
            unit_groupbox = QGroupBox(unit.title)
            unit_groupbox.setFont(QFont("Arial", 14, QFont.DemiBold))
            unit_layout = QVBoxLayout()

            for lesson in unit.lessons:
                lesson_button_text = f"{lesson.title}"
                is_completed = self.progress_manager.is_lesson_completed(lesson.lesson_id)
                # Pass current unit's lessons and all units for accurate unlocking check
                current_unit_lessons = unit.lessons 
                is_unlocked = self.progress_manager.is_lesson_unlocked(lesson.lesson_id, current_unit_lessons, all_course_units_for_unlock_check)

                lesson_button = QPushButton()
                lesson_button.setFont(QFont("Arial", 11))
                lesson_button.setMinimumHeight(40)

                status_indicator = ""
                button_style = "QPushButton { text-align: left; padding: 5px; }"
                
                if is_completed:
                    status_indicator = "✓ " # Checkmark for completed
                    lesson_button_text = f"{status_indicator}{lesson.title}"
                    button_style += "QPushButton { background-color: #d4edda; color: #155724; border: 1px solid #c3e6cb; }"
                    lesson_button.setProperty("status", "completed")
                elif is_unlocked:
                    status_indicator = "▶ " # Play icon for unlocked
                    lesson_button_text = f"{status_indicator}{lesson.title}"
                    button_style += "QPushButton { background-color: #e2e3e5; border: 1px solid #d6d8db; }"
                    lesson_button.setProperty("status", "unlocked")
                else:
                    status_indicator = "🔒 " # Lock icon for locked
                    lesson_button_text = f"{status_indicator}{lesson.title}"
                    lesson_button.setEnabled(False)
                    button_style += "QPushButton { background-color: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }"
                    lesson_button.setProperty("status", "locked")

                lesson_button.setText(lesson_button_text)
                lesson_button.setStyleSheet(button_style)
                
                if is_unlocked and not is_completed: # Only connect signal if lesson can be started
                    lesson_button.clicked.connect(lambda checked=False, lid=lesson.lesson_id: self.lesson_selected.emit(lid))
                elif is_completed: # Allow replaying completed lessons
                     lesson_button.clicked.connect(lambda checked=False, lid=lesson.lesson_id: self.lesson_selected.emit(lid))


                unit_layout.addWidget(lesson_button)
            
            unit_groupbox.setLayout(unit_layout)
            self.units_layout.addWidget(unit_groupbox)
            
        self.xp_label.setText(f"Total XP: {self.progress_manager.get_total_xp()}")


    def refresh_view(self):
        """Called when returning to this view to update lesson statuses."""
        self.populate_units()