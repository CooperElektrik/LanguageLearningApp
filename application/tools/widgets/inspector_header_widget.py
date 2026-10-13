# application/tools/widgets/inspector_header_widget.py

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)


class InspectorHeaderWidget(QWidget):
    """
    Reusable Inspector banner displaying:
    - Entity Type Badge (e.g., [UNIT], [LESSON], [EXERCISE])
    - Dynamic Breadcrumb Trail (e.g., Course > Unit 1 > Lesson 2)
    - Prominent Entity Title (13-14pt bold typographic hierarchy)
    - Persistent Status Indicator (Saved, Unsaved Changes*, Issue)
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("InspectorHeader")
        self._setup_ui()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 8)
        main_layout.setSpacing(6)

        # Top Bar: Badge, Breadcrumbs, Status Indicator
        top_bar_layout = QHBoxLayout()
        top_bar_layout.setContentsMargins(0, 0, 0, 0)
        top_bar_layout.setSpacing(8)

        self.badge_label = QLabel("[ITEM]")
        self.badge_label.setObjectName("InspectorBadge")
        self.badge_label.setProperty("isBadge", True)
        self.badge_label.setAlignment(Qt.AlignCenter)

        self.breadcrumb_label = QLabel("Course")
        self.breadcrumb_label.setObjectName("InspectorBreadcrumbs")
        self.breadcrumb_label.setWordWrap(True)

        self.status_label = QLabel("Saved")
        self.status_label.setObjectName("InspectorStatus")
        self.status_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        top_bar_layout.addWidget(self.badge_label)
        top_bar_layout.addWidget(self.breadcrumb_label, 1)
        top_bar_layout.addWidget(self.status_label)
        main_layout.addLayout(top_bar_layout)

        # Bottom Bar: Prominent Entity Title
        self.title_label = QLabel("Details")
        self.title_label.setObjectName("InspectorTitle")
        main_layout.addWidget(self.title_label)

        # Bottom Divider
        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        divider.setFrameShadow(QFrame.Plain)
        divider.setObjectName("InspectorDivider")
        main_layout.addWidget(divider)

    def set_context(
        self,
        entity_type: str,
        breadcrumb_parts: list[str] | None = None,
        title: str = "",
        status: str = "Saved",
        is_dirty: bool = False,
        has_error: bool = False,
    ):
        """Updates the inspector header context."""
        badge_text = entity_type.upper()
        if not badge_text.startswith("["):
            badge_text = f"[{badge_text}]"
        self.badge_label.setText(badge_text)

        # Update breadcrumbs
        parts = breadcrumb_parts or ["Course"]
        self.breadcrumb_label.setText(" › ".join(parts))

        # Update title
        self.title_label.setText(title or "Inspector & Details")

        # Update status
        if has_error:
            self.status_label.setText("● Validation Issue")
            self.status_label.setStyleSheet("color: #e74c3c; font-weight: 600; font-size: 9pt;")
        elif is_dirty:
            self.status_label.setText("● Unsaved Changes*")
            self.status_label.setStyleSheet("color: #f39c12; font-weight: 600; font-size: 9pt;")
        else:
            self.status_label.setText("● " + status)
            self.status_label.setStyleSheet("color: #27ae60; font-weight: 600; font-size: 9pt;")
