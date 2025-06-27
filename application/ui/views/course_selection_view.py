import os
import yaml
import logging
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QFrame,
    QWidget
)
from PySide6.QtGui import QPixmap, QImage
from PySide6.QtCore import Signal, Qt, QEvent

import settings
import utils

logger = logging.getLogger(__name__)


class CourseButton(QPushButton):
    def __init__(
        self,
        course_title,
        course_description,
        author,
        version,
        source_language,
        target_language,
        image_path=None,
        manifest_path=None,
    ):
        super().__init__()
        self.manifest_path = manifest_path
        self.setObjectName("course_select_button")

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(20)

        # Image on the left
        if image_path:
            pixmap = QPixmap(image_path)
            image_label = QLabel()
            image_label.setPixmap(
                pixmap.scaled(
                    150, 150, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
                )
            )
            main_layout.addWidget(image_label, alignment=Qt.AlignmentFlag.AlignVCenter)

        # Text section in the middle
        text_layout = QVBoxLayout()
        text_layout.setSpacing(5)
        text_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        title_label = QLabel(course_title)
        title_label.setObjectName("course_button_title_label")
        text_layout.addWidget(title_label)

        if course_description:
            description_label = QLabel(course_description)
            description_label.setObjectName("course_button_description_label")
            description_label.setWordWrap(True)
            text_layout.addWidget(description_label)

        # Metadata section in a container to control its minimum width
        main_layout.addLayout(text_layout, 1)  # Add stretch factor

        # Right panel to hold the separator and metadata text, ensuring fixed width for alignment
        right_panel_widget = QWidget()
        right_panel_layout = QHBoxLayout(right_panel_widget)
        right_panel_layout.setContentsMargins(0, 0, 0, 0)  # No internal margins for the panel itself
        right_panel_layout.setSpacing(10)  # Space between separator and metadata text block

        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.VLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        right_panel_layout.addWidget(separator)

        # Metadata text layout (this will contain the actual metadata labels)
        metadata_text_layout = QVBoxLayout()
        metadata_text_layout.setSpacing(5)
        # Align items within this layout to the top-left (VCenter for vertical, AlignLeft for horizontal)
        metadata_text_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)

        if author:
            author_label = QLabel(f"<b>{self.tr('Author')}:</b> {author}")
            author_label.setObjectName("course_button_metadata_label")
            metadata_text_layout.addWidget(author_label)

        if version:
            version_label = QLabel(f"<b>{self.tr('Version')}:</b> {version}")
            version_label.setObjectName("course_button_metadata_label")
            metadata_text_layout.addWidget(version_label)

        if source_language and target_language:
            language_label = QLabel(f"<b>{self.tr('Language')}:</b> {source_language} → {target_language}")
            language_label.setObjectName("course_button_metadata_label")
            metadata_text_layout.addWidget(language_label)

        right_panel_layout.addLayout(metadata_text_layout) # Add labels layout to the right panel
        # Set a fixed width for the entire right panel to ensure consistent alignment across buttons.
        # This value may need adjustment based on font, language, and content length.
        right_panel_widget.setFixedWidth(260)
        main_layout.addWidget(right_panel_widget, 0)  # Add panel to main layout, no stretch factor

        self.setLayout(main_layout)


class CourseSelectionView(QWidget):
    course_selected = Signal(
        str
    )  # Emits the absolute path to the course's manifest.yaml

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("course_selection_view")
        self._setup_ui()
        self._find_and_display_courses()

    def _setup_ui(self):  # Renamed to self.title_label
        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter
        )

        self.title_label = QLabel(self.tr("Select a Course"))
        self.title_label.setObjectName("course_selection_title_label")
        main_layout.addWidget(self.title_label)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        main_layout.addWidget(scroll_area)

        self.scroll_content = QWidget()
        self.scroll_content.setObjectName("course_selection_scroll_content")
        self.courses_layout = QVBoxLayout(self.scroll_content)
        self.courses_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll_area.setWidget(self.scroll_content)

    def _find_and_display_courses(self):
        courses_dir_abs = utils.get_resource_path(settings.COURSES_DIR)
        if not os.path.isdir(courses_dir_abs):
            logger.error(f"Courses directory not found at: {courses_dir_abs}")
            self.courses_layout.addWidget(
                QLabel(self.tr("Error: Courses directory not found."))
            )
            return

        found_courses = False
        for course_dir_name in os.listdir(courses_dir_abs):
            course_path = os.path.join(courses_dir_abs, course_dir_name)
            manifest_path = os.path.join(course_path, settings.MANIFEST_FILENAME)

            if os.path.isfile(manifest_path):
                try:
                    with open(manifest_path, "r", encoding="utf-8") as f:
                        manifest_data = yaml.safe_load(f)
                        course_title = manifest_data.get(
                            "course_title", course_dir_name
                        )
                        course_description = manifest_data.get("description", "")
                        author = manifest_data.get("author", "")
                        version = manifest_data.get("version", "")
                        source_language = manifest_data.get("source_language", "")
                        target_language = manifest_data.get("target_language", "")
                        image_file = manifest_data.get("image_file")
                        
                        image_path = None
                        if image_file:
                            potential_path = os.path.join(course_path, "images", image_file)
                        if os.path.exists(potential_path):
                            image_path = potential_path
                        else:
                            image_path = utils.get_resource_path(os.path.join("assets/images/default_preview.jpg"))

                        button = CourseButton(
                            course_title,
                            course_description,
                            author,
                            version,
                            source_language,
                            target_language,
                            image_path,
                            manifest_path,
                        )
                        button.clicked.connect(
                            lambda checked=False, p=manifest_path: self.course_selected.emit(
                                p
                            )
                        )
                        self.courses_layout.addWidget(button)
                        found_courses = True
                except Exception as e:
                    logger.warning(
                        f"Could not load or parse manifest for course '{course_dir_name}': {e}"
                    )

        if not found_courses:
            self.courses_layout.addWidget(
                QLabel(self.tr("No valid courses found in the courses directory."))
            )

    def changeEvent(self, event: QEvent):
        if event.type() == QEvent.Type.LanguageChange:
            self.retranslateUi()
        super().changeEvent(event)

    def retranslateUi(self):
        self.title_label.setText(self.tr("Select a Course"))
        # Course buttons are created dynamically with titles from manifest, so they don't need retranslation here.
        # The "No valid courses" or "Error" labels are also dynamic.
        logger.debug("CourseSelectionView retranslated.")
