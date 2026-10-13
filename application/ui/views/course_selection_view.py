import logging
import os

import settings
import utils
import yaml
from PySide6.QtCore import QEvent, QSize, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QKeyEvent, QMouseEvent, QPixmap
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

try:
    from application.core.course_loader import import_course_package
except ImportError:
    from core.course_loader import import_course_package

logger = logging.getLogger(__name__)


class CourseThumbnailLabel(QLabel):
    """Fixed-width course artwork thumbnail.

    Encapsulates the aspect-ratio scaling math so the card itself stays a
    pure layout: the source pixmap is scaled once, when set, to fit inside a
    (THUMBNAIL_WIDTH x MAX_HEIGHT) box, and the widget takes that scaled size
    as its fixed size. No per-paint or per-resize math is needed.
    """

    THUMBNAIL_WIDTH = 150
    MAX_HEIGHT = 180

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("course_card_thumbnail")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Clicks anywhere on the card (including the artwork) activate it.
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def setSourcePath(self, image_path):
        """Load artwork from *image_path*; hides the label when unavailable."""
        pixmap = QPixmap(image_path) if image_path else QPixmap()
        if pixmap.isNull():
            self.setVisible(False)
            return
        scaled = pixmap.scaled(
            QSize(self.THUMBNAIL_WIDTH, self.MAX_HEIGHT),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        if scaled.isNull():
            self.setVisible(False)
            return
        self.setPixmap(scaled)
        # Fixed column width keeps titles aligned across cards; the label is
        # centered vertically by the card layout.
        self.setFixedSize(self.THUMBNAIL_WIDTH, scaled.height())


class CourseCardWidget(QFrame):
    """Selectable card representing a single course.

    A focusable container (QFrame), not a QPushButton: QFrame computes its
    size hints from its child layout, so no sizeHint() override is needed,
    and card visuals are scoped to ``QFrame#course_card`` selectors instead
    of leaking button pseudo-states into child labels. Activation (mouse and
    keyboard) is handled explicitly and reported via :attr:`clicked`.
    """

    clicked = Signal()

    METADATA_MIN_WIDTH = 180

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
        parent=None,
    ):
        super().__init__(parent)
        self.manifest_path = manifest_path
        self.setObjectName("course_card")
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        self.setLineWidth(1)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAccessibleName(course_title or "")
        if course_description:
            self.setAccessibleDescription(course_description)
        self.setProperty("pressed", False)
        self._armed = False
        self._press_visual = False

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(20)

        # Artwork on the left (hidden when no image is available).
        self.thumbnail = CourseThumbnailLabel(self)
        if image_path:
            self.thumbnail.setSourcePath(image_path)
        else:
            self.thumbnail.setVisible(False)
        main_layout.addWidget(self.thumbnail, 0, Qt.AlignmentFlag.AlignVCenter)

        # Text section in the middle; stretch lets it absorb width changes
        # while word wrapping keeps the height responsive to font metrics.
        text_layout = QVBoxLayout()
        text_layout.setSpacing(5)
        text_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self.title_label = QLabel(course_title or "")
        self.title_label.setObjectName("course_card_title")
        self.title_label.setWordWrap(True)
        self.title_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        text_layout.addWidget(self.title_label)

        self.description_label = None
        if course_description:
            self.description_label = QLabel(course_description)
            self.description_label.setObjectName("course_card_description")
            self.description_label.setWordWrap(True)
            self.description_label.setAttribute(
                Qt.WidgetAttribute.WA_TransparentForMouseEvents
            )
            text_layout.addWidget(self.description_label)

        main_layout.addLayout(text_layout, 1)

        # Separator + metadata on the right. The metadata panel uses a
        # minimum width (not a fixed width) so long values wrap instead of
        # overflowing on small screens or large fonts.
        separator = QFrame()
        separator.setObjectName("course_card_separator")
        separator.setFrameShape(QFrame.Shape.VLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        separator.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        main_layout.addWidget(separator)

        metadata_panel = QWidget()
        metadata_panel.setObjectName("course_card_metadata_panel")
        metadata_panel.setMinimumWidth(self.METADATA_MIN_WIDTH)
        metadata_panel.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        metadata_layout = QVBoxLayout(metadata_panel)
        metadata_layout.setContentsMargins(0, 0, 0, 0)
        metadata_layout.setSpacing(5)
        metadata_layout.setAlignment(
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
        )

        if author:
            metadata_layout.addWidget(
                self._make_metadata_label(f"<b>{self.tr('Author')}:</b> {author}")
            )

        if version:
            metadata_layout.addWidget(
                self._make_metadata_label(f"<b>{self.tr('Version')}:</b> {version}")
            )

        if source_language and target_language:
            metadata_layout.addWidget(
                self._make_metadata_label(
                    f"<b>{self.tr('Language')}:</b> {source_language} → {target_language}"
                )
            )

        main_layout.addWidget(metadata_panel, 0)

    @staticmethod
    def _make_metadata_label(rich_text):
        label = QLabel(rich_text)
        label.setObjectName("course_card_metadata")
        label.setWordWrap(True)
        label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        return label

    def click(self):
        """Programmatically activate the card (equivalent to a user click)."""
        self.clicked.emit()

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self._armed = True
            self._set_pressed_visual(True)
            self.setFocus(Qt.FocusReason.MouseFocusReason)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._armed:
            self._set_pressed_visual(self.rect().contains(event.position().toPoint()))
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if self._armed and event.button() == Qt.MouseButton.LeftButton:
            self._armed = False
            inside = self.rect().contains(event.position().toPoint())
            self._set_pressed_visual(False)
            if inside:
                self.clicked.emit()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def leaveEvent(self, event: QEvent):
        self._set_pressed_visual(False)
        super().leaveEvent(event)

    def keyPressEvent(self, event: QKeyEvent):
        if event.modifiers() == Qt.KeyboardModifier.NoModifier:
            if event.key() in (Qt.Key.Key_Enter, Qt.Key.Key_Return):
                self.clicked.emit()
                event.accept()
                return
            if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
                self._set_pressed_visual(True)
                event.accept()
                return
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent):
        if (
            event.key() == Qt.Key.Key_Space
            and not event.isAutoRepeat()
            and event.modifiers() == Qt.KeyboardModifier.NoModifier
        ):
            if self._press_visual:
                self._set_pressed_visual(False)
                self.clicked.emit()
                event.accept()
                return
        super().keyReleaseEvent(event)

    def focusOutEvent(self, event):
        self._set_pressed_visual(False)
        super().focusOutEvent(event)

    def _set_pressed_visual(self, pressed):
        pressed = bool(pressed)
        if pressed == self._press_visual:
            return
        self._press_visual = pressed
        self.setProperty("pressed", pressed)
        # Dynamic-property selectors ([pressed="true"]) only re-evaluate on
        # repolish.
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()


# Backward-compatible alias: CourseButton was the previous QPushButton-based
# implementation. New code should use CourseCardWidget.
CourseButton = CourseCardWidget


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

                    button = CourseCardWidget(
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
                        lambda p=manifest_path: self.course_selected.emit(p)
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
