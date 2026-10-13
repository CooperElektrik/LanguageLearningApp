import logging
import os
import uuid
from typing import Any

import yaml
from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QAction, QActionGroup, QColor, QFont, QUndoStack
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QStyle,
    QTabWidget,
    QTextEdit,
    QToolBar,
    QTreeWidgetItem,
    QTreeWidgetItemIterator,
    QVBoxLayout,
    QWidget,
)

try:
    from application.core import yaml_serializer
    from application.core.course_loader import (
        create_new_course,
        load_manifest,
    )
    from application.core.course_loader import (
        load_course_content as load_course_content_from_yaml,
    )
    from application.core.exercise_types import ALL_EXERCISE_TYPES
    from application.core.models import Course, Exercise, ExerciseOption, Lesson, Unit
    from application.tools.widgets.glossary_editor_widget import GlossaryEditorWidget

    from .dialogs.exercise_preview_dialog import ExercisePreviewDialog
    from .widgets.course_tree_widget import CourseTreeWidget
except ImportError as e:
    logging.error(
        f"Failed to import core or UI widgets for preview dialog. Ensure 'application' directory is on sys.path. Error: {e}"
    )

    class Course:
        pass

    class Unit:
        pass

    class Lesson:
        pass

    class Exercise:
        pass

    class ExerciseOption:
        pass

    class CourseTreeWidget:
        def __init__(self, *args, **kwargs):
            pass

    class GlossaryEditorWidget:
        def __init__(self, *args, **kwargs):
            pass

    class ExercisePreviewDialog:
        def __init__(self, *args, **kwargs):
            pass

    ALL_EXERCISE_TYPES = []

    def create_new_course(*args, **kwargs):
        return None

    def load_manifest(*args, **kwargs):
        return None

    def load_course_content_from_yaml(*args, **kwargs):
        return None

    yaml_serializer = None


from .course_packager import create_package_for_gui
from .course_validator import (
    perform_course_content_validation,
    perform_manifest_validation,
)
from .csv_importer import import_csv_data, load_existing_course_data, save_course_data
from .dialogs.csv_import_dialog import CsvImportDialog
from .dialogs.package_creation_dialog import PackageCreationDialog
from .editor.item_commands import ItemCommandsMixin
from .widgets.asset_hub_widget import AssetHubWidget
from .widgets.exercise_editor_widgets import (
    BaseExerciseEditorWidget,
    ContextBlockExerciseEditorWidget,
    DictationExerciseEditorWidget,
    FillInTheBlankExerciseEditorWidget,
    ImageAssociationExerciseEditorWidget,
    ListenAndSelectExerciseEditorWidget,
    MultipleChoiceExerciseEditorWidget,
    SentenceJumbleExerciseEditorWidget,
    TranslationExerciseEditorWidget,
    mark_widget_validity,
)
from .widgets.live_preview_pane import LivePreviewPane
from .widgets.manifest_editor_widget import ManifestEditorWidget
from .widgets.problems_drawer import ProblemsDrawer

logger = logging.getLogger(__name__)

_current_script_dir = os.path.dirname(os.path.abspath(__file__))
_dark_theme_qss_path = os.path.join(_current_script_dir, "styles", "dark_theme.qss")
_light_theme_qss_path = os.path.join(_current_script_dir, "styles", "light_theme.qss")


