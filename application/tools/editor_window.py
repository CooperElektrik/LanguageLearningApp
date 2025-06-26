import os
import uuid
import logging
import sys
import copy
from typing import Any, Optional, List
import yaml
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTreeWidgetItem,
    QStackedWidget,
    QPushButton,
    QFileDialog,
    QMessageBox,
    QLabel,
    QInputDialog,
    QSplitter,
    QComboBox,
    QMenu,
    QTextEdit,
    QDialog,
    QFrame,
    QLineEdit,
    QTreeWidgetItemIterator,
    QStyle,
    QToolBar,
    QApplication,
    QGroupBox,
)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QAction, QFont, QActionGroup

try:
    from application.core.models import Course, Unit, Lesson, Exercise, ExerciseOption
    from application.core.course_loader import (
        load_course_content as load_course_content_from_yaml,
    )
    from .dialogs.exercise_preview_dialog import ExercisePreviewDialog
    from .widgets.course_tree_widget import CourseTreeWidget
    from application.tools.widgets.glossary_editor_widget import GlossaryEditorWidget
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


from .yaml_manager import load_manifest, save_manifest, create_new_course
from .widgets.manifest_editor_widget import ManifestEditorWidget
from .widgets.exercise_editor_widgets import (
    TranslationExerciseEditorWidget,
    MultipleChoiceExerciseEditorWidget,
    FillInTheBlankExerciseEditorWidget,
    BaseExerciseEditorWidget,
    DictationExerciseEditorWidget,
    ImageAssociationExerciseEditorWidget,
    ListenAndSelectExerciseEditorWidget,
    SentenceJumbleExerciseEditorWidget,
    ContextBlockExerciseEditorWidget,
)
from .dialogs.csv_import_dialog import CsvImportDialog
from .dialogs.package_creation_dialog import PackageCreationDialog
from .course_validator import (
    perform_manifest_validation,
    perform_course_content_validation,
)
from .csv_importer import import_csv_data, load_existing_course_data, save_course_data
from .course_packager import create_package_for_gui


logger = logging.getLogger(__name__)

_current_script_dir = os.path.dirname(os.path.abspath(__file__))
_dark_theme_qss_path = os.path.join(_current_script_dir, "styles", "dark_theme.qss")
_light_theme_qss_path = os.path.join(_current_script_dir, "styles", "light_theme.qss")


