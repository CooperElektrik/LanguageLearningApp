import logging
import os

import utils
from core.course_manager import CourseManager  # For type hinting
from core.progress_manager import ProgressManager  # For type hinting
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QGroupBox,
    QLabel,
    QProgressBar,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

try:
    from application.ui.widgets.achievement_card_widget import AchievementCardWidget
except ImportError:
    from ui.widgets.achievement_card_widget import AchievementCardWidget

logger = logging.getLogger(__name__)


class ProgressView(QWidget):
    # back_to_overview_signal is no longer needed as this view is embedded.

    def __init__(
        self,
        course_manager: CourseManager,
        progress_manager: ProgressManager,
        parent=None,
    ):
        super().__init__(parent)
        self.course_manager = course_manager
        self.progress_manager = progress_manager

        self._setup_ui()
        self.refresh_view()  # Load initial data

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setObjectName("progress_view_main_layout")
        main_layout.setContentsMargins(0, 0, 0, 0)  # Make it more compact for embedding

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
        self.scroll_content_layout.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter
        )
        self.scroll_area.setWidget(self.scroll_content_widget)
        main_layout.addWidget(self.scroll_area)

        # XP Section
        xp_group = QGroupBox(self.tr("Total Experience (XP)"))
        xp_group.setObjectName("xp_groupbox")
        xp_layout = QVBoxLayout(xp_group)

        self.xp_value_label = QLabel()  # Text set in refresh_view
        self.xp_value_label.setObjectName("xp_value_label")
        self.xp_value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        xp_layout.addWidget(self.xp_value_label)
        self.scroll_content_layout.addWidget(xp_group)

        # Streak Section
        self.streak_group = QGroupBox(self.tr("Study Streak"))
        self.streak_group.setObjectName("streak_groupbox")
        streak_layout = QVBoxLayout(self.streak_group)

        self.streak_value_label = QLabel()  # Text set in refresh_view
        self.streak_value_label.setObjectName("streak_value_label")
        self.streak_value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.streak_description_label = QLabel()  # Text set in refresh_view
        self.streak_description_label.setObjectName("streak_description_label")
        self.streak_description_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        streak_layout.addWidget(self.streak_value_label)
        streak_layout.addWidget(self.streak_description_label)
        self.scroll_content_layout.addWidget(self.streak_group)

        # Retention & Mastery Section (SM-2)
        self.retention_group = QGroupBox(self.tr("Memory Retention & Mastery (SM-2)"))
        self.retention_group.setObjectName("retention_groupbox")
        retention_layout = QVBoxLayout(self.retention_group)

        self.retention_gauge = QProgressBar()
        self.retention_gauge.setObjectName("retention_gauge")
        self.retention_gauge.setRange(0, 100)
        self.retention_gauge.setValue(0)
        self.retention_gauge.setTextVisible(True)
        self.retention_gauge.setFormat("%v% Estimated Retention")
        retention_layout.addWidget(self.retention_gauge)

        self.retention_desc_label = QLabel()
        self.retention_desc_label.setObjectName("retention_desc_label")
        self.retention_desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        retention_layout.addWidget(self.retention_desc_label)

        self.retention_breakdown_label = QLabel()
        self.retention_breakdown_label.setObjectName("retention_breakdown_label")
        self.retention_breakdown_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        retention_layout.addWidget(self.retention_breakdown_label)

        self.scroll_content_layout.addWidget(self.retention_group)

        # Achievements Section
        self.achievements_group = QGroupBox(self.tr("Achievements"))
        self.achievements_group.setObjectName("achievements_groupbox")
        self.achievements_grid_layout = QGridLayout(self.achievements_group)
        self.achievements_grid_layout.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        )

        self.scroll_content_layout.addWidget(self.achievements_group)
        self.scroll_content_layout.addStretch(1)  # Pushes content to top

    def _clear_grid_layout(self, layout: QGridLayout):
        """Helper to remove all widgets from a QGridLayout."""
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def _add_achievement(self, title: str, description: str, is_unlocked: bool, icon_filename: str):
        """Adds a single achievement display to the grid layout."""
        card = AchievementCardWidget(
            title=title,
            description=description,
            is_unlocked=is_unlocked,
            icon_filename=icon_filename,
            parent=self.achievements_group,
        )

        row = self.achievements_grid_layout.count() // 3  # 3 columns per row
        col = self.achievements_grid_layout.count() % 3
        self.achievements_grid_layout.addWidget(card, row, col)

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

        # Retention & Mastery Stats
        all_exercises = self.course_manager.get_all_exercises() if self.course_manager else []
        retention_stats = self.progress_manager.get_retention_stats(all_exercises)
        avg_retention = retention_stats["average_retention"]
        self.retention_gauge.setValue(int(avg_retention))
        self.retention_desc_label.setText(
            self.tr("Estimated Memory Retention: {0}%").format(avg_retention)
        )
        learning_count = max(
            0, retention_stats["learned_count"] - retention_stats["mastered_count"]
        )
        self.retention_breakdown_label.setText(
            self.tr("Mastered: {0}  |  Learning: {1}  |  Due for Review: {2}").format(
                retention_stats["mastered_count"], learning_count, retention_stats["due_count"]
            )
        )

        # Clear existing achievements before re-adding
        self._clear_grid_layout(self.achievements_grid_layout)

        # Re-add achievements based on current progress from ProgressManager
        achievements = self.progress_manager.get_achievements(self.course_manager)
        for ach in achievements:
            self._add_achievement(
                self.tr(ach.title),
                self.tr(ach.description),
                ach.is_unlocked,
                ach.icon,
            )
