import os
import logging
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea,
    QFrame, QGroupBox, QGridLayout, QSizePolicy
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QPixmap, QIcon, QPainter

logger = logging.getLogger(__name__)


class ProgressView(QWidget):
    back_to_overview_signal = Signal()

    def __init__(self, course_manager, progress_manager, parent=None):
        super().__init__(parent)
        self.course_manager = course_manager
        self.progress_manager = progress_manager

        self._setup_ui()
        self.refresh_view() # Load initial data

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)

        # Top Bar with Back Button
        top_bar_layout = QHBoxLayout()
        self.back_button = QPushButton("← Back to Course Overview")
        self.back_button.clicked.connect(self.back_to_overview_signal.emit)
        top_bar_layout.addWidget(self.back_button)
        top_bar_layout.addStretch(1) # Pushes button to left
        main_layout.addLayout(top_bar_layout)

        # Title
        title_label = QLabel("Your Progress")
        title_label.setFont(QFont("Arial", 20, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title_label)

        # Scroll Area for Content
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_content_widget = QWidget()
        self.scroll_content_layout = QVBoxLayout(self.scroll_content_widget)
        self.scroll_content_layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        self.scroll_area.setWidget(self.scroll_content_widget)
        main_layout.addWidget(self.scroll_area)


        # XP Section
        xp_group = QGroupBox("Total Experience (XP)")
        xp_group.setFont(QFont("Arial", 14, QFont.DemiBold))
        xp_layout = QVBoxLayout(xp_group)
        self.xp_value_label = QLabel("0 XP")
        self.xp_value_label.setFont(QFont("Arial", 24, QFont.Bold))
        self.xp_value_label.setAlignment(Qt.AlignCenter)
        xp_layout.addWidget(self.xp_value_label)
        self.scroll_content_layout.addWidget(xp_group)

        # Streak Section
        streak_group = QGroupBox("Study Streak")
        streak_group.setFont(QFont("Arial", 14, QFont.DemiBold))
        streak_layout = QVBoxLayout(streak_group)
        self.streak_value_label = QLabel("0 Days")
        self.streak_value_label.setFont(QFont("Arial", 24, QFont.Bold))
        self.streak_value_label.setAlignment(Qt.AlignCenter)
        self.streak_description_label = QLabel("Keep up the consistent work!")
        self.streak_description_label.setFont(QFont("Arial", 10))
        self.streak_description_label.setAlignment(Qt.AlignCenter)
        streak_layout.addWidget(self.streak_value_label)
        streak_layout.addWidget(self.streak_description_label)
        self.scroll_content_layout.addWidget(streak_group)


        # Achievements Section (Placeholder)
        achievements_group = QGroupBox("Achievements")
        achievements_group.setFont(QFont("Arial", 14, QFont.DemiBold))
        self.achievements_grid_layout = QGridLayout(achievements_group)
        self.achievements_grid_layout.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        
        # Add some placeholder achievements
        self._add_achievement_placeholder("First Step", "Complete your first lesson.", lambda: self.progress_manager.get_total_xp() >= 10, "trophy_bronze.png")
        self._add_achievement_placeholder("XP Enthusiast", "Reach 1000 XP.", lambda: self.progress_manager.get_total_xp() >= 1000, "star_silver.png")
        self._add_achievement_placeholder("7-Day Streak", "Study for 7 consecutive days.", lambda: self.progress_manager.get_current_streak() >= 7, "streak_gold.png")
        # Add more as needed
        
        self.scroll_content_layout.addWidget(achievements_group)
        self.scroll_content_layout.addStretch(1) # Pushes content to top


    def _add_achievement_placeholder(self, title: str, description: str, is_unlocked_func, icon_filename: str):
        """Helper to add a conceptual achievement to the grid."""
        # Check if the achievement is unlocked
        is_unlocked = is_unlocked_func()
        
        # Create a frame for each achievement
        achievement_frame = QFrame()
        achievement_frame.setFrameShape(QFrame.StyledPanel)
        achievement_frame.setFrameShadow(QFrame.Raised)
        achievement_layout = QVBoxLayout(achievement_frame)
        achievement_layout.setAlignment(Qt.AlignCenter)
        
        # Icon (conceptual, assumes local path for now or would need a pixmap cache)
        icon_path = os.path.join(os.path.dirname(__file__), "..", "..", "assets", "icons", icon_filename)
        # Note: 'assets/icons' might need to be created and relevant icons placed there for this to work
        # For now, if icon not found, it will just show empty icon or a default.
        
        icon_label = QLabel()
        pixmap = QPixmap(icon_path)
        if pixmap.isNull():
            # Fallback to a default icon or a generic one if image not found
            pixmap = self.style().standardIcon(self.style().StandardPixmap.SP_DialogNoButton).pixmap(64, 64)
            logger.warning(f"Achievement icon not found: {icon_path}. Using default.")
        
        if not is_unlocked:
            # Apply grayscale effect to pixmap if locked
            if not pixmap.isNull():
                grayscale_pixmap = QPixmap(pixmap.size())
                grayscale_pixmap.fill(Qt.transparent)
                painter = QPainter(grayscale_pixmap)
                painter.setOpacity(0.3) # Dim it
                painter.drawPixmap(0, 0, pixmap)
                painter.end()
                pixmap = grayscale_pixmap

        icon_label.setPixmap(pixmap)
        achievement_layout.addWidget(icon_label, alignment=Qt.AlignCenter)
        
        # Title
        title_label = QLabel(title)
        title_label.setFont(QFont("Arial", 12, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        achievement_layout.addWidget(title_label, alignment=Qt.AlignCenter)

        # Description
        desc_label = QLabel(description)
        desc_label.setFont(QFont("Arial", 9))
        desc_label.setAlignment(Qt.AlignCenter)
        desc_label.setWordWrap(True)
        achievement_layout.addWidget(desc_label, alignment=Qt.AlignCenter)

        # Add to grid layout
        row = self.achievements_grid_layout.count() // 3 # 3 columns per row
        col = self.achievements_grid_layout.count() % 3
        self.achievements_grid_layout.addWidget(achievement_frame, row, col)

    def refresh_view(self):
        self.xp_value_label.setText(f"{self.progress_manager.get_total_xp()} XP")
        
        current_streak = self.progress_manager.get_current_streak()
        self.streak_value_label.setText(f"{current_streak} Days")
        if current_streak > 0:
            self.streak_value_label.setStyleSheet("color: #FFD700;") # Gold
            self.streak_description_label.setText("Keep up the consistent work!")
        else:
            self.streak_value_label.setStyleSheet("color: gray;")
            self.streak_description_label.setText("Start a new streak today!")

        # Re-populate achievements to update their unlocked status
        # Clear existing achievements before re-adding
        for i in reversed(range(self.achievements_grid_layout.count())): 
            widget = self.achievements_grid_layout.itemAt(i).widget()
            if widget: widget.deleteLater()

        # Re-add achievements (adjust arguments as per _add_achievement_placeholder)
        self._add_achievement_placeholder("First Step", "Complete your first lesson.", lambda: self.progress_manager.get_total_xp() >= 10, "trophy_bronze.png")
        self._add_achievement_placeholder("XP Enthusiast", "Reach 1000 XP.", lambda: self.progress_manager.get_total_xp() >= 1000, "star_silver.png")
        self._add_achievement_placeholder("7-Day Streak", "Study for 7 consecutive days.", lambda: self.progress_manager.get_current_streak() >= 7, "streak_gold.png")
        # Ensure that any new achievements added to _add_achievement_placeholder are also added here for refresh.