class EditorWindow(QMainWindow):
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
            with open(qss_file_path, "r", encoding="utf-8") as f:
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

        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setObjectName("EditorSplitter")

        left_pane_widget = QWidget()
        left_pane_widget.setObjectName("LeftPane")
        left_pane_layout = QVBoxLayout(left_pane_widget)
        left_pane_layout.setContentsMargins(0, 0, 0, 0)

        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search units, lessons, exercises...")
        self.search_bar.textChanged.connect(self._filter_tree_view)
        left_pane_layout.addWidget(self.search_bar)

        self.advanced_filters_group = QGroupBox("Advanced Filters")
        advanced_filters_layout = QVBoxLayout(self.advanced_filters_group)

        # Exercise Type Filter
        type_filter_layout = QHBoxLayout()
        type_filter_layout.addWidget(QLabel("Type:"))
        self.type_filter_combo = QComboBox()
        self.type_filter_combo.addItems(
            [
                "All Types",
                "translate_to_target",
                "translate_to_source",
                "multiple_choice_translation",
                "fill_in_the_blank",
                "dictation",
                "image_association",
                "listen_and_select",
                "sentence_jumble",
                "context_block",
            ]
        )
        self.type_filter_combo.currentIndexChanged.connect(
            lambda: self._filter_tree_view(self.search_bar.text())
        )
        type_filter_layout.addWidget(self.type_filter_combo)
        advanced_filters_layout.addLayout(type_filter_layout)

        # Asset Presence Filter
        asset_filter_layout = QHBoxLayout()
        asset_filter_layout.addWidget(QLabel("Assets:"))
        self.asset_filter_combo = QComboBox()
        self.asset_filter_combo.addItems(
            [
                "Any Asset Status",
                "Has Audio",
                "No Audio",
                "Has Image",
                "No Image",
                "Has Both Audio & Image",
                "Missing Any Asset",  # Assumes if either audio or image is missing
            ]
        )
        self.asset_filter_combo.currentIndexChanged.connect(
            lambda: self._filter_tree_view(self.search_bar.text())
        )
        asset_filter_layout.addWidget(self.asset_filter_combo)
        advanced_filters_layout.addLayout(asset_filter_layout)

        # Search Scope Filter
        scope_filter_layout = QHBoxLayout()
        scope_filter_layout.addWidget(QLabel("Search In:"))
        self.scope_filter_combo = QComboBox()
        self.scope_filter_combo.addItems(
            [
                "All Text Fields",
                "Prompt Only",
                "Answer Only",
                "Source Word Only",
                "Sentence Template Only",
                "Translation Hint Only",
            ]
        )
        self.scope_filter_combo.currentIndexChanged.connect(
            lambda: self._filter_tree_view(self.search_bar.text())
        )
        scope_filter_layout.addWidget(self.scope_filter_combo)
        advanced_filters_layout.addLayout(scope_filter_layout)

        # Clear Filters Button
        self.clear_filters_button = QPushButton("Clear Filters")
        self.clear_filters_button.clicked.connect(self._clear_advanced_filters)
        advanced_filters_layout.addWidget(self.clear_filters_button)

        left_pane_layout.addWidget(self.advanced_filters_group)

        self.tree_widget = CourseTreeWidget(self.course_data, self)
        self.tree_widget.setHeaderLabels(["Course Structure"])
        self.tree_widget.setFont(QFont("Arial", 10))
        self.tree_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree_widget.customContextMenuRequested.connect(self._show_context_menu)
        self.tree_widget.itemSelectionChanged.connect(self._on_tree_item_selected)

        self.tree_widget.data_model_reordered.connect(self._handle_data_model_reordered)

        left_pane_layout.addWidget(self.tree_widget, 1)

        tree_actions_layout = QHBoxLayout()
        self.expand_all_button = QPushButton("Expand All")
        self.expand_all_button.clicked.connect(self.tree_widget.expandAll)
        self.collapse_all_button = QPushButton("Collapse All")
        self.collapse_all_button.clicked.connect(self.tree_widget.collapseAll)
        tree_actions_layout.addWidget(self.expand_all_button)
        tree_actions_layout.addWidget(self.collapse_all_button)
        tree_actions_layout.addStretch(1)
        left_pane_layout.addLayout(tree_actions_layout)

        self.splitter.addWidget(left_pane_widget)

        right_pane_widget = QWidget()
        right_pane_layout = QVBoxLayout(right_pane_widget)
        self.detail_editor_stacked_widget = QStackedWidget()
        self.detail_editor_stacked_widget.setObjectName("DetailEditorStackedWidget")
        right_pane_layout.addWidget(self.detail_editor_stacked_widget, 1)

        self.item_actions_widget = QWidget()
        item_actions_layout = QHBoxLayout(self.item_actions_widget)
        item_actions_layout.setContentsMargins(0, 5, 0, 0)
        self.move_up_button = QPushButton("Move Up ↑")
        self.move_up_button.clicked.connect(self._move_item_up)
        self.move_down_button = QPushButton("Move Down ↓")
        self.move_down_button.clicked.connect(self._move_item_down)
        self.preview_exercise_button = QPushButton("Preview Exercise ▶")
        self.preview_exercise_button.clicked.connect(self._preview_exercise)
        item_actions_layout.addStretch(1)
        item_actions_layout.addWidget(self.move_up_button)
        item_actions_layout.addWidget(self.move_down_button)
        item_actions_layout.addWidget(self.preview_exercise_button)
        item_actions_layout.addStretch(1)
        right_pane_layout.addWidget(self.item_actions_widget)
        self.item_actions_widget.setVisible(False)

        self.splitter.addWidget(right_pane_widget)
        self.splitter.setSizes([350, 850])

        outer_layout.addWidget(self.splitter)

        self.manifest_editor = ManifestEditorWidget()
        self.manifest_editor.data_changed.connect(self._set_dirty_state)
        self.detail_editor_stacked_widget.addWidget(self.manifest_editor)

        self.glossary_editor = GlossaryEditorWidget()
        self.glossary_editor.data_changed.connect(self._set_dirty_state)
        self.detail_editor_stacked_widget.addWidget(self.glossary_editor)

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

    def _handle_data_model_reordered(self, moved_obj: Any, new_parent_obj: Any):
        """
        Slot to handle the data_model_reordered signal from CourseTreeWidget.
        Refreshes the tree view and re-selects the moved item.
        """
        self.update_tree_view()
        self._set_dirty_state(True)
        self._expand_and_select_item(moved_obj)
        self.status_bar.showMessage("Item reordered successfully.", 2000)

    def _clear_advanced_filters(self):
        """Resets all advanced filter combo boxes to their default selections."""
        self.type_filter_combo.setCurrentIndex(0)  # "All Types"
        self.asset_filter_combo.setCurrentIndex(0)  # "Any Asset Status"
        self.scope_filter_combo.setCurrentIndex(0)  # "All Text Fields"
        # The _filter_tree_view will be called automatically by the currentIndexChanged signals.
        self.status_bar.showMessage("Advanced filters cleared.", 2000)

    def _filter_tree_view(self, text: str):
        search_term = text.lower().strip()
        selected_type_filter = self.type_filter_combo.currentText()
        selected_asset_filter = self.asset_filter_combo.currentText()
        selected_scope_filter = self.scope_filter_combo.currentText()

        # Store expanded state and selection before clearing
        expanded_state = {}
        selected_item_data = None
        current_sel_item = self.tree_widget.currentItem()
        if current_sel_item:
            selected_item_data = current_sel_item.data(0, Qt.UserRole)
            iterator = QTreeWidgetItemIterator(self.tree_widget)
            while iterator.value():
                item = iterator.value()
                item_data = item.data(0, Qt.UserRole)
                if item_data:
                    expanded_state[id(item_data)] = item.isExpanded()
                iterator += 1

        # Clear existing selection before re-populating if necessary,
        # otherwise currentItem might be invalid after hiding/showing
        self.tree_widget.setCurrentItem(None)

        # First pass: Determine visibility of each item based on all filters
        iterator = QTreeWidgetItemIterator(
            self.tree_widget, QTreeWidgetItemIterator.All
        )
        items_to_potentially_show_parents_for = []  # Collect items that become visible

        while iterator.value():
            item = iterator.value()
            item_data = item.data(0, Qt.UserRole)

            is_item_visible_by_filters = True

            # Items like "Manifest Info" or root items of a tree
            if not item_data or (
                isinstance(item_data, dict) and item_data.get("type") == "manifest"
            ):
                # Manifest item is special, only hide if search term is active and doesn't match its text
                if search_term and search_term not in item.text(0).lower():
                    is_item_visible_by_filters = False
                item.setHidden(not is_item_visible_by_filters)
                if is_item_visible_by_filters:
                    items_to_potentially_show_parents_for.append(item)
                iterator += 1
                continue

            # Units and Lessons only check search term
            if isinstance(item_data, (Unit, Lesson)):
                if search_term and search_term not in item.text(0).lower():
                    is_item_visible_by_filters = False
                item.setHidden(not is_item_visible_by_filters)
                if is_item_visible_by_filters:
                    items_to_potentially_show_parents_for.append(item)
                iterator += 1
                continue

            # Exercises: Apply all filters
            if isinstance(item_data, Exercise):
                exercise = item_data
                item_text_for_search = ""  # Default to empty

                # Apply Search Scope Filter
                if (
                    search_term
                ):  # Only consider scope if a search term is actually provided
                    if selected_scope_filter == "Prompt Only":
                        item_text_for_search = (exercise.prompt or "").lower()
                    elif selected_scope_filter == "Answer Only":
                        item_text_for_search = (exercise.answer or "").lower()
                    elif selected_scope_filter == "Source Word Only":
                        item_text_for_search = (exercise.source_word or "").lower()
                    elif selected_scope_filter == "Sentence Template Only":
                        item_text_for_search = (
                            exercise.sentence_template or ""
                        ).lower()
                    elif selected_scope_filter == "Translation Hint Only":
                        item_text_for_search = (exercise.translation_hint or "").lower()
                    else:  # "All Text Fields"
                        searchable_content = [
                            exercise.prompt,
                            exercise.answer,
                            exercise.source_word,
                            exercise.sentence_template,
                            exercise.translation_hint,
                            exercise.title,  # For context_block
                            item.text(0),  # Display text in tree
                        ]
                        # For sentence_jumble, exercise.words is a list of strings
                        if hasattr(exercise, "words") and isinstance(
                            exercise.words, list
                        ):
                            searchable_content.append(" ".join(exercise.words))

                        # For MCQ/Association, exercise.options is a list of ExerciseOption
                        if hasattr(exercise, "options") and isinstance(
                            exercise.options, list
                        ):
                            for option_obj in exercise.options:
                                if hasattr(option_obj, "text"):
                                    searchable_content.append(option_obj.text)

                        item_text_for_search = "".join(
                            str(s).lower() for s in searchable_content if s
                        )

                    if search_term not in item_text_for_search:
                        is_item_visible_by_filters = False

                # Apply Exercise Type Filter
                if is_item_visible_by_filters and selected_type_filter != "All Types":
                    # Convert 'translate_to_target' to 'Translate to Target' for comparison if needed, or use exact type
                    # For simplicity, we are directly using the internal type strings in QComboBox for now.
                    if exercise.type != selected_type_filter:
                        is_item_visible_by_filters = False

                # Apply Asset Presence Filter
                if (
                    is_item_visible_by_filters
                    and selected_asset_filter != "Any Asset Status"
                ):
                    has_audio = bool(exercise.audio_file)
                    has_image = bool(exercise.image_file)

                    if selected_asset_filter == "Has Audio" and not has_audio:
                        is_item_visible_by_filters = False
                    elif selected_asset_filter == "No Audio" and has_audio:
                        is_item_visible_by_filters = False
                    elif selected_asset_filter == "Has Image" and not has_image:
                        is_item_visible_by_filters = False
                    elif selected_asset_filter == "No Image" and has_image:
                        is_item_visible_by_filters = False
                    elif selected_asset_filter == "Has Both Audio & Image" and not (
                        has_audio and has_image
                    ):
                        is_item_visible_by_filters = False
                    elif selected_asset_filter == "Missing Any Asset" and (
                        has_audio or has_image
                    ):  # If either is present, it's not "missing any"
                        is_item_visible_by_filters = False

                item.setHidden(not is_item_visible_by_filters)
                if is_item_visible_by_filters:
                    items_to_potentially_show_parents_for.append(item)

            iterator += 1  # Move to the next item

        # Second pass: Ensure parents of visible children are also visible and expanded
        for item in items_to_potentially_show_parents_for:
            parent = item.parent()
            while parent:
                parent.setHidden(False)
                # Only expand parents if they were previously expanded or if they need to reveal a matching child
                # This prevents over-expanding the whole tree when filters are applied.
                parent_data_id = id(parent.data(0, Qt.UserRole))
                if parent_data_id in expanded_state and expanded_state[parent_data_id]:
                    parent.setExpanded(True)
                elif (
                    item.isExpanded() or not item.isHidden()
                ):  # If child was expanded or is now visible, expand parent
                    parent.setExpanded(True)
                parent = parent.parent()

        # Restore previous selection if it's still visible
        if selected_item_data:
            self._expand_and_select_item(selected_item_data)
        elif (
            self.tree_widget.topLevelItem(0)
            and not self.tree_widget.topLevelItem(0).isHidden()
        ):
            # If nothing was selected or selected item became hidden, select manifest info if visible
            self.tree_widget.setCurrentItem(self.tree_widget.topLevelItem(0))

    def _set_dirty_state(self, dirty: bool = True):
        self.is_dirty = dirty
        self.setWindowTitle(
            f"LL Course Editor{' *' if dirty else ''} - "
            f"{os.path.basename(self.current_manifest_path) if self.current_manifest_path else 'New Course'}"
        )

    def _display_item_editor(self, item_data: Any):
        self._clear_editor_pane()

        if isinstance(item_data, dict) and item_data.get("type") == "manifest":
            self.current_editor_widget = self.manifest_editor
            self.manifest_editor.load_data(
                item_data.get("manifest_data", {}),
                item_data.get("course_obj", self.course_data),
            )
            self.detail_editor_stacked_widget.setCurrentWidget(self.manifest_editor)
        elif isinstance(item_data, dict) and item_data.get("type") == "glossary":
            self.current_editor_widget = self.glossary_editor
            self.glossary_editor.load_glossary_data(
                self.manifest_data, self.current_manifest_path
            )
            self.detail_editor_stacked_widget.setCurrentWidget(self.glossary_editor)
        elif isinstance(item_data, Unit):
            self.current_editor_widget = self._create_unit_editor_widget(item_data)
            self.detail_editor_stacked_widget.addWidget(self.current_editor_widget)
            self.detail_editor_stacked_widget.setCurrentWidget(
                self.current_editor_widget
            )
        elif isinstance(item_data, Lesson):
            self.current_editor_widget = self._create_lesson_editor_widget(item_data)
            self.detail_editor_stacked_widget.addWidget(self.current_editor_widget)
            self.detail_editor_stacked_widget.setCurrentWidget(
                self.current_editor_widget
            )
        elif isinstance(item_data, Exercise):
            self.current_editor_widget = self._create_exercise_editor_widget(item_data)
            self.detail_editor_stacked_widget.addWidget(self.current_editor_widget)
            self.detail_editor_stacked_widget.setCurrentWidget(
                self.current_editor_widget
            )
        else:
            self.current_editor_widget = QLabel(
                "Select an item to edit its properties."
            )
            self.current_editor_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.detail_editor_stacked_widget.addWidget(self.current_editor_widget)
            self.detail_editor_stacked_widget.setCurrentWidget(
                self.current_editor_widget
            )

    def _clear_editor_pane(self):
        for i in reversed(range(self.detail_editor_stacked_widget.count())):
            widget = self.detail_editor_stacked_widget.widget(i)
            if (
                widget is not self.manifest_editor
                and widget is not self.glossary_editor
            ):
                self.detail_editor_stacked_widget.removeWidget(widget)
                widget.deleteLater()
        self.current_editor_widget = None

    def _validate_line_edit_required(self, input_widget: QLineEdit, is_required: bool):
        if not is_required:
            input_widget.setStyleSheet("")
            return
        text = input_widget.text().strip()
        if not text:
            input_widget.setStyleSheet("border: 1px solid red;")
        else:
            input_widget.setStyleSheet("")
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
                exercise, target_lang, source_lang  # No course_root_dir typically
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
    ) -> tuple[Optional[List], Optional[int]]:
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

    def _generate_new_ids_for_exercise(self, exercise: Exercise):
        exercise.exercise_id = f"ex_{uuid.uuid4().hex[:8]}"

    def _generate_new_ids_for_lesson(self, lesson: Lesson):
        lesson.lesson_id = f"lesson_{uuid.uuid4().hex[:8]}"
        for ex in lesson.exercises:
            self._generate_new_ids_for_exercise(ex)

    def _generate_new_ids_for_unit(self, unit: Unit):
        unit.unit_id = f"unit_{uuid.uuid4().hex[:8]}"
        for l in unit.lessons:
            l.unit_id = unit.unit_id
            self._generate_new_ids_for_lesson(l)

    def _duplicate_unit(self, original_unit_item: QTreeWidgetItem):
        original_unit: Unit = original_unit_item.data(0, Qt.UserRole)
        if not original_unit or not self.course_data:
            return

        new_unit = copy.deepcopy(original_unit)
        self._generate_new_ids_for_unit(new_unit)
        new_unit.title = f"{original_unit.title}_copy"

        original_index = self.course_data.units.index(original_unit)
        self.course_data.units.insert(original_index + 1, new_unit)

        self.update_tree_view()
        self._set_dirty_state(True)
        self._expand_and_select_item(new_unit)

    def _duplicate_lesson(self, original_lesson_item: QTreeWidgetItem):
        original_lesson: Lesson = original_lesson_item.data(0, Qt.UserRole)
        parent_unit_item = original_lesson_item.parent()
        parent_unit: Unit = (
            parent_unit_item.data(0, Qt.UserRole) if parent_unit_item else None
        )

        if not original_lesson or not parent_unit:
            return

        new_lesson = copy.deepcopy(original_lesson)
        new_lesson.unit_id = parent_unit.unit_id
        self._generate_new_ids_for_lesson(new_lesson)
        new_lesson.title = f"{original_lesson.title}_copy"

        original_index = parent_unit.lessons.index(original_lesson)
        parent_unit.lessons.insert(original_index + 1, new_lesson)

        self.update_tree_view()
        self._set_dirty_state(True)
        self._expand_and_select_item(new_lesson)

    def _duplicate_exercise(self, original_exercise_item: QTreeWidgetItem):
        original_exercise: Exercise = original_exercise_item.data(0, Qt.UserRole)
        parent_lesson_item = original_exercise_item.parent()
        parent_lesson: Lesson = (
            parent_lesson_item.data(0, Qt.UserRole) if parent_lesson_item else None
        )

        if not original_exercise or not parent_lesson:
            return

        new_exercise = copy.deepcopy(original_exercise)
        self._generate_new_ids_for_exercise(new_exercise)
        if new_exercise.prompt:
            new_exercise.prompt += "_copy"
        elif new_exercise.source_word:
            new_exercise.source_word += "_copy"

        original_index = parent_lesson.exercises.index(original_exercise)
        parent_lesson.exercises.insert(original_index + 1, new_exercise)

        self.update_tree_view()
        self._set_dirty_state(True)
        self._expand_and_select_item(new_exercise)

    def _add_unit(self):
        if not self.course_data:
            return
        unit_id_suffix = str(uuid.uuid4().hex[:8])
        default_title = f"New Unit {len(self.course_data.units) + 1}"
        unit_title, ok = QInputDialog.getText(
            self, "New Unit", "Enter Unit Title:", text=default_title
        )
        if ok and unit_title and unit_title.strip():
            new_unit = Unit(
                unit_id=f"unit_{unit_id_suffix}", title=unit_title.strip(), lessons=[]
            )
            self.course_data.units.append(new_unit)
            self.update_tree_view()
            self._set_dirty_state(True)
            self._expand_and_select_item(new_unit)
        elif ok:
            QMessageBox.warning(self, "Invalid Input", "Unit title cannot be empty.")

    def _delete_unit(self, item: QTreeWidgetItem):
        unit_to_delete: Unit = item.data(0, Qt.UserRole)
        if not unit_to_delete:
            return
        reply = QMessageBox.question(
            self,
            "Delete Unit",
            f"Are you sure you want to delete unit '{unit_to_delete.title}' and all its contents?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.course_data.units = [
                u for u in self.course_data.units if u.unit_id != unit_to_delete.unit_id
            ]
            self.update_tree_view()
            self._set_dirty_state(True)
            self._clear_editor_pane()
            self.item_actions_widget.setVisible(False)

    def _add_lesson(self, unit_item: QTreeWidgetItem):
        unit: Unit = unit_item.data(0, Qt.UserRole)
        if not unit:
            return
        lesson_id_suffix = str(uuid.uuid4().hex[:8])
        default_title = f"New Lesson {len(unit.lessons) + 1}"
        lesson_title, ok = QInputDialog.getText(
            self, "New Lesson", "Enter Lesson Title:", text=default_title
        )
        if ok and lesson_title and lesson_title.strip():
            new_lesson = Lesson(
                lesson_id=f"lesson_{lesson_id_suffix}",
                title=lesson_title.strip(),
                exercises=[],
                unit_id=unit.unit_id,
            )
            unit.lessons.append(new_lesson)
            self.update_tree_view()
            self._set_dirty_state(True)
            self._expand_and_select_item(new_lesson)
        elif ok:
            QMessageBox.warning(self, "Invalid Input", "Lesson title cannot be empty.")

    def _delete_lesson(self, item: QTreeWidgetItem):
        lesson_to_delete: Lesson = item.data(0, Qt.UserRole)
        if not lesson_to_delete:
            return
        reply = QMessageBox.question(
            self,
            "Delete Lesson",
            f"Are you sure you want to delete lesson '{lesson_to_delete.title}' and all its exercises?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            parent_unit_item = item.parent()
            parent_unit: Unit = (
                parent_unit_item.data(0, Qt.UserRole) if parent_unit_item else None
            )
            if parent_unit:
                parent_unit.lessons = [
                    l
                    for l in parent_unit.lessons
                    if l.lesson_id != lesson_to_delete.lesson_id
                ]
                self.update_tree_view()
                self._set_dirty_state(True)
                self._clear_editor_pane()
                self.item_actions_widget.setVisible(False)

    def _add_exercise(self, lesson_item: QTreeWidgetItem):
        lesson: Lesson = lesson_item.data(0, Qt.UserRole)
        if not lesson:
            return

        ex_types = [
            "translate_to_target",
            "translate_to_source",
            "multiple_choice_translation",
            "fill_in_the_blank",
            "dictation",
            "image_association",
            "listen_and_select",
            "sentence_jumble",
            "context_block",
        ]
        item_type_name, ok = QInputDialog.getItem(
            self, "New Exercise", "Select Exercise Type:", ex_types, 0, False
        )

        if ok and item_type_name:
            exercise_id_suffix = str(uuid.uuid4().hex[:8])
            new_exercise = Exercise(
                exercise_id=f"ex_{exercise_id_suffix}", type=item_type_name
            )
            lesson.exercises.append(new_exercise)
            self.update_tree_view()
            self._set_dirty_state(True)
            self._expand_and_select_item(new_exercise)

    def _delete_exercise(self, item: QTreeWidgetItem):
        exercise_to_delete: Exercise = item.data(0, Qt.UserRole)
        if not exercise_to_delete:
            return
        reply = QMessageBox.question(
            self,
            "Delete Exercise",
            f"Are you sure you want to delete this exercise?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            parent_lesson_item = item.parent()
            parent_lesson: Lesson = (
                parent_lesson_item.data(0, Qt.UserRole) if parent_lesson_item else None
            )
            if parent_lesson:
                parent_lesson.exercises = [
                    e
                    for e in parent_lesson.exercises
                    if e.exercise_id != exercise_to_delete.exercise_id
                ]
                self.update_tree_view()
                self._set_dirty_state(True)
                self._clear_editor_pane()
                self.item_actions_widget.setVisible(False)

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

        self.tree_widget.clear()
        if not self.course_data:
            return

        manifest_item_data = {
            "type": "manifest",
            "manifest_data": self.manifest_data,
            "course_obj": self.course_data,
        }
        manifest_item = QTreeWidgetItem(self.tree_widget, ["Manifest Info"])
        manifest_item.setData(0, Qt.UserRole, manifest_item_data)
        manifest_item.setFont(0, QFont("Arial", 11, QFont.Bold))
        manifest_item.setFlags(
            manifest_item.flags()
            & ~Qt.ItemFlag.ItemIsDragEnabled
            & ~Qt.ItemFlag.ItemIsDropEnabled
        )
        if (
            id(manifest_item_data) in expanded_items_data
            and expanded_items_data[id(manifest_item_data)]
        ):
            manifest_item.setExpanded(True)

        glossary_item_data = {"type": "glossary"}
        glossary_item = QTreeWidgetItem(self.tree_widget, ["Glossary"])
        glossary_item.setData(0, Qt.UserRole, glossary_item_data)
        glossary_item.setFont(0, QFont("Arial", 11, QFont.Bold))
        # Glossary item itself is not draggable/droppable, only its content.
        glossary_item.setFlags(
            glossary_item.flags()
            & ~Qt.ItemFlag.ItemIsDragEnabled
            & ~Qt.ItemFlag.ItemIsDropEnabled
        )
        # Place after Manifest Info
        self.tree_widget.insertTopLevelItem(
            self.tree_widget.indexOfTopLevelItem(manifest_item) + 1, glossary_item
        )

        if (
            id(glossary_item_data) in expanded_items_data
            and expanded_items_data[id(glossary_item_data)]
        ):
            glossary_item.setExpanded(True)

        for unit in self.course_data.units:
            unit_item = QTreeWidgetItem(self.tree_widget, [unit.title])
            unit_item.setData(0, Qt.UserRole, unit)
            unit_item.setFont(0, QFont("Arial", 10, QFont.Bold))
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

                for idx, exercise in enumerate(lesson.exercises):
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
                    ex_display_text = f"[{exercise.type}] {ex_display_text_content}"
                    exercise_item = QTreeWidgetItem(lesson_item, [ex_display_text])
                    exercise_item.setData(0, Qt.UserRole, exercise)
                    exercise_item.setFlags(
                        exercise_item.flags()
                        | Qt.ItemIsDragEnabled
                        | Qt.ItemIsDropEnabled
                    )

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
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
            )
            if reply == QMessageBox.Save:
                if not self.save_course():
                    return
            elif reply == QMessageBox.Cancel:
                return

        self.manifest_data, self.course_data = create_new_course()
        self.current_manifest_path = None
        self.current_course_content_path = None
        self.update_tree_view()
        self._set_dirty_state(False)
        self._clear_editor_pane()
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
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
            )
            if reply == QMessageBox.Save:
                if not self.save_course():
                    return
            elif reply == QMessageBox.Cancel:
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

        self.update_tree_view()
        self._set_dirty_state(False)
        self._clear_editor_pane()
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

        if not save_manifest(self.manifest_data, manifest_file):
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
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
            )
            if reply == QMessageBox.Save:
                if not self.save_course():
                    event.ignore()
                    return
            elif reply == QMessageBox.Cancel:
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
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
            )
            if reply == QMessageBox.Save:
                if not self.save_course():
                    return
            elif reply == QMessageBox.Cancel:
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

        if not all_errors:
            QMessageBox.information(
                self, "Validation Result", "Validation Successful! No errors found."
            )
        else:
            error_dialog = QDialog(self)
            error_dialog.setWindowTitle("Validation Errors")
            layout = QVBoxLayout(error_dialog)
            text_edit = QTextEdit()
            text_edit.setReadOnly(True)
            text_edit.setText("\n".join(all_errors))
            layout.addWidget(text_edit)
            ok_button = QPushButton("OK")
            ok_button.clicked.connect(error_dialog.accept)
            layout.addWidget(ok_button)
            error_dialog.setMinimumSize(600, 400)
            error_dialog.exec()

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
                    self.current_course_content_path, self.manifest_data
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
