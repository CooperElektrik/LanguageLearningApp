import logging
import os
import uuid
from typing import Any

import yaml
from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QAction, QActionGroup, QColor, QUndoStack
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDockWidget,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QStackedWidget,
    QStyle,
    QTabWidget,
    QToolBar,
    QToolButton,
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
    from application.tools.widgets.inspector_header_widget import InspectorHeaderWidget
    from application.tools.widgets.lesson_editor_widget import LessonEditorWidget
    from application.tools.widgets.unit_editor_widget import UnitEditorWidget

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
        self._setup_ui()
        self._create_menu_bar()
        self._create_tool_bar()
        self._set_dirty_state(False)

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
        self.save_as_action.setStatusTip("Save the current course under a new name or location")
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
        view_menu.addSeparator()
        if hasattr(self, "preview_dock"):
            view_menu.addAction(self.preview_dock.toggleViewAction())
        if hasattr(self, "asset_dock"):
            view_menu.addAction(self.asset_dock.toggleViewAction())
        if hasattr(self, "problems_dock"):
            view_menu.addAction(self.problems_dock.toggleViewAction())

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
            self.status_bar.showMessage(f"Switched to {theme_name.capitalize()} Theme.", 3000)

        except FileNotFoundError:
            QMessageBox.warning(
                self, "Theme Error", f"Theme QSS file not found at: {qss_file_path}"
            )
            self.status_bar.showMessage(f"Error loading {theme_name} theme.", 3000)
            QApplication.instance().setStyleSheet("")
            self.dark_theme_action.setChecked(False)
            self.light_theme_action.setChecked(False)
        except Exception as e:
            QMessageBox.warning(self, "Theme Error", f"Failed to apply {theme_name} theme: {e}")
            self.status_bar.showMessage(f"Error applying {theme_name} theme.", 3000)
            QApplication.instance().setStyleSheet("")
            self.dark_theme_action.setChecked(False)
            self.light_theme_action.setChecked(False)

    def _setup_ui(self):
        self._editor_cache: dict[str, QWidget] = {}
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        outer_layout = QVBoxLayout(main_widget)
        outer_layout.setContentsMargins(12, 12, 12, 12)
        outer_layout.setSpacing(8)

        # 2-Pane Master-Detail Splitter
        self.master_splitter = QSplitter(Qt.Horizontal)
        self.master_splitter.setObjectName("MasterSplitter")
        self.splitter = self.master_splitter  # Backward-compatibility alias
        self.three_pane_splitter = self.master_splitter  # Backward-compatibility alias
        self.vertical_splitter = self.master_splitter  # Backward-compatibility alias

        # -------------------------------------------------------------
        # 1. Left Navigation Pane (Master Navigation)
        # -------------------------------------------------------------
        left_pane_widget = QWidget()
        left_pane_widget.setObjectName("LeftNavPane")
        left_pane_layout = QVBoxLayout(left_pane_widget)
        left_pane_layout.setContentsMargins(8, 8, 8, 8)
        left_pane_layout.setSpacing(8)

        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search or filter (e.g. type:mcq, missing:audio)...")
        self.search_bar.textChanged.connect(self._filter_tree_view)
        left_pane_layout.addWidget(self.search_bar)

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
        left_pane_layout.addLayout(chips_layout)

        # Navigation Action Strip Toolbar
        nav_toolbar_layout = QHBoxLayout()
        nav_toolbar_layout.setSpacing(4)

        # "Add Item" Dropdown ToolButton
        self.add_item_btn = QToolButton()
        self.add_item_btn.setText("+ Add Item ▾")
        self.add_item_btn.setProperty("primary", True)
        self.add_item_btn.setPopupMode(QToolButton.InstantPopup)
        self.add_item_menu = QMenu(self.add_item_btn)

        self.action_add_unit = QAction("+ Add Unit", self)
        self.action_add_unit.triggered.connect(lambda: self._add_unit())
        self.add_item_menu.addAction(self.action_add_unit)

        self.action_add_lesson = QAction("+ Add Lesson", self)
        self.action_add_lesson.triggered.connect(self._add_lesson_from_nav)
        self.add_item_menu.addAction(self.action_add_lesson)

        self.add_exercise_menu = self.add_item_menu.addMenu("+ Add Exercise")
        for ex_type in [
            "translate_to_target",
            "translate_to_source",
            "multiple_choice_translation",
            "fill_in_the_blank",
            "dictation",
            "image_association",
            "listen_and_select",
            "sentence_jumble",
            "context_block",
        ]:
            type_label = ex_type.replace("_", " ").title()
            act = QAction(type_label, self)
            act.triggered.connect(lambda checked=False, t=ex_type: self._add_exercise_from_nav(t))
            self.add_exercise_menu.addAction(act)

        self.add_item_btn.setMenu(self.add_item_menu)
        nav_toolbar_layout.addWidget(self.add_item_btn)

        # Reordering arrows
        self.move_up_btn = QPushButton("↑")
        self.move_up_btn.setToolTip("Move Item Up")
        self.move_up_btn.setFixedWidth(28)
        self.move_up_btn.clicked.connect(self._move_item_up)
        nav_toolbar_layout.addWidget(self.move_up_btn)

        self.move_down_btn = QPushButton("↓")
        self.move_down_btn.setToolTip("Move Item Down")
        self.move_down_btn.setFixedWidth(28)
        self.move_down_btn.clicked.connect(self._move_item_down)
        nav_toolbar_layout.addWidget(self.move_down_btn)

        self.move_up_button = self.move_up_btn
        self.move_down_button = self.move_down_btn

        # Expand / Collapse toggles
        self.expand_all_button = QPushButton("Expand All")
        self.expand_all_button.clicked.connect(lambda: self.tree_widget.expandAll() if hasattr(self, "tree_widget") else None)
        nav_toolbar_layout.addWidget(self.expand_all_button)

        self.collapse_all_button = QPushButton("Collapse All")
        self.collapse_all_button.clicked.connect(lambda: self.tree_widget.collapseAll() if hasattr(self, "tree_widget") else None)
        nav_toolbar_layout.addWidget(self.collapse_all_button)

        left_pane_layout.addLayout(nav_toolbar_layout)

        # Unified Course Tree Widget
        self.tree_widget = CourseTreeWidget(self.course_data, self)
        self.tree_widget.setHeaderLabels(["Course Structure"])
        self.tree_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree_widget.customContextMenuRequested.connect(self._show_context_menu)
        self.tree_widget.itemSelectionChanged.connect(self._on_tree_item_selected)
        self.tree_widget.data_model_reordered.connect(self._handle_data_model_reordered)
        left_pane_layout.addWidget(self.tree_widget, 1)

        self.master_splitter.addWidget(left_pane_widget)

        # -------------------------------------------------------------
        # 2. Right Pane (Contextual Inspector Pane)
        # -------------------------------------------------------------
        center_pane_widget = QWidget()
        center_pane_widget.setObjectName("CenterInspectorPane")
        center_pane_layout = QVBoxLayout(center_pane_widget)
        center_pane_layout.setContentsMargins(8, 8, 8, 8)
        center_pane_layout.setSpacing(8)

        # Reusable Inspector Header Banner
        self.inspector_header = InspectorHeaderWidget(self)
        center_pane_layout.addWidget(self.inspector_header)

        # Detail Editors Stacked Widget wrapped in QScrollArea
        self.detail_editor_stacked_widget = QStackedWidget()
        self.detail_editor_stacked_widget.setObjectName("DetailEditorStackedWidget")

        self._placeholder_editor_widget = QLabel("Select an item in the navigation tree to edit its properties.")
        self._placeholder_editor_widget.setAlignment(Qt.AlignCenter)
        self._placeholder_editor_widget.setStyleSheet("color: #888899; font-style: italic; font-size: 11pt;")
        self.detail_editor_stacked_widget.addWidget(self._placeholder_editor_widget)

        self.manifest_editor = ManifestEditorWidget()
        self.manifest_editor.data_changed.connect(self._set_dirty_state)
        self.detail_editor_stacked_widget.addWidget(self.manifest_editor)

        self.glossary_editor = GlossaryEditorWidget()
        self.glossary_editor.data_changed.connect(self._set_dirty_state)
        self.detail_editor_stacked_widget.addWidget(self.glossary_editor)

        self.inspector_scroll_area = QScrollArea()
        self.inspector_scroll_area.setObjectName("InspectorScrollArea")
        self.inspector_scroll_area.setWidgetResizable(True)
        self.inspector_scroll_area.setFrameShape(QFrame.NoFrame)
        self.inspector_scroll_area.setWidget(self.detail_editor_stacked_widget)
        center_pane_layout.addWidget(self.inspector_scroll_area, 1)

        # Scoped Inspector Action Bar
        self.item_actions_widget = QWidget()
        item_actions_layout = QHBoxLayout(self.item_actions_widget)
        item_actions_layout.setContentsMargins(0, 4, 0, 0)
        item_actions_layout.setSpacing(8)

        self.preview_exercise_button = QPushButton("Preview Exercise ▶")
        self.preview_exercise_button.clicked.connect(self._preview_exercise)

        self.revert_button = QPushButton("Revert Changes ↺")
        self.revert_button.clicked.connect(self._revert_active_item)

        self.delete_item_button = QPushButton("Delete Item ✕")
        self.delete_item_button.clicked.connect(self._delete_active_item)

        item_actions_layout.addStretch(1)
        item_actions_layout.addWidget(self.preview_exercise_button)
        item_actions_layout.addWidget(self.revert_button)
        item_actions_layout.addWidget(self.delete_item_button)

        center_pane_layout.addWidget(self.item_actions_widget)
        self.item_actions_widget.setVisible(False)

        self.master_splitter.addWidget(center_pane_widget)
        self.master_splitter.setSizes([340, 860])
        outer_layout.addWidget(self.master_splitter)

        # -------------------------------------------------------------
        # 3. Peripheral Dock Widgets (QDockWidget)
        # -------------------------------------------------------------
        # Live Preview Dock
        self.live_preview_pane = LivePreviewPane(self)
        self.preview_dock = QDockWidget("Live Preview", self)
        self.preview_dock.setObjectName("LivePreviewDock")
        self.preview_dock.setWidget(self.live_preview_pane)
        self.addDockWidget(Qt.RightDockWidgetArea, self.preview_dock)

        # Asset Hub Dock
        self.asset_hub = AssetHubWidget(course_root_dir=None, parent=self)
        self.asset_hub.asset_selected.connect(self._handle_asset_hub_selected)
        self.asset_dock = QDockWidget("Asset Hub", self)
        self.asset_dock.setObjectName("AssetHubDock")
        self.asset_dock.setWidget(self.asset_hub)
        self.addDockWidget(Qt.RightDockWidgetArea, self.asset_dock)
        self.tabifyDockWidget(self.preview_dock, self.asset_dock)
        self.preview_dock.raise_()

        # Problems & Validation Drawer Dock
        self.problems_drawer = ProblemsDrawer(self)
        self.problems_drawer.validate_requested.connect(self.validate_current_course)
        self.problems_drawer.issue_selected.connect(self._navigate_to_validation_issue)
        self.problems_dock = QDockWidget("Problems & Validation", self)
        self.problems_dock.setObjectName("ProblemsDock")
        self.problems_dock.setWidget(self.problems_drawer)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.problems_dock)
        self.problems_dock.setVisible(False)

        # Status Bar
        self.status_bar = self.statusBar()
        self.current_file_label = QLabel("No course loaded")
        self.dirty_status_label = QLabel("")
        self.dirty_status_label.setStyleSheet("padding-right: 10px;")

        self.status_bar.addPermanentWidget(self.current_file_label, stretch=1)
        self.status_bar.addPermanentWidget(self.dirty_status_label)

        self.current_editor_widget = None
        self.current_selected_tree_item = None

    def _handle_asset_hub_selected(self, asset_path: str):
        """Inserts selected asset path into the active exercise input if applicable."""
        if not self.current_editor_widget:
            return
        if asset_path.endswith((".mp3", ".wav", ".ogg", ".flac", ".m4a")):
            target_attr = getattr(self.current_editor_widget, "audio_file_edit", None) or getattr(
                self.current_editor_widget, "audio_edit", None
            )
            if target_attr and hasattr(target_attr, "setText"):
                target_attr.setText(asset_path)
                self.status_bar.showMessage(f"Asset assigned: {asset_path}", 3000)
                return
        elif asset_path.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg")):
            target_attr = getattr(self.current_editor_widget, "image_file_edit", None) or getattr(
                self.current_editor_widget, "image_edit", None
            )
            if target_attr and hasattr(target_attr, "setText"):
                target_attr.setText(asset_path)
                self.status_bar.showMessage(f"Asset assigned: {asset_path}", 3000)
                return
        self.status_bar.showMessage(f"Asset selected: {asset_path}", 2000)

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

    def _add_lesson_from_nav(self):
        """Adds a new lesson to the currently selected Unit or parent of selected Lesson/Exercise."""
        if not self.tree_widget or not self.course_data:
            return
        item = self.tree_widget.currentItem()
        target_unit = None
        if item:
            item_data = item.data(0, Qt.UserRole)
            if isinstance(item_data, Unit):
                target_unit = item_data
            elif isinstance(item_data, Lesson):
                p = item.parent()
                if p:
                    target_unit = p.data(0, Qt.UserRole)
            elif isinstance(item_data, Exercise):
                p = item.parent()
                if p and p.parent():
                    target_unit = p.parent().data(0, Qt.UserRole)
        if not target_unit and self.course_data.units:
            target_unit = self.course_data.units[-1]
        if target_unit:
            self._add_lesson(target_unit)
        else:
            self._add_unit()

    def _add_exercise_from_nav(self, exercise_type: str = "translate_to_target"):
        """Adds a new exercise to the currently selected Lesson or parent of selected Exercise."""
        if not self.tree_widget or not self.course_data:
            return
        item = self.tree_widget.currentItem()
        target_lesson = None
        if item:
            item_data = item.data(0, Qt.UserRole)
            if isinstance(item_data, Lesson):
                target_lesson = item_data
            elif isinstance(item_data, Exercise):
                p = item.parent()
                if p:
                    target_lesson = p.data(0, Qt.UserRole)
            elif isinstance(item_data, Unit) and item_data.lessons:
                target_lesson = item_data.lessons[-1]
        if not target_lesson:
            for u in self.course_data.units:
                if u.lessons:
                    target_lesson = u.lessons[-1]
                    break
        if target_lesson:
            self._add_exercise(target_lesson, exercise_type)

    def _revert_active_item(self):
        """Reverts uncommitted changes in the active inspector editor."""
        if not self.current_selected_tree_item:
            return
        item_data = self.current_selected_tree_item.data(0, Qt.UserRole)
        if hasattr(self.current_editor_widget, "revert"):
            self.current_editor_widget.revert()
            self._set_dirty_state(False)
            self.status_bar.showMessage("Reverted changes to current item.", 2000)
        elif isinstance(item_data, Exercise):
            self._display_item_editor(item_data)
            self._set_dirty_state(False)
            self.status_bar.showMessage("Reverted exercise changes.", 2000)

    def _delete_active_item(self):
        """Deletes the active Unit, Lesson, or Exercise from the course hierarchy."""
        if not self.current_selected_tree_item:
            return
        item_data = self.current_selected_tree_item.data(0, Qt.UserRole)
        if isinstance(item_data, Exercise):
            self._delete_exercise(self.current_selected_tree_item)
        elif isinstance(item_data, Lesson):
            self._delete_lesson(self.current_selected_tree_item)
        elif isinstance(item_data, Unit):
            self._delete_unit(self.current_selected_tree_item)

    def _navigate_to_validation_issue(self, issue: Any):
        issue_str = str(issue)
        entity_type = getattr(issue, "entity_type", None)
        unit_id = getattr(issue, "unit_id", None)
        lesson_id = getattr(issue, "lesson_id", None)
        exercise_id = getattr(issue, "exercise_id", None)
        field = getattr(issue, "field", None)

        if hasattr(self, "problems_dock") and not self.problems_dock.isVisible():
            self.problems_dock.setVisible(True)

        if entity_type == "manifest" or (
            not unit_id and not lesson_id and not exercise_id and "manifest" in issue_str.lower()
        ):
            if self.tree_widget.topLevelItemCount() > 0:
                self.tree_widget.setCurrentItem(self.tree_widget.topLevelItem(0))
                if hasattr(self.manifest_editor, "focus_field"):
                    self.manifest_editor.focus_field(field)
            self.status_bar.showMessage(f"Navigated to: {issue_str[:80]}", 3000)
            return

        if entity_type == "glossary" or "glossary" in issue_str.lower():
            if self.tree_widget.topLevelItemCount() > 1:
                self.tree_widget.setCurrentItem(self.tree_widget.topLevelItem(1))
                if hasattr(self.glossary_editor, "focus_field"):
                    self.glossary_editor.focus_field(field)
            self.status_bar.showMessage(f"Navigated to: {issue_str[:80]}", 3000)
            return

        if not self.course_data:
            return

        target_obj = None
        if exercise_id:
            for unit in self.course_data.units:
                for lesson in unit.lessons:
                    for ex in lesson.exercises:
                        if ex.exercise_id == exercise_id:
                            target_obj = ex
                            break
                    if target_obj:
                        break
                if target_obj:
                    break

        if not target_obj and lesson_id:
            for unit in self.course_data.units:
                for lesson in unit.lessons:
                    if lesson.lesson_id == lesson_id:
                        target_obj = lesson
                        break
                if target_obj:
                    break

        if not target_obj and unit_id:
            for unit in self.course_data.units:
                if unit.unit_id == unit_id:
                    target_obj = unit
                    break

        if not target_obj:
            for unit in self.course_data.units:
                if "Exercise" in issue_str:
                    for lesson in unit.lessons:
                        for ex in lesson.exercises:
                            if ex.exercise_id and ex.exercise_id in issue_str:
                                target_obj = ex
                                break
                        if target_obj:
                            break
                if target_obj:
                    break
                if "Lesson" in issue_str:
                    for lesson in unit.lessons:
                        if lesson.lesson_id and lesson.lesson_id in issue_str:
                            target_obj = lesson
                            break
                    if target_obj:
                        break
                if unit.unit_id and unit.unit_id in issue_str:
                    target_obj = unit
                    break

        if target_obj:
            self._expand_and_select_item(target_obj)
            self.status_bar.showMessage(f"Navigated to: {issue_str[:80]}", 3000)
            if self.current_editor_widget and hasattr(self.current_editor_widget, "focus_field"):
                self.current_editor_widget.focus_field(field)
            elif field and self.current_editor_widget:
                for attr_name in [f"{field}_edit", f"{field}_input", field]:
                    w = getattr(self.current_editor_widget, attr_name, None)
                    if w and hasattr(w, "setFocus"):
                        w.setFocus()
                        mark_widget_validity(w, False)
                        break
            if hasattr(self, "inspector_header"):
                self.inspector_header.status_label.setText("● Validation Issue")
                self.inspector_header.status_label.setStyleSheet(
                    "color: #e74c3c; font-weight: 600; font-size: 9pt;"
                )

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
                    searchable = " ".join(
                        [
                            getattr(ex, "prompt", "") or "",
                            getattr(ex, "title", "") or "",
                            getattr(ex, "answer", "") or "",
                            getattr(ex, "source_word", "") or "",
                            getattr(ex, "sentence_template", "") or "",
                            getattr(ex, "explanation", "") or "",
                        ]
                    ).lower()
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

    def _update_context_paths(self):
        course_root = None
        if self.current_manifest_path:
            course_root = os.path.dirname(self.current_manifest_path)
        elif self.current_course_content_path:
            course_root = os.path.dirname(self.current_course_content_path)
        if hasattr(self, "asset_hub"):
            self.asset_hub.set_course_root_dir(course_root)

    def _set_dirty_state(self, dirty: bool = True):
        try:
            self.is_dirty = dirty
            self.setWindowTitle(
                f"LL Course Editor{' *' if dirty else ''} - "
                f"{os.path.basename(self.current_manifest_path) if self.current_manifest_path else 'New Course'}"
            )
            if hasattr(self, "dirty_status_label"):
                if dirty:
                    self.dirty_status_label.setText("Unsaved Changes*")
                    self.dirty_status_label.setStyleSheet(
                        "color: orange; padding-right: 10px; font-weight: bold;"
                    )
                else:
                    self.dirty_status_label.setText("Saved")
                    self.dirty_status_label.setStyleSheet("color: green; padding-right: 10px;")

            if hasattr(self, "inspector_header"):
                if dirty:
                    self.inspector_header.status_label.setText("● Unsaved Changes*")
                    self.inspector_header.status_label.setStyleSheet(
                        "color: #f39c12; font-weight: 600; font-size: 9pt;"
                    )
                else:
                    self.inspector_header.status_label.setText("● Saved")
                    self.inspector_header.status_label.setStyleSheet(
                        "color: #27ae60; font-weight: 600; font-size: 9pt;"
                    )
        except RuntimeError:
            pass

    def _flush_active_editor(self):
        """Ensure active editor widgets flush their uncommitted data before saving or switching."""
        if hasattr(self, "manifest_editor") and self.manifest_editor:
            if (
                self.current_editor_widget == self.manifest_editor
                or getattr(self.manifest_editor, "current_manifest_data", None) is not None
            ):
                if self.manifest_data is not None and self.course_data is not None:
                    self.manifest_editor.apply_changes_to_data(self.manifest_data, self.course_data)

        if hasattr(self, "current_editor_widget") and self.current_editor_widget:
            if self.current_editor_widget != getattr(self, "manifest_editor", None) and hasattr(
                self.current_editor_widget, "apply_changes_to_data"
            ):
                self.current_editor_widget.apply_changes_to_data(
                    self.manifest_data, self.course_data
                )
            elif hasattr(self.current_editor_widget, "flush"):
                self.current_editor_widget.flush()

    def _clear_editor_cache(self):
        """Clears cached editor widgets to prevent memory leaks and stale state."""
        if hasattr(self, "_editor_cache"):
            for _key, widget in list(self._editor_cache.items()):
                if hasattr(self, "detail_editor_stacked_widget") and widget not in (
                    getattr(self, "_placeholder_editor_widget", None),
                    getattr(self, "manifest_editor", None),
                    getattr(self, "glossary_editor", None),
                ):
                    self.detail_editor_stacked_widget.removeWidget(widget)
                    widget.deleteLater()
            self._editor_cache.clear()

    def _display_item_editor(self, item_data: Any):
        self._flush_active_editor()
        if not hasattr(self, "_editor_cache"):
            self._editor_cache = {}

        if isinstance(item_data, dict) and item_data.get("type") == "manifest":
            self.current_editor_widget = self.manifest_editor
            self.manifest_editor.load_data(
                item_data.get("manifest_data", {}) or (self.manifest_data or {}),
                item_data.get("course_obj", self.course_data),
                os.path.dirname(self.current_manifest_path) if self.current_manifest_path else None,
            )
            self.detail_editor_stacked_widget.setCurrentWidget(self.manifest_editor)
            self.live_preview_pane.update_preview(None)
        elif isinstance(item_data, dict) and item_data.get("type") == "glossary":
            self.current_editor_widget = self.glossary_editor
            self.glossary_editor.load_glossary_data(self.manifest_data, self.current_manifest_path)
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
            persistent_id = getattr(item_data, "exercise_id", None) or getattr(
                item_data, "id", None
            )
            cache_key = (
                f"exercise_{persistent_id}" if persistent_id else f"exercise_{id(item_data)}"
            )
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
        self._flush_active_editor()
        self.current_editor_widget = None
        if hasattr(self, "_placeholder_editor_widget"):
            self.detail_editor_stacked_widget.setCurrentWidget(self._placeholder_editor_widget)

    def _populate_unit_editor_widget(self, widget: QWidget, unit: Unit):
        if hasattr(widget, "load_unit"):
            widget.load_unit(unit)
        else:
            widget.unit_id_edit.setText(unit.unit_id)
            widget.unit_title_edit.setText(unit.title)

    def _populate_lesson_editor_widget(self, widget: QWidget, lesson: Lesson):
        if hasattr(widget, "load_lesson"):
            widget.load_lesson(lesson)
        else:
            widget.lesson_id_edit.setText(lesson.lesson_id)
            widget.lesson_title_edit.setText(lesson.title)

    def _validate_line_edit_required(self, input_widget: QLineEdit, is_required: bool):
        if not is_required:
            mark_widget_validity(input_widget, True)
            return
        text = input_widget.text().strip()
        mark_widget_validity(input_widget, bool(text))
        self._set_dirty_state(True)

    def _create_unit_editor_widget(self, unit: Unit):
        widget = UnitEditorWidget(self)
        widget.load_unit(unit)
        widget.data_changed.connect(lambda: self._set_dirty_state(True))
        widget.title_changed.connect(self._handle_active_unit_title_changed)
        return widget

    def _handle_active_unit_title_changed(self, new_title: str):
        if (
            self.current_selected_tree_item
            and isinstance(self.current_selected_tree_item.data(0, Qt.UserRole), Unit)
        ):
            self.current_selected_tree_item.setText(0, new_title)
        if hasattr(self, "inspector_header"):
            course_title = (self.course_data.title if self.course_data else "Course")
            self.inspector_header.set_context(
                "Unit",
                [course_title, new_title or "Untitled Unit"],
                new_title or "Untitled Unit",
                is_dirty=self.is_dirty,
            )

    def _update_unit_title(self, unit: Unit, new_title: str):
        unit.title = new_title.strip()
        self._set_dirty_state(True)
        if (
            self.current_selected_tree_item
            and self.current_selected_tree_item.data(0, Qt.UserRole) is unit
        ):
            self.current_selected_tree_item.setText(0, new_title.strip())

    def _create_lesson_editor_widget(self, lesson: Lesson):
        widget = LessonEditorWidget(self)
        widget.load_lesson(lesson)
        widget.data_changed.connect(lambda: self._set_dirty_state(True))
        widget.title_changed.connect(self._handle_active_lesson_title_changed)
        return widget

    def _handle_active_lesson_title_changed(self, new_title: str):
        if (
            self.current_selected_tree_item
            and isinstance(self.current_selected_tree_item.data(0, Qt.UserRole), Lesson)
        ):
            self.current_selected_tree_item.setText(0, new_title)
        if hasattr(self, "inspector_header"):
            course_title = (self.course_data.title if self.course_data else "Course")
            unit_title = (
                self.current_selected_tree_item.parent().text(0)
                if self.current_selected_tree_item and self.current_selected_tree_item.parent()
                else "Unit"
            )
            self.inspector_header.set_context(
                "Lesson",
                [course_title, unit_title, new_title or "Untitled Lesson"],
                new_title or "Untitled Lesson",
                is_dirty=self.is_dirty,
            )

    def _update_lesson_title(self, lesson: Lesson, new_title: str):
        lesson.title = new_title.strip()
        self._set_dirty_state(True)
        if (
            self.current_selected_tree_item
            and self.current_selected_tree_item.data(0, Qt.UserRole) is lesson
        ):
            self.current_selected_tree_item.setText(0, new_title.strip())

    def _create_exercise_editor_widget(self, exercise: Exercise):
        target_lang = self.course_data.target_language if self.course_data else "Target Language"
        source_lang = self.course_data.source_language if self.course_data else "Source Language"

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

        if exercise.type == "translate_to_target" or exercise.type == "translate_to_source":
            widget = TranslationExerciseEditorWidget(
                exercise, target_lang, source_lang, course_root_dir
            )
        elif exercise.type == "multiple_choice_translation":
            widget = MultipleChoiceExerciseEditorWidget(exercise, target_lang, source_lang)
        elif exercise.type == "fill_in_the_blank":
            widget = FillInTheBlankExerciseEditorWidget(exercise, target_lang, source_lang)
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
            if hasattr(self, "inspector_header"):
                self.inspector_header.setVisible(False)
            return

        self.current_selected_tree_item = selected_items[0]
        item_data = self.current_selected_tree_item.data(0, Qt.UserRole)
        self._display_item_editor(item_data)

        course_title = (self.manifest_data.get("course_title") if self.manifest_data else None) or (
            self.course_data.title if self.course_data else "Course"
        )

        if isinstance(item_data, dict) and item_data.get("type") == "manifest":
            self.item_actions_widget.setVisible(True)
            self.preview_exercise_button.setVisible(False)
            self.delete_item_button.setVisible(False)
            self.revert_button.setVisible(True)
            self.move_up_btn.setEnabled(False)
            self.move_down_btn.setEnabled(False)
            if hasattr(self, "inspector_header"):
                self.inspector_header.setVisible(True)
                self.inspector_header.set_context(
                    "Settings",
                    [course_title, "Settings"],
                    course_title,
                    is_dirty=self.is_dirty,
                )
        elif isinstance(item_data, dict) and item_data.get("type") == "glossary":
            self.item_actions_widget.setVisible(True)
            self.preview_exercise_button.setVisible(False)
            self.delete_item_button.setVisible(False)
            self.revert_button.setVisible(True)
            self.move_up_btn.setEnabled(False)
            self.move_down_btn.setEnabled(False)
            if hasattr(self, "inspector_header"):
                self.inspector_header.setVisible(True)
                self.inspector_header.set_context(
                    "Glossary",
                    [course_title, "Glossary"],
                    "Course Glossary",
                    is_dirty=self.is_dirty,
                )
        elif isinstance(item_data, (Unit, Lesson, Exercise)):
            self.item_actions_widget.setVisible(True)
            self.preview_exercise_button.setVisible(isinstance(item_data, Exercise))
            self.delete_item_button.setVisible(True)
            self.revert_button.setVisible(True)

            parent_list, current_index = self._get_item_list_and_index(item_data)
            can_up = parent_list is not None and current_index is not None and current_index > 0
            can_down = (
                parent_list is not None
                and current_index is not None
                and current_index < len(parent_list) - 1
            )
            self.move_up_btn.setEnabled(can_up)
            self.move_down_btn.setEnabled(can_down)

            if hasattr(self, "inspector_header"):
                self.inspector_header.setVisible(True)
                if isinstance(item_data, Unit):
                    self.inspector_header.set_context(
                        "Unit",
                        [course_title, item_data.title or "Untitled Unit"],
                        item_data.title or "Untitled Unit",
                        is_dirty=self.is_dirty,
                    )
                elif isinstance(item_data, Lesson):
                    unit_item = self.current_selected_tree_item.parent()
                    unit_title = unit_item.text(0) if unit_item else "Unit"
                    self.inspector_header.set_context(
                        "Lesson",
                        [course_title, unit_title, item_data.title or "Untitled Lesson"],
                        item_data.title or "Untitled Lesson",
                        is_dirty=self.is_dirty,
                    )
                elif isinstance(item_data, Exercise):
                    lesson_item = self.current_selected_tree_item.parent()
                    unit_item = lesson_item.parent() if lesson_item else None
                    unit_title = unit_item.text(0) if unit_item else "Unit"
                    lesson_title = lesson_item.text(0) if lesson_item else "Lesson"
                    type_label = item_data.type.replace("_", " ").title()
                    ex_name = (
                        getattr(item_data, "title", "")
                        or getattr(item_data, "prompt", "")
                        or getattr(item_data, "source_word", "")
                        or f"Exercise ({type_label})"
                    )
                    self.inspector_header.set_context(
                        type_label,
                        [course_title, unit_title, lesson_title, type_label],
                        ex_name,
                        is_dirty=self.is_dirty,
                    )
        else:
            self.item_actions_widget.setVisible(False)
            self.move_up_btn.setEnabled(False)
            self.move_down_btn.setEnabled(False)
            if hasattr(self, "inspector_header"):
                self.inspector_header.setVisible(False)

    def _get_item_list_and_index(self, item_data_obj: Any) -> tuple[list | None, int | None]:
        """Helper to get the list and index of an item for reordering."""
        if isinstance(item_data_obj, Unit):
            try:
                return self.course_data.units, self.course_data.units.index(item_data_obj)
            except ValueError:
                return None, None
        elif isinstance(item_data_obj, Lesson):
            parent_unit_item = self.current_selected_tree_item.parent()
            if parent_unit_item:
                parent_unit: Unit = parent_unit_item.data(0, Qt.UserRole)
                if parent_unit and isinstance(parent_unit, Unit):
                    try:
                        return parent_unit.lessons, parent_unit.lessons.index(item_data_obj)
                    except ValueError:
                        return None, None
        elif isinstance(item_data_obj, Exercise):
            parent_lesson_item = self.current_selected_tree_item.parent()
            if parent_lesson_item:
                parent_lesson: Lesson = parent_lesson_item.data(0, Qt.UserRole)
                if parent_lesson and isinstance(parent_lesson, Lesson):
                    try:
                        return parent_lesson.exercises, parent_lesson.exercises.index(item_data_obj)
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
                duplicate_unit_action.triggered.connect(lambda: self._duplicate_unit(item))
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
                duplicate_lesson_action.triggered.connect(lambda: self._duplicate_lesson(item))
                menu.addAction(duplicate_lesson_action)
                menu.addSeparator()

                delete_lesson_action = QAction("Delete Lesson", self)
                delete_lesson_action.triggered.connect(lambda: self._delete_lesson(item))
                menu.addAction(delete_lesson_action)
            elif isinstance(item_data, Exercise):
                duplicate_exercise_action = QAction("Duplicate Exercise", self)
                duplicate_exercise_action.triggered.connect(lambda: self._duplicate_exercise(item))
                menu.addAction(duplicate_exercise_action)
                menu.addSeparator()

                delete_exercise_action = QAction("Delete Exercise", self)
                delete_exercise_action.triggered.connect(lambda: self._delete_exercise(item))
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
            "target": (self.course_data.target_language if self.course_data else "Target Language"),
            "source": (self.course_data.source_language if self.course_data else "Source Language"),
        }
        course_content_base_dir = None
        if self.current_course_content_path:
            course_content_base_dir = os.path.dirname(self.current_course_content_path)

        dialog = ExercisePreviewDialog(item_data, course_languages, course_content_base_dir, self)
        dialog.exec()

    def _expand_and_select_item(self, item_data_obj: Any):
        def find_and_select(parent_item, target_data_obj):
            for i in range(parent_item.childCount()):
                child_item = parent_item.child(i)
                data = child_item.data(0, Qt.UserRole)
                if data is target_data_obj:
                    self.tree_widget.setCurrentItem(child_item)
                    self.tree_widget.expandItem(parent_item)
                    if child_item.childCount() > 0:
                        self.tree_widget.expandItem(child_item)
                    self.tree_widget.scrollToItem(child_item)
                    return True
                if isinstance(data, dict) and isinstance(target_data_obj, dict):
                    if data.get("type") and data.get("type") == target_data_obj.get("type"):
                        self.tree_widget.setCurrentItem(child_item)
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

        # 1. Course Settings (Manifest) Root Item
        manifest_item = QTreeWidgetItem(self.tree_widget, ["⚙ Course Settings"])
        manifest_item.setData(
            0,
            Qt.UserRole,
            {"type": "manifest", "manifest_data": self.manifest_data, "course_obj": self.course_data},
        )
        manifest_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)

        # 2. Course Glossary Root Item
        glossary_item = QTreeWidgetItem(self.tree_widget, ["📖 Course Glossary"])
        glossary_item.setData(0, Qt.UserRole, {"type": "glossary"})
        glossary_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)

        # 3. Units, Lessons, Exercises
        for unit in self.course_data.units:
            unit_item = QTreeWidgetItem(self.tree_widget, [unit.title])
            unit_item.setData(0, Qt.UserRole, unit)
            unit_item.setFlags(
                unit_item.flags() | Qt.ItemFlag.ItemIsDragEnabled | Qt.ItemFlag.ItemIsDropEnabled
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
                if id(lesson) in expanded_items_data and expanded_items_data[id(lesson)]:
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
                        exercise_item.flags() | Qt.ItemIsDragEnabled | Qt.ItemIsDropEnabled
                    )

        if selected_item_data:
            self._expand_and_select_item(selected_item_data)
        elif self.tree_widget.topLevelItemCount() > 0:
            self.tree_widget.setCurrentItem(self.tree_widget.topLevelItem(0))

        # Reapply current filter after update_tree_view rebuilds it
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

        self._clear_editor_cache()
        if hasattr(self, "manifest_editor") and self.manifest_editor:
            self.manifest_editor.current_manifest_data = None
            self.manifest_editor.current_course_obj = None
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
            QMessageBox.critical(self, "Load Error", "Manifest does not specify 'content_file'.")
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
            QMessageBox.critical(self, "Load Error", "Failed to load course content file.")
            self._set_dirty_state(False)
            return

        self._clear_editor_cache()
        if hasattr(self, "manifest_editor") and self.manifest_editor:
            self.manifest_editor.current_manifest_data = None
            self.manifest_editor.current_course_obj = None

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
        return self._do_save(self.current_manifest_path, self.current_course_content_path)

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
        course_id_for_filename = self.manifest_data.get("course_id", str(uuid.uuid4().hex[:8]))
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

        self._flush_active_editor()

        # It's better to always attempt to save glossary if it's been loaded
        # so changes in its tab are saved.
        if self.glossary_editor.glossary_entries:  # Only attempt if there's glossary data
            if not self.glossary_editor.save_glossary_data(
                self.manifest_data, self.current_manifest_path
            ):
                QMessageBox.critical(self, "Save Error", "Failed to save glossary file.")
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
            QMessageBox.critical(self, "Save Error", f"Failed to save course content file: {e}")
            return False

        self.current_manifest_path = manifest_file
        self.current_course_content_path = content_file
        self._update_context_paths()
        self.current_file_label.setText(os.path.basename(self.current_manifest_path))
        self._set_dirty_state(False)
        self.status_bar.showMessage("Course saved successfully!", 3000)
        QMessageBox.information(self, "Save Successful", "Course and Manifest saved successfully!")
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
        self._clear_editor_cache()
        event.accept()

    def validate_current_course(self):
        if not self.manifest_data or not self.course_data:
            QMessageBox.warning(self, "Validation Error", "No course loaded to validate.")
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

        if hasattr(self, "problems_dock"):
            self.problems_dock.setVisible(True)
            self.problems_dock.raise_()

        if hasattr(self, "problems_drawer"):
            self.problems_drawer.set_issues(all_errors)
            if hasattr(self.problems_drawer, "is_drawer_visible") and not self.problems_drawer.is_drawer_visible():
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
            course_dict_for_import = load_existing_course_data(self.current_course_content_path)
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
                save_course_data(course_dict_for_import, self.current_course_content_path)
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

        dialog = PackageCreationDialog(self, self.current_manifest_path, default_package_name_stem)
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
