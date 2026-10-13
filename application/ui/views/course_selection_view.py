import logging
import os

import settings
import utils
import yaml
from PySide6.QtCore import QEvent, QSize, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

try:
    from application.core.course_loader import import_course_package
except ImportError:
    from core.course_loader import import_course_package

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

            # Define a minimum width for the image
            MIN_IMAGE_WIDTH = 150

            # Scale the pixmap while maintaining aspect ratio
            scaled_pixmap = pixmap.scaled(
                QSize(MIN_IMAGE_WIDTH, 150),  # Use MIN_IMAGE_WIDTH as base for scaling
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )

            # Ensure the scaled pixmap's width is at least MIN_IMAGE_WIDTH
            if scaled_pixmap.width() < MIN_IMAGE_WIDTH:
                scaled_pixmap = pixmap.scaled(
                    QSize(
                        MIN_IMAGE_WIDTH,
                        int(pixmap.height() * (MIN_IMAGE_WIDTH / pixmap.width())),
                    ),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )

            image_label.setPixmap(scaled_pixmap)
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
        right_panel_layout.setContentsMargins(
            0, 0, 0, 0
        )  # No internal margins for the panel itself
        right_panel_layout.setSpacing(10)  # Space between separator and metadata text block

        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.VLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        right_panel_layout.addWidget(separator)

        # Metadata text layout (this will contain the actual metadata labels)
        metadata_text_layout = QVBoxLayout()
        metadata_text_layout.setSpacing(5)
        # Align items within this layout to the top-left (VCenter for vertical, AlignLeft for horizontal)
        metadata_text_layout.setAlignment(
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
        )

        if author:
            author_label = QLabel(f"<b>{self.tr('Author')}:</b> {author}")
            author_label.setObjectName("course_button_metadata_label")
            metadata_text_layout.addWidget(author_label)

        if version:
            version_label = QLabel(f"<b>{self.tr('Version')}:</b> {version}")
            version_label.setObjectName("course_button_metadata_label")
            metadata_text_layout.addWidget(version_label)

        if source_language and target_language:
            language_label = QLabel(
                f"<b>{self.tr('Language')}:</b> {source_language} → {target_language}"
            )
            language_label.setObjectName("course_button_metadata_label")
            metadata_text_layout.addWidget(language_label)

        right_panel_layout.addLayout(metadata_text_layout)  # Add labels layout to the right panel
        # Set a fixed width for the entire right panel to ensure consistent alignment across buttons.
        # This value may need adjustment based on font, language, and content length.
        right_panel_widget.setFixedWidth(260)
        main_layout.addWidget(right_panel_widget, 0)  # Add panel to main layout, no stretch factor

        self.setLayout(main_layout)

    def sizeHint(self) -> QSize:
        """Use the card layout's size, not QPushButton's text-based size.

        QPushButton computes its sizeHint from its own text/icon and ignores
        child layouts, so without this override the card is laid out at button
        height (~25px) and every child (image, title, metadata) is squeezed to
        zero height, rendering the card as an empty collapsed strip.
        """
        layout = self.layout()
        if layout is not None:
            return layout.totalSizeHint()
        return super().sizeHint()

    def minimumSizeHint(self) -> QSize:
        layout = self.layout()
        if layout is not None:
            return layout.totalMinimumSize()
        return super().minimumSizeHint()


