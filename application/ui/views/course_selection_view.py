import os
import yaml
import logging
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QScrollArea
from PySide6.QtCore import Signal, Qt, QEvent

import settings
import utils

logger = logging.getLogger(__name__)

class CourseSelectionView(QWidget):
    course_selected = Signal(str)  # Emits the absolute path to the course's manifest.yaml

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("course_selection_view")
        self._setup_ui()
        self._find_and_display_courses()

    def _setup_ui(self): # Renamed to self.title_label
        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)

        self.title_label = QLabel(self.tr("Select a Course"))
        self.title_label.setObjectName("course_selection_title_label")
        main_layout.addWidget(self.title_label)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        main_layout.addWidget(scroll_area)
        
        self.scroll_content = QWidget()
        self.courses_layout = QVBoxLayout(self.scroll_content)
        self.courses_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll_area.setWidget(self.scroll_content)

    def _find_and_display_courses(self):
        courses_dir_abs = utils.get_resource_path(settings.COURSES_DIR)
        if not os.path.isdir(courses_dir_abs):
            logger.error(f"Courses directory not found at: {courses_dir_abs}")
            self.courses_layout.addWidget(QLabel(self.tr("Error: Courses directory not found.")))
            return

        found_courses = False
        for course_dir_name in os.listdir(courses_dir_abs):
            course_path = os.path.join(courses_dir_abs, course_dir_name)
            manifest_path = os.path.join(course_path, settings.MANIFEST_FILENAME)
            
            if os.path.isfile(manifest_path):
                try:
                    with open(manifest_path, 'r', encoding='utf-8') as f:
                        manifest_data = yaml.safe_load(f)
                        course_title = manifest_data.get("course_title", course_dir_name)
                        
                        button = QPushButton(course_title)
                        button.setObjectName("course_select_button")
                        button.clicked.connect(lambda checked=False, p=manifest_path: self.course_selected.emit(p))
                        self.courses_layout.addWidget(button)
                        found_courses = True
                except Exception as e:
                    logger.warning(f"Could not load or parse manifest for course '{course_dir_name}': {e}")
        
        if not found_courses:
            self.courses_layout.addWidget(QLabel(self.tr("No valid courses found in the courses directory.")))

    def changeEvent(self, event: QEvent):
        if event.type() == QEvent.Type.LanguageChange:
            self.retranslateUi()
        super().changeEvent(event)

    def retranslateUi(self):
        self.title_label.setText(self.tr("Select a Course"))
        # Course buttons are created dynamically with titles from manifest, so they don't need retranslation here.
        # The "No valid courses" or "Error" labels are also dynamic.
        logger.debug("CourseSelectionView retranslated.")