class EditorWindow(ItemCommandsMixin, QMainWindow):
    course_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        WIN_WIDTH = 1200
        WIN_HEIGHT = 800

        self.setWindowTitle("LL Course Editor")
        self.setGeometry(100, 100, WIN_WIDTH, WIN_HEIGHT)
        self.setObjectName("EditorWindow")
        # self.setFixedSize(WIN_WIDTH, WIN_HEIGHT)

        self.current_manifest_path: str = None
        self.current_course_content_path: str = None
        self.manifest_data: dict = None
        self.course_data: Course = None

        self.undo_stack = QUndoStack(self)
        self.undo_stack.cleanChanged.connect(lambda clean: self._set_dirty_state(not clean))

        self._create_actions()
        self._create_menu_bar()
        self._create_tool_bar()
        self._set_dirty_state(False)
        self._setup_ui()

        self._set_theme("dark")

        self.new_course()

    def _create_actions(self):
        self.new_action = QAction(
            self.style().standardIcon(QStyle.SP_FileIcon), "&New Course...", self
        )
        self.new_action.setShortcut(Qt.CTRL | Qt.Key_N)
        self.new_action.setStatusTip("Create a new course")
        self.new_action.triggered.connect(self.new_course)

        self.open_action = QAction(
            self.style().standardIcon(QStyle.SP_DialogOpenButton),
            "&Open Course...",
            self,
        )
        self.open_action.setShortcut(Qt.CTRL | Qt.Key_O)
        self.open_action.setStatusTip("Open an existing course manifest")
        self.open_action.triggered.connect(self.open_course)

        self.save_action = QAction(
            self.style().standardIcon(QStyle.SP_DialogSaveButton), "&Save Course", self
        )
        self.save_action.setShortcut(Qt.CTRL | Qt.Key_S)
        self.save_action.setStatusTip("Save the current course")
        self.save_action.triggered.connect(self.save_course)

        self.save_as_action = QAction("Save Course &As...", self)
        self.save_as_action.setShortcut(Qt.CTRL | Qt.SHIFT | Qt.Key_S)
        self.save_as_action.setStatusTip(
            "Save the current course under a new name or location"
        )
        self.save_as_action.triggered.connect(self.save_course_as)

        self.exit_action = QAction(
            self.style().standardIcon(QStyle.SP_DialogCloseButton), "E&xit", self
        )
        self.exit_action.setShortcut(Qt.CTRL | Qt.Key_Q)
        self.exit_action.setStatusTip("Exit the application")
        self.exit_action.triggered.connect(self.close)

        self.validate_action = QAction(
            self.style().standardIcon(QStyle.SP_DialogApplyButton),
            "&Validate Current Course",
            self,
        )
        self.validate_action.setStatusTip(
            "Validate the structure and content of the current course"
        )
        self.validate_action.triggered.connect(self.validate_current_course)

        self.import_csv_action = QAction(
            self.style().standardIcon(QStyle.SP_ArrowUp),
            "&Import Exercises from CSV...",
            self,
        )
        self.import_csv_action.setStatusTip("Import exercises from a CSV file")
        self.import_csv_action.triggered.connect(self.import_from_csv)

        self.package_action = QAction(
            self.style().standardIcon(QStyle.SP_DriveHDIcon),
            "Create Course &Package (.lcpkg)...",
            self,
        )
        self.package_action.setStatusTip(
            "Package the current course into a distributable .lcpkg file"
        )
        self.package_action.triggered.connect(self.create_course_package)

        self.undo_action = self.undo_stack.createUndoAction(self, "&Undo")
        self.undo_action.setShortcut(Qt.CTRL | Qt.Key_Z)
        self.undo_action.setIcon(self.style().standardIcon(QStyle.SP_ArrowBack))

        self.redo_action = self.undo_stack.createRedoAction(self, "&Redo")
        self.redo_action.setShortcut(Qt.CTRL | Qt.Key_Y)
        self.redo_action.setIcon(self.style().standardIcon(QStyle.SP_ArrowForward))

        self.theme_group = QActionGroup(self)
        self.light_theme_action = QAction("Light Theme", self, checkable=True)
        self.light_theme_action.setStatusTip("Switch to light theme")
        self.light_theme_action.triggered.connect(lambda: self._set_theme("light"))
        self.theme_group.addAction(self.light_theme_action)

        self.dark_theme_action = QAction("Dark Theme", self, checkable=True)
        self.dark_theme_action.setStatusTip("Switch to dark theme")
        self.dark_theme_action.triggered.connect(lambda: self._set_theme("dark"))
        self.theme_group.addAction(self.dark_theme_action)

    def _create_menu_bar(self):
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("&File")

        file_menu.addAction(self.new_action)
        file_menu.addAction(self.open_action)
        file_menu.addSeparator()
        file_menu.addAction(self.save_action)
        file_menu.addAction(self.save_as_action)
        file_menu.addSeparator()
        file_menu.addAction(self.exit_action)

        edit_menu = menu_bar.addMenu("&Edit")
        edit_menu.addAction(self.undo_action)
        edit_menu.addAction(self.redo_action)

        tools_menu = menu_bar.addMenu("&Tools")
        tools_menu.addAction(self.validate_action)
        tools_menu.addAction(self.import_csv_action)
        tools_menu.addSeparator()
        tools_menu.addAction(self.package_action)

        view_menu = menu_bar.addMenu("&View")
        theme_submenu = view_menu.addMenu("Theme")
        theme_submenu.addAction(self.light_theme_action)
        theme_submenu.addAction(self.dark_theme_action)

    def _create_tool_bar(self):
        tool_bar = QToolBar("Main Toolbar", self)
        tool_bar.setIconSize(QSize(22, 22))
        tool_bar.setToolButtonStyle(Qt.ToolButtonIconOnly)

        tool_bar.addAction(self.new_action)
        tool_bar.addAction(self.open_action)
        tool_bar.addAction(self.save_action)
        tool_bar.addSeparator()
        tool_bar.addAction(self.undo_action)
        tool_bar.addAction(self.redo_action)
        tool_bar.addSeparator()
        tool_bar.addAction(self.validate_action)
        tool_bar.addAction(self.import_csv_action)
        tool_bar.addAction(self.package_action)

        self.addToolBar(Qt.ToolBarArea.LeftToolBarArea, tool_bar)

    def _set_theme(self, theme_name: str):
        qss_file_path = ""
        if theme_name == "dark":
            qss_file_path = _dark_theme_qss_path
            self.dark_theme_action.setChecked(True)
        else:
            qss_file_path = _light_theme_qss_path
            self.light_theme_action.setChecked(True)

        try:
            with open(qss_file_path, encoding="utf-8") as f:
                qss_content = f.read()
            QApplication.instance().setStyleSheet(qss_content)
            self.status_bar.showMessage(
                f"Switched to {theme_name.capitalize()} Theme.", 3000
            )

        except FileNotFoundError:
            QMessageBox.warning(
                self, "Theme Error", f"Theme QSS file not found at: {qss_file_path}"
            )
            self.status_bar.showMessage(f"Error loading {theme_name} theme.", 3000)
            QApplication.instance().setStyleSheet("")
            self.dark_theme_action.setChecked(False)
            self.light_theme_action.setChecked(False)
        except Exception as e:
            QMessageBox.warning(
                self, "Theme Error", f"Failed to apply {theme_name} theme: {e}"
            )
            self.status_bar.showMessage(f"Error applying {theme_name} theme.", 3000)
            QApplication.instance().setStyleSheet("")
            self.dark_theme_action.setChecked(False)
            self.light_theme_action.setChecked(False)

    def _setup_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        outer_layout = QVBoxLayout(main_widget)
        outer_layout.setContentsMargins(6, 6, 6, 6)
        outer_layout.setSpacing(6)

        # Vertical splitter: top = 3-pane workspace, bottom = problems drawer
        self.vertical_splitter = QSplitter(Qt.Vertical)
        self.vertical_splitter.setObjectName("EditorVerticalSplitter")

        # 3-Pane Horizontal Splitter
        self.three_pane_splitter = QSplitter(Qt.Horizontal)
        self.three_pane_splitter.setObjectName("EditorThreePaneSplitter")
        self.splitter = self.three_pane_splitter  # For backward-compatibility

        # -------------------------------------------------------------
        # 1. Left Navigation Pane (Tabs: Structure, Manifest, Glossary)
        # -------------------------------------------------------------
        left_pane_widget = QWidget()
        left_pane_widget.setObjectName("LeftNavPane")
        left_pane_layout = QVBoxLayout(left_pane_widget)
        left_pane_layout.setContentsMargins(4, 4, 4, 4)
        left_pane_layout.setSpacing(6)

        self.left_nav_tabs = QTabWidget()
        self.left_nav_tabs.setObjectName("LeftNavTabs")

        # Tab 1: Structure
        structure_tab_widget = QWidget()
        structure_layout = QVBoxLayout(structure_tab_widget)
        structure_layout.setContentsMargins(4, 4, 4, 4)
        structure_layout.setSpacing(6)

        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search or filter (e.g. type:mcq, missing:audio)...")
        self.search_bar.textChanged.connect(self._filter_tree_view)
        structure_layout.addWidget(self.search_bar)

        # Filter Chips Layout
        chips_layout = QHBoxLayout()
        chips_layout.setSpacing(4)
        self.chip_all = QPushButton("All")
        self.chip_all.setProperty("isChip", True)
        self.chip_all.setCheckable(True)
        self.chip_all.setChecked(True)
        self.chip_all.clicked.connect(lambda: self._set_active_chip("all"))
        chips_layout.addWidget(self.chip_all)

        self.chip_audio = QPushButton("Audio")
        self.chip_audio.setProperty("isChip", True)
        self.chip_audio.setCheckable(True)
        self.chip_audio.clicked.connect(lambda: self._set_active_chip("audio"))
        chips_layout.addWidget(self.chip_audio)

        self.chip_image = QPushButton("Image")
        self.chip_image.setProperty("isChip", True)
        self.chip_image.setCheckable(True)
        self.chip_image.clicked.connect(lambda: self._set_active_chip("image"))
        chips_layout.addWidget(self.chip_image)

        self.chip_draft = QPushButton("Draft")
        self.chip_draft.setProperty("isChip", True)
        self.chip_draft.setCheckable(True)
        self.chip_draft.clicked.connect(lambda: self._set_active_chip("draft"))
        chips_layout.addWidget(self.chip_draft)

        chips_layout.addStretch(1)
        structure_layout.addLayout(chips_layout)

        # Course Tree
        self.tree_widget = CourseTreeWidget(self.course_data, self)
        self.tree_widget.setHeaderLabels(["Course Structure"])
        self.tree_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree_widget.customContextMenuRequested.connect(self._show_context_menu)
        self.tree_widget.itemSelectionChanged.connect(self._on_tree_item_selected)
        self.tree_widget.data_model_reordered.connect(self._handle_data_model_reordered)
        self.tree_widget.inline_add_requested.connect(self._handle_inline_add)
        structure_layout.addWidget(self.tree_widget, 1)

        # Tree Bottom Action Bar
        tree_actions_layout = QHBoxLayout()
        self.add_unit_button = QPushButton("+ Add Unit")
        self.add_unit_button.setProperty("primary", True)
        self.add_unit_button.clicked.connect(lambda: self._add_unit())
        tree_actions_layout.addWidget(self.add_unit_button)

        self.expand_all_button = QPushButton("Expand All")
        self.expand_all_button.clicked.connect(self.tree_widget.expandAll)
        self.collapse_all_button = QPushButton("Collapse All")
        self.collapse_all_button.clicked.connect(self.tree_widget.collapseAll)
        tree_actions_layout.addWidget(self.expand_all_button)
        tree_actions_layout.addWidget(self.collapse_all_button)
        structure_layout.addLayout(tree_actions_layout)

        self.left_nav_tabs.addTab(structure_tab_widget, "Structure")

        # Tab 2: Manifest Info Placeholder
        manifest_tab_widget = QWidget()
        manifest_tab_layout = QVBoxLayout(manifest_tab_widget)
        manifest_tab_lbl = QLabel("Manifest settings are displayed in the center Inspector.")
        manifest_tab_lbl.setWordWrap(True)
        manifest_tab_layout.addWidget(manifest_tab_lbl)
        manifest_tab_layout.addStretch(1)
        self.left_nav_tabs.addTab(manifest_tab_widget, "Manifest Info")

        # Tab 3: Glossary Placeholder
        glossary_tab_widget = QWidget()
        glossary_tab_layout = QVBoxLayout(glossary_tab_widget)
        glossary_tab_lbl = QLabel("Glossary vocabulary is displayed in the center Inspector.")
        glossary_tab_lbl.setWordWrap(True)
        glossary_tab_layout.addWidget(glossary_tab_lbl)
        glossary_tab_layout.addStretch(1)
        self.left_nav_tabs.addTab(glossary_tab_widget, "Glossary")

        self.left_nav_tabs.currentChanged.connect(self._handle_left_tab_changed)
        left_pane_layout.addWidget(self.left_nav_tabs)
        self.three_pane_splitter.addWidget(left_pane_widget)

        # -------------------------------------------------------------
        # 2. Center Pane (Inspector / Property Form Editor)
        # -------------------------------------------------------------
        center_pane_widget = QWidget()
        center_pane_widget.setObjectName("CenterInspectorPane")
        center_pane_layout = QVBoxLayout(center_pane_widget)
        center_pane_layout.setContentsMargins(6, 6, 6, 6)
        center_pane_layout.setSpacing(6)

        inspector_header = QLabel("<b>Inspector & Details</b>")
        center_pane_layout.addWidget(inspector_header)

        self.detail_editor_stacked_widget = QStackedWidget()
        self.detail_editor_stacked_widget.setObjectName("DetailEditorStackedWidget")

        self._placeholder_editor_widget = QLabel("Select an item to edit its properties.")
        self._placeholder_editor_widget.setAlignment(Qt.AlignCenter)
        self._placeholder_editor_widget.setStyleSheet("color: #888899; font-style: italic;")
        self.detail_editor_stacked_widget.addWidget(self._placeholder_editor_widget)

        self.manifest_editor = ManifestEditorWidget()
        self.manifest_editor.data_changed.connect(self._set_dirty_state)
        self.detail_editor_stacked_widget.addWidget(self.manifest_editor)

        self.glossary_editor = GlossaryEditorWidget()
        self.glossary_editor.data_changed.connect(self._set_dirty_state)
        self.detail_editor_stacked_widget.addWidget(self.glossary_editor)

        center_pane_layout.addWidget(self.detail_editor_stacked_widget, 1)

        self.item_actions_widget = QWidget()
        item_actions_layout = QHBoxLayout(self.item_actions_widget)
        item_actions_layout.setContentsMargins(0, 4, 0, 0)
        self.move_up_button = QPushButton("Move Up ↑")
        self.move_up_button.clicked.connect(self._move_item_up)
        self.move_down_button = QPushButton("Move Down ↓")
        self.move_down_button.clicked.connect(self._move_item_down)
        self.preview_exercise_button = QPushButton("Refresh Preview ▶")
        self.preview_exercise_button.clicked.connect(self._preview_exercise)
        item_actions_layout.addStretch(1)
        item_actions_layout.addWidget(self.move_up_button)
        item_actions_layout.addWidget(self.move_down_button)
        item_actions_layout.addWidget(self.preview_exercise_button)
        item_actions_layout.addStretch(1)
        center_pane_layout.addWidget(self.item_actions_widget)
        self.item_actions_widget.setVisible(False)

        self.three_pane_splitter.addWidget(center_pane_widget)

        # -------------------------------------------------------------
        # 3. Right Pane (Live Preview & Integrated Asset Hub)
        # -------------------------------------------------------------
        right_pane_widget = QWidget()
        right_pane_widget.setObjectName("RightPreviewPane")
        right_pane_layout = QVBoxLayout(right_pane_widget)
        right_pane_layout.setContentsMargins(4, 4, 4, 4)
        right_pane_layout.setSpacing(6)

        self.right_splitter = QSplitter(Qt.Vertical)
        self.right_splitter.setObjectName("RightSplitter")

        self.live_preview_pane = LivePreviewPane(self)
        self.right_splitter.addWidget(self.live_preview_pane)

        self.asset_hub = AssetHubWidget(course_root_dir=None, parent=self)
        self.asset_hub.asset_selected.connect(self._handle_asset_hub_selected)
        self.right_splitter.addWidget(self.asset_hub)
        self.right_splitter.setSizes([450, 300])

        right_pane_layout.addWidget(self.right_splitter, 1)
        self.three_pane_splitter.addWidget(right_pane_widget)

        # Set 3-pane widths (Left: 310, Center: 510, Right: 380)
        self.three_pane_splitter.setSizes([310, 510, 380])
        self.vertical_splitter.addWidget(self.three_pane_splitter)

        # -------------------------------------------------------------
        # 4. Bottom Problems & Validation Drawer
        # -------------------------------------------------------------
        self.problems_drawer = ProblemsDrawer(self)
        self.problems_drawer.validate_requested.connect(self.validate_current_course)
        self.problems_drawer.issue_selected.connect(self._navigate_to_validation_issue)
        self.vertical_splitter.addWidget(self.problems_drawer)
        self.vertical_splitter.setSizes([680, 140])

        outer_layout.addWidget(self.vertical_splitter)

        self.current_editor_widget = None
        self.current_selected_tree_item = None

        self.status_bar = self.statusBar()
        self.current_file_label = QLabel("No course loaded")
        self.dirty_status_label = QLabel("")
        self.dirty_status_label.setStyleSheet("padding-right: 10px;")

        self.status_bar.addPermanentWidget(self.current_file_label, stretch=1)
        self.status_bar.addPermanentWidget(self.dirty_status_label)

        if self.is_dirty:
            self.dirty_status_label.setText("Unsaved Changes*")
            self.dirty_status_label.setStyleSheet(
                "color: orange; padding-right: 10px; font-weight: bold;"
            )
        else:
            self.dirty_status_label.setText("Saved")
            self.dirty_status_label.setStyleSheet("color: green; padding-right: 10px;")

    def _set_active_chip(self, chip_name: str):
        for chip, name in [
            (self.chip_all, "all"),
            (self.chip_audio, "audio"),
            (self.chip_image, "image"),
            (self.chip_draft, "draft"),
        ]:
            chip.setChecked(name == chip_name)
        self._filter_tree_view(self.search_bar.text())

    def _handle_inline_add(self, item_type: str, parent_obj: Any):
        if item_type == "unit":
            self._add_unit()
        elif item_type == "lesson":
            self._add_lesson(parent_obj)
        elif item_type == "exercise":
            self._add_exercise(parent_obj)

    def _handle_left_tab_changed(self, index: int):
        if index == 0:
            sel = self.tree_widget.currentItem()
            if sel:
                self._on_tree_item_selected()
            else:
                self._display_item_editor(None)
        elif index == 1:
            manifest_item_data = {
                "type": "manifest",
                "manifest_data": self.manifest_data,
                "course_obj": self.course_data,
            }
            self._display_item_editor(manifest_item_data)
        elif index == 2:
            glossary_item_data = {"type": "glossary"}
            self._display_item_editor(glossary_item_data)

    def _update_context_paths(self):
        base_dir = (
            os.path.dirname(self.current_manifest_path)
            if self.current_manifest_path
            else (
                os.path.dirname(self.current_course_content_path)
                if self.current_course_content_path
                else None
            )
        )
        if hasattr(self, "asset_hub"):
            self.asset_hub.set_course_root_dir(base_dir)
        if hasattr(self, "live_preview_pane"):
            langs = {
                "target": (
                    self.course_data.target_language
                    if self.course_data
                    else "Target Language"
                ),
                "source": (
                    self.course_data.source_language
                    if self.course_data
                    else "Source Language"
                ),
            }
            self.live_preview_pane.set_course_context(langs, base_dir)

    def _handle_asset_hub_selected(self, relative_asset_path: str):
        self.status_bar.showMessage(
            f"Selected asset: {relative_asset_path} (drag directly into fields)", 3000
        )

    def _navigate_to_validation_issue(self, issue: Any):
        issue_str = str(issue)
        unit_id = getattr(issue, "unit_id", None)
        lesson_id = getattr(issue, "lesson_id", None)
        exercise_id = getattr(issue, "exercise_id", None)

        if "Manifest" in issue_str:
            self.left_nav_tabs.setCurrentIndex(1)
            return
        elif "glossary" in issue_str.lower():
            self.left_nav_tabs.setCurrentIndex(2)
            return
        else:
            self.left_nav_tabs.setCurrentIndex(0)

        if not self.course_data:
            return

        target_obj = None
        for unit in self.course_data.units:
            if exercise_id or "Exercise" in issue_str:
                for lesson in unit.lessons:
                    for ex in lesson.exercises:
                        if (exercise_id and ex.exercise_id == exercise_id) or (
                            ex.exercise_id and ex.exercise_id in issue_str
                        ):
                            target_obj = ex
                            break
                    if target_obj:
                        break
            if target_obj:
                break
            if lesson_id or "Lesson" in issue_str:
                for lesson in unit.lessons:
                    if (lesson_id and lesson.lesson_id == lesson_id) or (
                        lesson.lesson_id and lesson.lesson_id in issue_str
                    ):
                        target_obj = lesson
                        break
            if target_obj:
                break
            if (unit_id and unit.unit_id == unit_id) or (
                unit.unit_id and unit.unit_id in issue_str
            ):
                target_obj = unit
                break

        if target_obj:
            self._expand_and_select_item(target_obj)
            self.status_bar.showMessage(f"Navigated to: {issue_str[:80]}", 3000)
            field = getattr(issue, "field", None)
            if field and self.current_editor_widget:
                for attr_name in [f"{field}_edit", f"{field}_input", field]:
                    w = getattr(self.current_editor_widget, attr_name, None)
                    if w and hasattr(w, "setFocus"):
                        w.setFocus()
                        mark_widget_validity(w, False)
                        break

    def _handle_data_model_reordered(self, moved_obj: Any, new_parent_obj: Any):
        self.update_tree_view()
        self._set_dirty_state(True)
        self._expand_and_select_item(moved_obj)
        self.status_bar.showMessage("Item reordered successfully.", 2000)

    def _clear_advanced_filters(self):
        """Resets search bar and filter chips."""
        self.search_bar.clear()
        self._set_active_chip("all")
        self.status_bar.showMessage("Filters cleared.", 2000)

    def _filter_tree_view(self, text: str = ""):
        if not self.tree_widget:
            return
        query = (text or self.search_bar.text()).strip().lower()

        # Parse query syntax
        type_filter = None
        asset_mode = None
        text_tokens = []

        for token in query.split():
            if token.startswith("type:"):
                type_filter = token[5:].strip()
            elif token in ["missing:audio", "no:audio"]:
                asset_mode = "missing_audio"
            elif token in ["has:audio", "with:audio"]:
                asset_mode = "has_audio"
            elif token in ["missing:image", "no:image"]:
                asset_mode = "missing_image"
            elif token in ["has:image", "with:image"]:
                asset_mode = "has_image"
            else:
                text_tokens.append(token)

        search_term = " ".join(text_tokens)

        # Check filter chips
        if hasattr(self, "chip_audio") and self.chip_audio.isChecked():
            asset_mode = "has_audio"
        elif hasattr(self, "chip_image") and self.chip_image.isChecked():
            asset_mode = "has_image"
        elif hasattr(self, "chip_draft") and self.chip_draft.isChecked():
            asset_mode = "missing_assets"

        iterator = QTreeWidgetItemIterator(self.tree_widget, QTreeWidgetItemIterator.All)
        while iterator.value():
            item = iterator.value()
            item_data = item.data(0, Qt.UserRole)
            is_visible = True

            if isinstance(item_data, dict):
                item.setHidden(bool(search_term or type_filter or asset_mode))
                iterator += 1
                continue

            if isinstance(item_data, (Unit, Lesson)):
                if search_term and search_term not in item.text(0).lower():
                    is_visible = False
                item.setHidden(not is_visible)
                iterator += 1
                continue

            if isinstance(item_data, Exercise):
                ex = item_data
                if type_filter and type_filter not in ex.type.lower():
                    is_visible = False
                if asset_mode == "has_audio" and not getattr(ex, "audio_file", None):
                    is_visible = False
                elif asset_mode == "missing_audio" and getattr(ex, "audio_file", None):
                    is_visible = False
                elif asset_mode == "has_image" and not getattr(ex, "image_file", None):
                    is_visible = False
                elif asset_mode == "missing_image" and getattr(ex, "image_file", None):
                    is_visible = False
                elif asset_mode == "missing_assets" and (
                    getattr(ex, "audio_file", None) or getattr(ex, "image_file", None)
                ):
                    is_visible = False

                if is_visible and search_term:
                    searchable = " ".join([
                        getattr(ex, "prompt", "") or "",
                        getattr(ex, "title", "") or "",
                        getattr(ex, "answer", "") or "",
                        getattr(ex, "source_word", "") or "",
                        getattr(ex, "sentence_template", "") or "",
                        getattr(ex, "explanation", "") or "",
                    ]).lower()
                    if search_term not in searchable:
                        is_visible = False

                item.setHidden(not is_visible)

            iterator += 1

        # Second pass: ensure parents of visible items are visible and expanded
        iterator = QTreeWidgetItemIterator(self.tree_widget, QTreeWidgetItemIterator.All)
        while iterator.value():
            item = iterator.value()
            if not item.isHidden():
                parent = item.parent()
                while parent:
                    parent.setHidden(False)
                    parent.setExpanded(True)
                    parent = parent.parent()
            iterator += 1

    def _set_dirty_state(self, dirty: bool = True):
        self.is_dirty = dirty
        self.setWindowTitle(
            f"LL Course Editor{' *' if dirty else ''} - "
            f"{os.path.basename(self.current_manifest_path) if self.current_manifest_path else 'New Course'}"
        )
        if hasattr(self, "dirty_status_label"):
            if dirty:
                self.dirty_status_label.setText("Unsaved Changes*")
                self.dirty_status_label.setStyleSheet("color: orange; padding-right: 10px; font-weight: bold;")
            else:
                self.dirty_status_label.setText("Saved")
                self.dirty_status_label.setStyleSheet("color: green; padding-right: 10px;")

    def _display_item_editor(self, item_data: Any):
        if not hasattr(self, "_editor_cache"):
            self._editor_cache = {}

        if isinstance(item_data, dict) and item_data.get("type") == "manifest":
            self.current_editor_widget = self.manifest_editor
            self.manifest_editor.load_data(
                item_data.get("manifest_data", {}) or (self.manifest_data or {}),
                item_data.get("course_obj", self.course_data),
                os.path.dirname(self.current_manifest_path)
                if self.current_manifest_path
                else None,
            )
            self.detail_editor_stacked_widget.setCurrentWidget(self.manifest_editor)
            self.live_preview_pane.update_preview(None)
        elif isinstance(item_data, dict) and item_data.get("type") == "glossary":
            self.current_editor_widget = self.glossary_editor
            self.glossary_editor.load_glossary_data(
                self.manifest_data, self.current_manifest_path
            )
            self.detail_editor_stacked_widget.setCurrentWidget(self.glossary_editor)
            self.live_preview_pane.update_preview(None)
        elif isinstance(item_data, Unit):
            cache_key = "unit_editor"
            if cache_key not in self._editor_cache:
                w = self._create_unit_editor_widget(item_data)
                self._editor_cache[cache_key] = w
                self.detail_editor_stacked_widget.addWidget(w)
            else:
                w = self._editor_cache[cache_key]
                self._populate_unit_editor_widget(w, item_data)
            self.current_editor_widget = w
            self.detail_editor_stacked_widget.setCurrentWidget(w)
            self.live_preview_pane.update_preview(None)
        elif isinstance(item_data, Lesson):
            cache_key = "lesson_editor"
            if cache_key not in self._editor_cache:
                w = self._create_lesson_editor_widget(item_data)
                self._editor_cache[cache_key] = w
                self.detail_editor_stacked_widget.addWidget(w)
            else:
                w = self._editor_cache[cache_key]
                self._populate_lesson_editor_widget(w, item_data)
            self.current_editor_widget = w
            self.detail_editor_stacked_widget.setCurrentWidget(w)
            self.live_preview_pane.update_preview(None)
        elif isinstance(item_data, Exercise):
            cache_key = f"exercise_{id(item_data)}"
            if cache_key not in self._editor_cache:
                w = self._create_exercise_editor_widget(item_data)
                self._editor_cache[cache_key] = w
                self.detail_editor_stacked_widget.addWidget(w)
            else:
                w = self._editor_cache[cache_key]
            self.current_editor_widget = w
            self.detail_editor_stacked_widget.setCurrentWidget(w)
            self.live_preview_pane.update_preview(item_data)
        else:
            self.current_editor_widget = self._placeholder_editor_widget
            self.detail_editor_stacked_widget.setCurrentWidget(self._placeholder_editor_widget)
            self.live_preview_pane.update_preview(None)

    def _clear_editor_pane(self):
        self.current_editor_widget = None
        if hasattr(self, "_placeholder_editor_widget"):
            self.detail_editor_stacked_widget.setCurrentWidget(self._placeholder_editor_widget)

    def _populate_unit_editor_widget(self, widget: QWidget, unit: Unit):
        widget.unit_id_edit.setText(unit.unit_id)
        widget.unit_title_edit.blockSignals(True)
        widget.unit_title_edit.setText(unit.title)
        widget.unit_title_edit.blockSignals(False)
        try:
            widget.unit_title_edit.textChanged.disconnect()
        except RuntimeError:
            pass
        widget.unit_title_edit.textChanged.connect(lambda text: self._update_unit_title(unit, text))
        widget.unit_title_edit.textChanged.connect(lambda text: self._validate_line_edit_required(widget.unit_title_edit, True))
        self._validate_line_edit_required(widget.unit_title_edit, True)

    def _populate_lesson_editor_widget(self, widget: QWidget, lesson: Lesson):
        widget.lesson_id_edit.setText(lesson.lesson_id)
        widget.lesson_title_edit.blockSignals(True)
        widget.lesson_title_edit.setText(lesson.title)
        widget.lesson_title_edit.blockSignals(False)
        try:
            widget.lesson_title_edit.textChanged.disconnect()
        except RuntimeError:
            pass
        widget.lesson_title_edit.textChanged.connect(lambda text: self._update_lesson_title(lesson, text))
        widget.lesson_title_edit.textChanged.connect(lambda text: self._validate_line_edit_required(widget.lesson_title_edit, True))
        self._validate_line_edit_required(widget.lesson_title_edit, True)

    def _validate_line_edit_required(self, input_widget: QLineEdit, is_required: bool):
        if not is_required:
            mark_widget_validity(input_widget, True)
            return
        text = input_widget.text().strip()
        mark_widget_validity(input_widget, bool(text))
        self._set_dirty_state(True)

    def _create_unit_editor_widget(self, unit: Unit):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.addWidget(QLabel(f"Editing Unit: {unit.title}"))
        id_layout = QHBoxLayout()
        id_layout.addWidget(QLabel("Unit ID:"))
        unit_id_edit = QLineEdit(unit.unit_id)
        unit_id_edit.setReadOnly(True)
        id_layout.addWidget(unit_id_edit)
        layout.addLayout(id_layout)
        title_layout = QHBoxLayout()
        title_label = QLabel("Title: *")
        title_layout.addWidget(title_label)
        unit_title_edit = QLineEdit(unit.title)
        unit_title_edit.textChanged.connect(
            lambda text: self._update_unit_title(unit, text)
        )
        unit_title_edit.textChanged.connect(
            lambda text: self._validate_line_edit_required(unit_title_edit, True)
        )
        title_layout.addWidget(unit_title_edit)
        layout.addLayout(title_layout)
        layout.addStretch(1)
        widget.unit_id_edit = unit_id_edit
        widget.unit_title_edit = unit_title_edit
        self._validate_line_edit_required(unit_title_edit, True)
        return widget

    def _update_unit_title(self, unit: Unit, new_title: str):
        unit.title = new_title.strip()
        self._set_dirty_state(True)
        if (
            self.current_selected_tree_item
            and self.current_selected_tree_item.data(0, Qt.UserRole) is unit
        ):
            self.current_selected_tree_item.setText(0, new_title.strip())

    def _create_lesson_editor_widget(self, lesson: Lesson):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.addWidget(QLabel(f"Editing Lesson: {lesson.title}"))
        id_layout = QHBoxLayout()
        id_layout.addWidget(QLabel("Lesson ID:"))
        lesson_id_edit = QLineEdit(lesson.lesson_id)
        lesson_id_edit.setReadOnly(True)
        id_layout.addWidget(lesson_id_edit)
        layout.addLayout(id_layout)
        title_layout = QHBoxLayout()
        title_label = QLabel("Title: *")
        title_layout.addWidget(title_label)
        lesson_title_edit = QLineEdit(lesson.title)
        lesson_title_edit.textChanged.connect(
            lambda text: self._update_lesson_title(lesson, text)
        )
        lesson_title_edit.textChanged.connect(
            lambda text: self._validate_line_edit_required(lesson_title_edit, True)
        )
        title_layout.addWidget(lesson_title_edit)
        layout.addLayout(title_layout)
        layout.addStretch(1)
        widget.lesson_id_edit = lesson_id_edit
        widget.lesson_title_edit = lesson_title_edit
        self._validate_line_edit_required(lesson_title_edit, True)
        return widget

    def _update_lesson_title(self, lesson: Lesson, new_title: str):
        lesson.title = new_title.strip()
        self._set_dirty_state(True)
        if (
            self.current_selected_tree_item
            and self.current_selected_tree_item.data(0, Qt.UserRole) is lesson
        ):
            self.current_selected_tree_item.setText(0, new_title.strip())

    def _create_exercise_editor_widget(self, exercise: Exercise):
        target_lang = (
            self.course_data.target_language if self.course_data else "Target Language"
        )
        source_lang = (
            self.course_data.source_language if self.course_data else "Source Language"
        )

        course_root_dir = None
        if self.current_manifest_path:
            course_root_dir = os.path.dirname(self.current_manifest_path)
        elif self.current_course_content_path:
            course_root_dir = os.path.dirname(self.current_course_content_path)
            logging.warning(
                "Using content file directory as course root for asset handling. Save manifest for best results."
            )
        else:
            logging.warning(
                "Course root directory for assets could not be determined (no manifest/content path). Asset browsing might be limited to full paths."
            )

        widget: BaseExerciseEditorWidget

        if (
            exercise.type == "translate_to_target"
            or exercise.type == "translate_to_source"
        ):
            widget = TranslationExerciseEditorWidget(
                exercise, target_lang, source_lang, course_root_dir
            )
        elif exercise.type == "multiple_choice_translation":
            widget = MultipleChoiceExerciseEditorWidget(
                exercise, target_lang, source_lang
            )
        elif exercise.type == "fill_in_the_blank":
            widget = FillInTheBlankExerciseEditorWidget(
                exercise, target_lang, source_lang
            )
        elif exercise.type == "dictation":
            widget = DictationExerciseEditorWidget(
                exercise, target_lang, source_lang, course_root_dir
            )
        elif exercise.type == "image_association":
            widget = ImageAssociationExerciseEditorWidget(
                exercise, target_lang, source_lang, course_root_dir
            )
        elif exercise.type == "listen_and_select":
            widget = ListenAndSelectExerciseEditorWidget(
                exercise, target_lang, source_lang, course_root_dir
            )
        elif exercise.type == "sentence_jumble":
            widget = SentenceJumbleExerciseEditorWidget(
                exercise,
                target_lang,
                source_lang,  # No course_root_dir typically
            )
        elif exercise.type == "context_block":
            widget = ContextBlockExerciseEditorWidget(
                exercise  # No langs or course_root_dir typically
            )
        else:
            widget = QLabel(f"No editor for exercise type: {exercise.type}")
            widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if hasattr(widget, "data_changed"):
            widget.data_changed.connect(self._set_dirty_state)
        return widget

    def _on_tree_item_selected(self):
        selected_items = self.tree_widget.selectedItems()
        self.current_selected_tree_item = None
        self.item_actions_widget.setVisible(False)

        if not selected_items:
            self._display_item_editor(None)
            return

        self.current_selected_tree_item = selected_items[0]
        item_data = self.current_selected_tree_item.data(0, Qt.UserRole)
        self._display_item_editor(item_data)

        if isinstance(item_data, (Unit, Lesson, Exercise)):
            self.item_actions_widget.setVisible(True)
            parent_list, current_index = self._get_item_list_and_index(item_data)
            if parent_list is not None and current_index is not None:
                self.move_up_button.setEnabled(current_index > 0)
                self.move_down_button.setEnabled(current_index < len(parent_list) - 1)
            else:
                self.move_up_button.setEnabled(False)
                self.move_down_button.setEnabled(False)
            self.preview_exercise_button.setEnabled(isinstance(item_data, Exercise))
        else:
            self.item_actions_widget.setVisible(False)

    def _get_item_list_and_index(
        self, item_data_obj: Any
    ) -> tuple[list | None, int | None]:
        """Helper to get the list and index of an item for reordering."""
        if isinstance(item_data_obj, Unit):
            try:
                return self.course_data.units, self.course_data.units.index(
                    item_data_obj
                )
            except ValueError:
                return None, None
        elif isinstance(item_data_obj, Lesson):
            parent_unit_item = self.current_selected_tree_item.parent()
            if parent_unit_item:
                parent_unit: Unit = parent_unit_item.data(0, Qt.UserRole)
                if parent_unit and isinstance(parent_unit, Unit):
                    try:
                        return parent_unit.lessons, parent_unit.lessons.index(
                            item_data_obj
                        )
                    except ValueError:
                        return None, None
        elif isinstance(item_data_obj, Exercise):
            parent_lesson_item = self.current_selected_tree_item.parent()
            if parent_lesson_item:
                parent_lesson: Lesson = parent_lesson_item.data(0, Qt.UserRole)
                if parent_lesson and isinstance(parent_lesson, Lesson):
                    try:
                        return parent_lesson.exercises, parent_lesson.exercises.index(
                            item_data_obj
                        )
                    except ValueError:
                        return None, None
        return None, None

    def _move_item_up(self):
        if not self.current_selected_tree_item:
            return
        item_data = self.current_selected_tree_item.data(0, Qt.UserRole)
        parent_list, current_index = self._get_item_list_and_index(item_data)

        if parent_list is not None and current_index is not None and current_index > 0:
            parent_list.insert(current_index - 1, parent_list.pop(current_index))
            self.update_tree_view()
            self._set_dirty_state(True)
            self._expand_and_select_item(item_data)
            self._on_tree_item_selected()

    def _move_item_down(self):
        if not self.current_selected_tree_item:
            return
        item_data = self.current_selected_tree_item.data(0, Qt.UserRole)
        parent_list, current_index = self._get_item_list_and_index(item_data)

        if (
            parent_list is not None
            and current_index is not None
            and current_index < len(parent_list) - 1
        ):
            parent_list.insert(current_index + 1, parent_list.pop(current_index))
            self.update_tree_view()
            self._set_dirty_state(True)
            self._expand_and_select_item(item_data)
            self._on_tree_item_selected()

    def _show_context_menu(self, position):
        item = self.tree_widget.itemAt(position)
        menu = QMenu(self)

        add_unit_action = QAction("Add New Unit", self)
        add_unit_action.triggered.connect(self._add_unit)
        menu.addAction(add_unit_action)

        if item:
            item_data = item.data(0, Qt.UserRole)
            if isinstance(item_data, dict) and item_data.get("type") == "manifest":
                pass
            elif isinstance(item_data, Unit):
                add_lesson_action = QAction("Add New Lesson", self)
                add_lesson_action.triggered.connect(lambda: self._add_lesson(item))
                menu.addAction(add_lesson_action)

                duplicate_unit_action = QAction("Duplicate Unit", self)
                duplicate_unit_action.triggered.connect(
                    lambda: self._duplicate_unit(item)
                )
                menu.addAction(duplicate_unit_action)
                menu.addSeparator()

                delete_unit_action = QAction("Delete Unit", self)
                delete_unit_action.triggered.connect(lambda: self._delete_unit(item))
                menu.addAction(delete_unit_action)
            elif isinstance(item_data, Lesson):
                add_exercise_action = QAction("Add New Exercise", self)
                add_exercise_action.triggered.connect(lambda: self._add_exercise(item))
                menu.addAction(add_exercise_action)

                duplicate_lesson_action = QAction("Duplicate Lesson", self)
                duplicate_lesson_action.triggered.connect(
                    lambda: self._duplicate_lesson(item)
                )
                menu.addAction(duplicate_lesson_action)
                menu.addSeparator()

                delete_lesson_action = QAction("Delete Lesson", self)
                delete_lesson_action.triggered.connect(
                    lambda: self._delete_lesson(item)
                )
                menu.addAction(delete_lesson_action)
            elif isinstance(item_data, Exercise):
                duplicate_exercise_action = QAction("Duplicate Exercise", self)
                duplicate_exercise_action.triggered.connect(
                    lambda: self._duplicate_exercise(item)
                )
                menu.addAction(duplicate_exercise_action)
                menu.addSeparator()

                delete_exercise_action = QAction("Delete Exercise", self)
                delete_exercise_action.triggered.connect(
                    lambda: self._delete_exercise(item)
                )
                menu.addAction(delete_exercise_action)

        menu.exec(self.tree_widget.viewport().mapToGlobal(position))

    def _preview_exercise(self):
        if not self.current_selected_tree_item:
            QMessageBox.warning(
                self,
                "Preview Error",
                "Please select an exercise in the tree to preview.",
            )
            return

        item_data = self.current_selected_tree_item.data(0, Qt.UserRole)
        if not isinstance(item_data, Exercise):
            QMessageBox.warning(
                self,
                "Preview Error",
                "Only exercises can be previewed. Please select an exercise.",
            )
            return

        course_languages = {
            "target": (
                self.course_data.target_language
                if self.course_data
                else "Target Language"
            ),
            "source": (
                self.course_data.source_language
                if self.course_data
                else "Source Language"
            ),
        }
        course_content_base_dir = None
        if self.current_course_content_path:
            course_content_base_dir = os.path.dirname(self.current_course_content_path)

        dialog = ExercisePreviewDialog(
            item_data, course_languages, course_content_base_dir, self
        )
        dialog.exec()

    def _expand_and_select_item(self, item_data_obj: Any):
        def find_and_select(parent_item, target_data_obj):
            for i in range(parent_item.childCount()):
                child_item = parent_item.child(i)
                if child_item.data(0, Qt.UserRole) is target_data_obj:
                    self.tree_widget.setCurrentItem(child_item)
                    self.tree_widget.expandItem(parent_item)
                    if child_item.childCount() > 0:
                        self.tree_widget.expandItem(child_item)
                    self.tree_widget.scrollToItem(child_item)
                    return True
                if find_and_select(child_item, target_data_obj):
                    return True
            return False

        hidden_root = self.tree_widget.invisibleRootItem()
        find_and_select(hidden_root, item_data_obj)

    def update_tree_view(self):
        if not self.tree_widget:
            return
        expanded_items_data = {}
        selected_item_data = None

        current_sel_item = self.tree_widget.currentItem()
        if current_sel_item:
            selected_item_data = current_sel_item.data(0, Qt.UserRole)

        iterator = QTreeWidgetItemIterator(self.tree_widget)
        while iterator.value():
            item = iterator.value()
            item_data = item.data(0, Qt.UserRole)
            if item_data:
                expanded_items_data[id(item_data)] = item.isExpanded()
            iterator += 1

        self.tree_widget.set_course_data(self.course_data)
        self.tree_widget.clear()
        if not self.course_data:
            return

        for unit in self.course_data.units:
            unit_item = QTreeWidgetItem(self.tree_widget, [unit.title])
            unit_item.setData(0, Qt.UserRole, unit)
            unit_item.setFlags(
                unit_item.flags()
                | Qt.ItemFlag.ItemIsDragEnabled
                | Qt.ItemFlag.ItemIsDropEnabled
            )
            if id(unit) in expanded_items_data and expanded_items_data[id(unit)]:
                unit_item.setExpanded(True)

            for lesson in unit.lessons:
                lesson_item = QTreeWidgetItem(unit_item, [lesson.title])
                lesson_item.setData(0, Qt.UserRole, lesson)
                lesson_item.setFlags(
                    lesson_item.flags()
                    | Qt.ItemFlag.ItemIsDragEnabled
                    | Qt.ItemFlag.ItemIsDropEnabled
                )
                if (
                    id(lesson) in expanded_items_data
                    and expanded_items_data[id(lesson)]
                ):
                    lesson_item.setExpanded(True)

                for exercise in lesson.exercises:
                    ex_display_text_content = "No Content"
                    if exercise.title:  # Primarily for context_block
                        ex_display_text_content = exercise.title
                    elif exercise.prompt:
                        ex_display_text_content = exercise.prompt
                    elif exercise.answer:  # For jumble or dictation answer
                        ex_display_text_content = exercise.answer
                    elif exercise.source_word:  # For MCQ
                        ex_display_text_content = exercise.source_word
                    elif exercise.sentence_template:  # For FIB
                        ex_display_text_content = exercise.sentence_template

                    if len(ex_display_text_content) > 50:  # Truncate if too long
                        ex_display_text_content = ex_display_text_content[:47] + "..."
                    type_badge = self.tree_widget.get_exercise_type_badge(exercise.type)
                    asset_badges = self.tree_widget.get_asset_badges(exercise)
                    badge_suffix = f"  {asset_badges}" if asset_badges else ""
                    ex_display_text = f"{type_badge} {ex_display_text_content}{badge_suffix}"

                    exercise_item = QTreeWidgetItem(lesson_item, [ex_display_text])
                    exercise_item.setData(0, Qt.UserRole, exercise)
                    exercise_item.setFlags(
                        exercise_item.flags()
                        | Qt.ItemIsDragEnabled
                        | Qt.ItemIsDropEnabled
                    )

                # Inline "+ Add Exercise..." button under lesson
                add_ex_item = QTreeWidgetItem(lesson_item, ["+ Add Exercise..."])
                add_ex_item.setData(
                    0, Qt.UserRole, {"action": "add_exercise", "target": lesson}
                )
                add_ex_item.setForeground(0, QColor("#8888aa"))
                add_ex_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)

            # Inline "+ Add Lesson..." button under unit
            add_les_item = QTreeWidgetItem(unit_item, ["+ Add Lesson..."])
            add_les_item.setData(
                0, Qt.UserRole, {"action": "add_lesson", "target": unit}
            )
            add_les_item.setForeground(0, QColor("#8888aa"))
            add_les_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)

        if selected_item_data:
            self._expand_and_select_item(selected_item_data)

        # Reapply current filter after update_tree_view rebuilds it
        # This ensures that any active filters are maintained after a reorder operation.
        self._filter_tree_view(self.search_bar.text())

    def new_course(self):
        if self.is_dirty:
            reply = QMessageBox.question(
                self,
                "Unsaved Changes",
                "You have unsaved changes. Do you want to save them before creating a new course?",
                QMessageBox.StandardButton.Save
                | QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel,
            )
            if reply == QMessageBox.StandardButton.Save:
                if not self.save_course():
                    return
            elif reply == QMessageBox.StandardButton.Cancel:
                return

        self.manifest_data, self.course_data = create_new_course()
        self.current_manifest_path = None
        self.current_course_content_path = None
        self._update_context_paths()
        self.update_tree_view()
        self._set_dirty_state(False)
        self._clear_editor_pane()
        if self.tree_widget.topLevelItemCount() > 0:
            self.tree_widget.setCurrentItem(self.tree_widget.topLevelItem(0))
        self.item_actions_widget.setVisible(False)

        self.current_file_label.setText("New Course (Unsaved)")
        self._set_dirty_state(False)
        self.status_bar.showMessage("New course created.", 3000)

    def open_course(self):
        if self.is_dirty:
            reply = QMessageBox.question(
                self,
                "Unsaved Changes",
                "You have unsaved changes. Do you want to save them before opening a new course?",
                QMessageBox.StandardButton.Save
                | QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel,
            )
            if reply == QMessageBox.StandardButton.Save:
                if not self.save_course():
                    return
            elif reply == QMessageBox.StandardButton.Cancel:
                return

        manifest_file, _ = QFileDialog.getOpenFileName(
            self, "Open Manifest File", "", "YAML Files (*.yaml *.yml);;All Files (*)"
        )
        if not manifest_file:
            return

        self.current_manifest_path = manifest_file
        self.manifest_data = load_manifest(self.current_manifest_path)

        if not self.manifest_data:
            QMessageBox.critical(self, "Load Error", "Failed to load manifest file.")
            self._set_dirty_state(False)
            return

        content_filename = self.manifest_data.get("content_file")
        if not content_filename:
            QMessageBox.critical(
                self, "Load Error", "Manifest does not specify 'content_file'."
            )
            self._set_dirty_state(False)
            return

        manifest_dir = os.path.dirname(self.current_manifest_path)
        self.current_course_content_path = os.path.join(manifest_dir, content_filename)

        course_id = self.manifest_data.get("course_id", "unknown_course")
        course_title = self.manifest_data.get("course_title", "Untitled Course")
        target_lang = self.manifest_data.get("target_language", "Unknown Target")
        source_lang = self.manifest_data.get("source_language", "Unknown Source")
        version = self.manifest_data.get("version", "0.0.0")
        author = self.manifest_data.get("author")
        description = self.manifest_data.get("description")

        self.course_data = load_course_content_from_yaml(
            content_filepath=self.current_course_content_path,
            course_id=course_id,
            course_title=course_title,
            target_lang=target_lang,
            source_lang=source_lang,
            version=version,
            author=author,
            description=description,
            image_file=self.manifest_data.get("image_file"),
        )

        if not self.course_data:
            QMessageBox.critical(
                self, "Load Error", "Failed to load course content file."
            )
            self._set_dirty_state(False)
            return

        self._update_context_paths()
        self.update_tree_view()
        self._set_dirty_state(False)
        self._clear_editor_pane()
        if self.tree_widget.topLevelItemCount() > 0:
            self.tree_widget.setCurrentItem(self.tree_widget.topLevelItem(0))
        self.item_actions_widget.setVisible(False)

        self.current_file_label.setText(os.path.basename(self.current_manifest_path))
        self._set_dirty_state(False)
        self.status_bar.showMessage(f"Course '{self.course_data.title}' loaded.", 3000)

    def save_course(self):
        if not self.current_manifest_path or not self.current_course_content_path:
            return self.save_course_as()
        return self._do_save(
            self.current_manifest_path, self.current_course_content_path
        )

    def save_course_as(self):
        manifest_file, _ = QFileDialog.getSaveFileName(
            self,
            "Save Manifest File As",
            "manifest.yaml",
            "YAML Files (*.yaml *.yml);;All Files (*)",
        )
        if not manifest_file:
            return False

        manifest_dir = os.path.dirname(manifest_file)
        course_id_for_filename = self.manifest_data.get(
            "course_id", str(uuid.uuid4().hex[:8])
        )
        content_filename_from_manifest = self.manifest_data.get(
            "content_file", f"course_{course_id_for_filename}.yaml"
        )
        content_file_path = os.path.join(manifest_dir, content_filename_from_manifest)
        self.manifest_data["content_file"] = os.path.basename(content_file_path)
        return self._do_save(manifest_file, content_file_path)

    def _do_save(self, manifest_file: str, content_file: str):
        if not self.manifest_data or not self.course_data:
            QMessageBox.warning(self, "Save Error", "No course data to save.")
            return False

        if self.current_editor_widget == self.manifest_editor:
            self.manifest_editor.apply_changes_to_data(
                self.manifest_data, self.course_data
            )

        # It's better to always attempt to save glossary if it's been loaded
        # so changes in its tab are saved.
        if (
            self.glossary_editor.glossary_entries
        ):  # Only attempt if there's glossary data
            if not self.glossary_editor.save_glossary_data(
                self.manifest_data, self.current_manifest_path
            ):
                QMessageBox.critical(
                    self, "Save Error", "Failed to save glossary file."
                )
                return False

        if not yaml_serializer.save_manifest_to_yaml(self.manifest_data, manifest_file):
            QMessageBox.critical(self, "Save Error", "Failed to save manifest file.")
            return False

        course_data_to_save_dict = self.course_data.to_dict()
        try:
            with open(content_file, "w", encoding="utf-8") as f:
                yaml.safe_dump(
                    course_data_to_save_dict,
                    f,
                    indent=2,
                    sort_keys=False,
                    allow_unicode=True,
                )
        except Exception as e:
            QMessageBox.critical(
                self, "Save Error", f"Failed to save course content file: {e}"
            )
            return False

        self.current_manifest_path = manifest_file
        self.current_course_content_path = content_file
        self._update_context_paths()
        self.current_file_label.setText(os.path.basename(self.current_manifest_path))
        self._set_dirty_state(False)
        self.status_bar.showMessage("Course saved successfully!", 3000)
        QMessageBox.information(
            self, "Save Successful", "Course and Manifest saved successfully!"
        )
        return True

    def closeEvent(self, event):
        if self.is_dirty:
            reply = QMessageBox.question(
                self,
                "Unsaved Changes",
                "You have unsaved changes. Do you want to save them before exiting?",
                QMessageBox.StandardButton.Save
                | QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel,
            )
            if reply == QMessageBox.StandardButton.Save:
                if not self.save_course():
                    event.ignore()
                    return
            elif reply == QMessageBox.StandardButton.Cancel:
                event.ignore()
                return
        event.accept()

    def validate_current_course(self):
        if not self.manifest_data or not self.course_data:
            QMessageBox.warning(
                self, "Validation Error", "No course loaded to validate."
            )
            return
        if not self.current_manifest_path:
            QMessageBox.warning(
                self,
                "Validation Error",
                "Manifest path unknown. Please save the course first.",
            )
            return
        if self.is_dirty:
            reply = QMessageBox.question(
                self,
                "Unsaved Changes",
                "You have unsaved changes. It's recommended to save before validating. Save now?",
                QMessageBox.StandardButton.Save
                | QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel,
            )
            if reply == QMessageBox.StandardButton.Save:
                if not self.save_course():
                    return
            elif reply == QMessageBox.StandardButton.Cancel:
                return

        all_errors = []
        logger.info(f"Validating manifest: {self.current_manifest_path}")
        manifest_errors = perform_manifest_validation(
            self.manifest_data, self.current_manifest_path
        )
        all_errors.extend(manifest_errors)

        if self.current_course_content_path:
            course_content_base_dir = os.path.dirname(self.current_course_content_path)
            content_errors = perform_course_content_validation(
                self.course_data, course_content_base_dir
            )
            all_errors.extend(content_errors)
        else:
            all_errors.append(
                "Error: Course content path is unknown, cannot validate asset file paths."
            )

        logger.info(f"Validating course content for: {self.course_data.title}")

        if hasattr(self, "problems_drawer"):
            self.problems_drawer.set_issues(all_errors)
            if not self.problems_drawer.is_drawer_visible():
                self.problems_drawer.toggle_drawer()

        if not all_errors:
            self.status_bar.showMessage("Validation Successful! No errors found.", 4000)
            QMessageBox.information(
                self, "Validation Result", "Validation Successful! No errors found."
            )
        else:
            self.status_bar.showMessage(
                f"Validation found {len(all_errors)} issues. See Problems drawer below.",
                5000,
            )

    def import_from_csv(self):
        if not self.course_data or not self.manifest_data:
            QMessageBox.warning(
                self,
                "Import Error",
                "Please open or create a course first before importing CSV data.",
            )
            return
        if not self.current_course_content_path:
            QMessageBox.warning(
                self,
                "Import Error",
                "Course content file path is not set. Please save your course first.",
            )
            return

        selected_item = self.tree_widget.currentItem()
        default_unit_id, default_lesson_id = "", ""
        if selected_item:
            item_data = selected_item.data(0, Qt.UserRole)
            if isinstance(item_data, Lesson):
                default_lesson_id = item_data.lesson_id
                if item_data.unit_id:
                    default_unit_id = item_data.unit_id
            elif isinstance(item_data, Unit):
                default_unit_id = item_data.unit_id

        dialog = CsvImportDialog(self, default_unit_id, default_lesson_id)
        if dialog.exec() == QDialog.Accepted:
            data = dialog.get_data()
            course_dict_for_import = load_existing_course_data(
                self.current_course_content_path
            )
            if not course_dict_for_import:
                QMessageBox.critical(
                    self,
                    "Import Error",
                    f"Could not load current course content from {self.current_course_content_path}",
                )
                return

            success, messages = import_csv_data(
                csv_filepath=data["csv_filepath"],
                existing_course_data=course_dict_for_import,
                exercise_type=data["exercise_type"],
                unit_id=data["unit_id"],
                unit_title=data["unit_title"],
                lesson_id=data["lesson_id"],
                lesson_title=data["lesson_title"],
                **data["custom_cols"],
            )
            result_message = "\n".join(messages)
            if success:
                save_course_data(
                    course_dict_for_import, self.current_course_content_path
                )
                reloaded_course = load_course_content_from_yaml(
                    content_filepath=self.current_course_content_path,
                    course_id=self.manifest_data.get("course_id", "unknown_course"),
                    course_title=self.manifest_data.get("course_title", "Untitled Course"),
                    target_lang=self.manifest_data.get("target_language", "Unknown Target"),
                    source_lang=self.manifest_data.get("source_language", "Unknown Source"),
                    version=self.manifest_data.get("version", "0.0.0"),
                    author=self.manifest_data.get("author"),
                    description=self.manifest_data.get("description"),
                    image_file=self.manifest_data.get("image_file"),
                )
                if reloaded_course:
                    self.course_data = reloaded_course
                    self.update_tree_view()
                    self._set_dirty_state(False)
                    QMessageBox.information(
                        self,
                        "Import Successful",
                        f"CSV data imported.\n{result_message}",
                    )
                else:
                    QMessageBox.critical(
                        self,
                        "Import Error",
                        "CSV imported, but failed to reload course data into editor.",
                    )
            else:
                QMessageBox.warning(
                    self,
                    "Import Failed",
                    f"Could not import CSV data.\n{result_message}",
                )

    def create_course_package(self):
        if not self.current_manifest_path:
            QMessageBox.warning(
                self,
                "Packaging Error",
                "Please open or save a course (manifest) first.",
            )
            return

        default_package_name_stem = ""
        if self.manifest_data:
            course_id = self.manifest_data.get("course_id", "course").replace(" ", "_")
            version = self.manifest_data.get("version", "1.0").replace(" ", "_")
            default_package_name_stem = f"{course_id}_{version}"

        dialog = PackageCreationDialog(
            self, self.current_manifest_path, default_package_name_stem
        )
        if dialog.exec() == QDialog.Accepted:
            data = dialog.get_data()
            success, package_path, messages = create_package_for_gui(
                manifest_filepath=data["manifest_filepath"],
                output_dir_override=data["output_dir"],
                package_name_override=data["package_name_override"],
            )
            result_message = "\n".join(messages)
            if success and package_path:
                QMessageBox.information(
                    self,
                    "Packaging Successful",
                    f"Course packaged successfully!\nPackage at: {package_path}\n\nDetails:\n{result_message}\nUnzip it using 7zip and place it in the same folder as main.",
                )
            else:
                QMessageBox.critical(
                    self,
                    "Packaging Failed",
                    f"Could not create course package.\n\nDetails:\n{result_message}",
                )
