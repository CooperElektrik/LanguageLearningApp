# application/tools/widgets/problems_drawer.py

import logging
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QIcon
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from application.tools.course_validator import ValidationIssue

logger = logging.getLogger(__name__)


class ProblemsDrawer(QWidget):
    """
    Bottom collapsible IDE-style Problems and Validation drawer.
    Displays course errors and warnings, and allows jumping directly
    to the erroneous tree node and field on click.
    """

    issue_selected = Signal(object)  # Emits ValidationIssue or dict
    validate_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ProblemsDrawer")
        self._is_collapsed = False
        self._all_issues: list[ValidationIssue] = []

        self._setup_ui()

    def _setup_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(6, 6, 6, 6)
        self.main_layout.setSpacing(4)

        # Header bar
        header_layout = QHBoxLayout()

        self.title_label = QLabel("<b>Problems & Validation</b>")
        header_layout.addWidget(self.title_label)

        self.badge_label = QLabel("0 issues")
        self.badge_label.setStyleSheet(
            "background-color: #2e2e3b; color: #a0a0b2; border-radius: 10px; padding: 2px 8px; font-size: 11px;"
        )
        header_layout.addWidget(self.badge_label)

        header_layout.addStretch(1)

        self.validate_button = QPushButton("Validate Now")
        self.validate_button.setToolTip("Run course validation check")
        self.validate_button.clicked.connect(self.validate_requested.emit)
        header_layout.addWidget(self.validate_button)

        self.toggle_collapse_button = QPushButton("▲")
        self.toggle_collapse_button.setFixedWidth(28)
        self.toggle_collapse_button.setToolTip("Collapse / Expand Problems Drawer")
        self.toggle_collapse_button.clicked.connect(self.toggle_collapse)
        header_layout.addWidget(self.toggle_collapse_button)

        self.main_layout.addLayout(header_layout)

        # Problems List
        self.issues_list = QListWidget()
        self.issues_list.setAlternatingRowColors(True)
        self.issues_list.itemClicked.connect(self._handle_item_clicked)
        self.issues_list.itemDoubleClicked.connect(self._handle_item_clicked)
        self.main_layout.addWidget(self.issues_list)

        self.setMaximumHeight(220)

    def toggle_collapse(self):
        self._is_collapsed = not self._is_collapsed
        self.issues_list.setVisible(not self._is_collapsed)
        self.toggle_collapse_button.setText("▼" if self._is_collapsed else "▲")
        if self._is_collapsed:
            self.setMaximumHeight(38)
        else:
            self.setMaximumHeight(220)

    def set_issues(self, issues: list[Any]):
        """Populates the problems drawer with validation issues."""
        self._all_issues = issues
        self.issues_list.clear()

        error_count = 0
        warning_count = 0

        for issue in issues:
            severity = getattr(issue, "severity", "error")
            if "Warning:" in str(issue):
                severity = "warning"

            if severity == "warning":
                warning_count += 1
            else:
                error_count += 1

            item = QListWidgetItem()
            item.setData(Qt.UserRole, issue)

            prefix_icon = (
                self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxWarning)
                if severity == "warning"
                else self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxCritical)
            )
            item.setIcon(prefix_icon)
            item.setText(str(issue))
            item.setToolTip(str(issue))

            if severity == "warning":
                item.setForeground(QColor("#f39c12"))
            else:
                item.setForeground(QColor("#e74c3c"))

            self.issues_list.addItem(item)

        total = error_count + warning_count
        if total == 0:
            self.badge_label.setText("✓ No issues found")
            self.badge_label.setStyleSheet(
                "background-color: #27ae60; color: white; border-radius: 10px; padding: 2px 8px; font-size: 11px; font-weight: bold;"
            )
        else:
            self.badge_label.setText(f"{error_count} Errors, {warning_count} Warnings")
            color = "#c0392b" if error_count > 0 else "#d35400"
            self.badge_label.setStyleSheet(
                f"background-color: {color}; color: white; border-radius: 10px; padding: 2px 8px; font-size: 11px; font-weight: bold;"
            )

        if self._is_collapsed and total > 0:
            self.toggle_collapse()

    def _handle_item_clicked(self, item: QListWidgetItem):
        issue = item.data(Qt.UserRole)
        if issue is not None:
            self.issue_selected.emit(issue)