class CourseSelectionView(QWidget):
    course_selected = Signal(str)  # Emits the absolute path to the course's manifest.yaml

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("course_selection_view")
        self._setup_ui()
        self._find_and_display_courses()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(10, 10, 10, 10)

        self.title_label = QLabel(self.tr("Select a Course"))
        self.title_label.setObjectName("course_selection_title_label")
        header_layout.addWidget(self.title_label)

        header_layout.addStretch()

        self.import_button = QPushButton(self.tr("Import Package (.lcpkg)..."))
        self.import_button.setObjectName("course_import_button")
        self.import_button.clicked.connect(self._on_import_course_clicked)
        header_layout.addWidget(self.import_button)

        self.refresh_button = QPushButton(self.tr("Refresh"))
        self.refresh_button.setObjectName("course_refresh_button")
        self.refresh_button.clicked.connect(self._find_and_display_courses)
        header_layout.addWidget(self.refresh_button)

        main_layout.addLayout(header_layout)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        main_layout.addWidget(scroll_area)

        self.scroll_content = QWidget()
        self.scroll_content.setObjectName("course_selection_scroll_content")
        self.courses_layout = QVBoxLayout(self.scroll_content)
        self.courses_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll_area.setWidget(self.scroll_content)

    def _clear_courses_layout(self):
        while self.courses_layout.count():
            item = self.courses_layout.takeAt(0)
            if item:
                widget = item.widget()
                if widget:
                    widget.deleteLater()

    def _find_and_display_courses(self):
        self._clear_courses_layout()

        search_dirs = utils.get_courses_search_directories()
        logger.info(f"Scanning for courses across directories: {search_dirs}")

        found_courses = False
        seen_course_ids = set()

        for courses_dir in search_dirs:
            if not os.path.isdir(courses_dir):
                continue

            for course_dir_name in sorted(os.listdir(courses_dir)):
                course_path = os.path.join(courses_dir, course_dir_name)
                if not os.path.isdir(course_path):
                    continue

                manifest_path = os.path.join(course_path, settings.MANIFEST_FILENAME)
                if not os.path.isfile(manifest_path):
                    continue

                try:
                    with open(manifest_path, encoding="utf-8") as f:
                        manifest_data = yaml.safe_load(f)

                    if not isinstance(manifest_data, dict):
                        continue

                    course_id = manifest_data.get("course_id", course_dir_name)
                    if course_id in seen_course_ids:
                        continue  # Avoid duplicates; higher priority directory wins
                    seen_course_ids.add(course_id)

                    course_title = manifest_data.get("course_title", course_dir_name)
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
                        elif os.path.exists(os.path.join(course_path, image_file)):
                            image_path = os.path.join(course_path, image_file)

                    if not image_path:
                        image_path = utils.get_resource_path(
                            os.path.join("assets/images/default_preview.jpg")
                        )

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
                        lambda checked=False, p=manifest_path: self.course_selected.emit(p)
                    )
                    self.courses_layout.addWidget(button)
                    found_courses = True
                except Exception as e:
                    logger.warning(f"Could not load manifest for course '{course_dir_name}': {e}")

        if not found_courses:
            self._render_empty_state()

    def _render_empty_state(self):
        empty_frame = QFrame()
        empty_frame.setObjectName("course_empty_state_frame")
        empty_layout = QVBoxLayout(empty_frame)
        empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.setContentsMargins(40, 40, 40, 40)
        empty_layout.setSpacing(15)

        welcome_label = QLabel(self.tr("<h2>Welcome to LanguageLearningApp!</h2>"))
        welcome_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(welcome_label)

        sub_label = QLabel(
            self.tr(
                "No courses were found in your library.<br>"
                "Get started by loading the starter course or importing a course package."
            )
        )
        sub_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub_label.setWordWrap(True)
        empty_layout.addWidget(sub_label)

        btn_layout = QHBoxLayout()
        btn_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        btn_layout.setSpacing(15)

        starter_btn = QPushButton(self.tr("Load Spanish Starter Course"))
        starter_btn.clicked.connect(self._load_starter_course)
        btn_layout.addWidget(starter_btn)

        import_btn = QPushButton(self.tr("Import Package (.lcpkg)..."))
        import_btn.clicked.connect(self._on_import_course_clicked)
        btn_layout.addWidget(import_btn)

        folder_btn = QPushButton(self.tr("Open Courses Folder"))
        folder_btn.clicked.connect(self._open_courses_folder)
        btn_layout.addWidget(folder_btn)

        empty_layout.addLayout(btn_layout)
        self.courses_layout.addWidget(empty_frame)

    def _load_starter_course(self):
        """Loads or installs the starter course bundled with the application."""
        # Check bundled courses first
        for d in utils.get_courses_search_directories():
            manifest = os.path.join(d, "starter_spanish", settings.MANIFEST_FILENAME)
            if os.path.isfile(manifest):
                self.course_selected.emit(manifest)
                return

        QMessageBox.information(
            self,
            self.tr("Starter Course"),
            self.tr(
                "Starter course was not found in the search directories. Try refreshing or importing an .lcpkg file."
            ),
        )

    def _on_import_course_clicked(self):
        pkg_path, _ = QFileDialog.getOpenFileName(
            self,
            self.tr("Import Course Package"),
            "",
            self.tr("Course Packages (*.lcpkg *.zip);;All Files (*)"),
        )
        if not pkg_path:
            return

        dest_dir = utils.get_user_courses_dir()
        success, msg, manifest_path = import_course_package(pkg_path, dest_dir)
        if success and manifest_path:
            QMessageBox.information(self, self.tr("Import Successful"), msg)
            self._find_and_display_courses()
            self.course_selected.emit(manifest_path)
        else:
            QMessageBox.warning(self, self.tr("Import Failed"), msg)

    def _open_courses_folder(self):
        courses_dir = utils.get_user_courses_dir()
        QDesktopServices.openUrl(QUrl.fromLocalFile(courses_dir))

    def changeEvent(self, event: QEvent):
        if event.type() == QEvent.Type.LanguageChange:
            self.retranslateUi()
        super().changeEvent(event)

    def retranslateUi(self):
        self.title_label.setText(self.tr("Select a Course"))
        self.import_button.setText(self.tr("Import Package (.lcpkg)..."))
        self.refresh_button.setText(self.tr("Refresh"))
        logger.debug("CourseSelectionView retranslated.")
