import os
import logging
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea,
    QFrame, QGroupBox, QGridLayout, QStyle
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap, QPainter

import utils

from core.course_manager import CourseManager # For type hinting
from core.progress_manager import ProgressManager # For type hinting

logger = logging.getLogger(__name__)


class ProgressView(QWidget):
    # back_to_overview_signal is no longer needed as this view is embedded.

    def __init__(self, course_manager: CourseManager, progress_manager: ProgressManager, parent=None):
        super().__init__(parent)
        self.course_manager = course_manager
        self.progress_manager = progress_manager

        self._setup_ui()
        self.refresh_view() # Load initial data

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setObjectName("progress_view_main_layout")
        main_layout.setContentsMargins(0, 0, 0, 0) # Make it more compact for embedding

        # Top Bar and Title have been removed as this view is now embedded.

        # Scroll Area for Content
        self.scroll_area = QScrollArea()
        self.scroll_area.setObjectName("progress_scroll_area")
        self.scroll_area.setWidgetResizable(True)
        # Set a minimum height to ensure it doesn't collapse entirely
        self.scroll_area.setMinimumHeight(200)
        
        self.scroll_content_widget = QWidget()
        self.scroll_content_widget.setObjectName("progress_scroll_content_widget")
        self.scroll_content_layout = QVBoxLayout(self.scroll_content_widget)
        self.scroll_content_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        self.scroll_area.setWidget(self.scroll_content_widget)
        main_layout.addWidget(self.scroll_area)


        # XP Section
        xp_group = QGroupBox(self.tr("Total Experience (XP)"))
        xp_group.setObjectName("xp_groupbox")
        xp_layout = QVBoxLayout(xp_group)
        
        self.xp_value_label = QLabel() # Text set in refresh_view
        self.xp_value_label.setObjectName("xp_value_label")
        self.xp_value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        xp_layout.addWidget(self.xp_value_label)
        self.scroll_content_layout.addWidget(xp_group)

        # Streak Section
        self.streak_group = QGroupBox(self.tr("Study Streak"))
        self.streak_group.setObjectName("streak_groupbox")
        streak_layout = QVBoxLayout(self.streak_group)
        
        self.streak_value_label = QLabel() # Text set in refresh_view
        self.streak_value_label.setObjectName("streak_value_label")
        self.streak_value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.streak_description_label = QLabel() # Text set in refresh_view
        self.streak_description_label.setObjectName("streak_description_label")
        self.streak_description_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        streak_layout.addWidget(self.streak_value_label)
        streak_layout.addWidget(self.streak_description_label)
        self.scroll_content_layout.addWidget(self.streak_group)


        # Achievements Section
        self.achievements_group = QGroupBox(self.tr("Achievements"))
        self.achievements_group.setObjectName("achievements_groupbox")
        self.achievements_grid_layout = QGridLayout(self.achievements_group)
        self.achievements_grid_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        
        # Add achievements definitions
        self._ACHIEVEMENTS = [
            {"id": "first_step", "title": self.tr("First Step"), "description": self.tr("Complete your first lesson."), 
             "check": lambda: self.progress_manager.get_total_xp() >= 10, "icon": "trophy_bronze.png"},
            {"id": "xp_enthusiast", "title": self.tr("XP Enthusiast"), "description": self.tr("Reach 1000 XP."), 
             "check": lambda: self.progress_manager.get_total_xp() >= 1000, "icon": "star_silver.png"},
            {"id": "7_day_streak", "title": self.tr("7-Day Streak"), "description": self.tr("Study for 7 consecutive days."), 
             "check": lambda: self.progress_manager.get_current_streak() >= 7, "icon": "streak_gold.png"},
            {"id": "30_day_streak", "title": self.tr("30-Day Streak"), "description": self.tr("Study for 30 consecutive days."), 
             "check": lambda: self.progress_manager.get_current_streak() >= 30, "icon": "streak_platinum.png"},
            {"id": "all_lessons_completed", "title": self.tr("Lesson Master"), "description": self.tr("Complete all lessons in the course."),
             "check": self._check_all_lessons_completed, "icon": "lessons_complete.png"},
        ]
        
        self.scroll_content_layout.addWidget(self.achievements_group)
        self.scroll_content_layout.addStretch(1) # Pushes content to top


    def _check_all_lessons_completed(self) -> bool:
        """Checks if all lessons in the course are completed."""
        if not self.course_manager.course:
            return False
        all_lessons = [lesson for unit in self.course_manager.get_units() for lesson in unit.lessons]
        if not all_lessons:
            return False
        
        for lesson in all_lessons:
            if not self.progress_manager.is_lesson_completed(lesson.lesson_id, self.course_manager):
                return False
        return True


    def _clear_grid_layout(self, layout: QGridLayout):
        """Helper to remove all widgets from a QGridLayout."""
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()


    def _add_achievement(self, title: str, description: str, is_unlocked: bool, icon_filename: str):
        """Adds a single achievement display to the grid layout."""
        
        achievement_frame = QFrame()
        achievement_frame.setObjectName("achievement_frame")
        achievement_frame.setFrameShape(QFrame.Shape.StyledPanel)
        achievement_frame.setFrameShadow(QFrame.Shadow.Raised)
        
        achievement_frame.setProperty("unlocked", is_unlocked)
        
        achievement_layout = QVBoxLayout(achievement_frame)
        achievement_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        icon_label = QLabel()
        icon_label.setObjectName("achievement_icon_label")
        
        # icons are in 'application/assets/icons/'
        icon_relative_path = os.path.join("assets", "icons", icon_filename)
        icon_path = utils.get_resource_path(icon_relative_path)
        
        pixmap = QPixmap(icon_path)
        if pixmap.isNull():
            pixmap = self.style().standardIcon(QStyle.StandardPixmap.SP_DialogNoButton).pixmap(64, 64)
            logger.warning(f"Achievement icon not found: {icon_path}. Using default icon.")
        
        # Apply grayscale effect if locked
        if not is_unlocked:
            grayscale_pixmap = QPixmap(pixmap.size())
            grayscale_pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(grayscale_pixmap)
            painter.setOpacity(0.3)
            painter.drawPixmap(0, 0, pixmap)
            painter.end()
            pixmap = grayscale_pixmap

        icon_label.setPixmap(pixmap)
        achievement_layout.addWidget(icon_label, stretch=1, alignment=(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignCenter))
        
        title_label = QLabel(title)
        title_label.setObjectName("achievement_title_label")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        achievement_layout.addWidget(title_label, stretch=1, alignment=Qt.AlignmentFlag.AlignCenter)

        desc_label = QLabel(description)
        desc_label.setObjectName("achievement_description_label")
        desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc_label.setWordWrap(True)
        achievement_layout.addWidget(desc_label, stretch=1, alignment=Qt.AlignmentFlag.AlignCenter)

        row = self.achievements_grid_layout.count() // 3 # 3 columns per row
        col = self.achievements_grid_layout.count() % 3
        self.achievements_grid_layout.addWidget(achievement_frame, row, col)


    def refresh_view(self):
        """Refreshes all dynamic content in the progress view."""
        self.xp_value_label.setText(self.tr("{0} XP").format(self.progress_manager.get_total_xp()))
        
        current_streak = self.progress_manager.get_current_streak()
        self.streak_value_label.setText(self.tr("{0} Days").format(current_streak))
        
        if current_streak > 0:
            self.streak_value_label.setProperty("active_streak", True)
            self.streak_description_label.setText(self.tr("Keep up the consistent work!"))
        else:
            self.streak_value_label.setProperty("active_streak", False)
            self.streak_description_label.setText(self.tr("Start a new streak today!"))

        # Clear existing achievements before re-adding
        self._clear_grid_layout(self.achievements_grid_layout)

        # Re-add achievements based on current progress
        for achievement_data in self._ACHIEVEMENTS:
            is_unlocked = achievement_data["check"]() # Execute the lambda function
            self._add_achievement(
                achievement_data["title"],
                achievement_data["description"],
                is_unlocked,
                achievement_data["icon"]
            )