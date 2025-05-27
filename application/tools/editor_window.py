import os
import uuid
import logging
import sys # For sys.path
import copy # For deepcopy
from typing import Any, Optional, List
import yaml
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                               QTreeWidget, QTreeWidgetItem, QStackedWidget,
                               QPushButton, QFileDialog, QMessageBox, QLabel, QInputDialog,
                               QSplitter, QComboBox, QMenu, QTextEdit, QDialog, QFrame, QLineEdit, QTreeWidgetItemIterator) # Added QFrame
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QFont

# Dynamic path adjustment for importing models from the 'application/core' directory.
try:
    from core.models import Course, Unit, Lesson, Exercise, ExerciseOption
    from core.course_loader import load_course_content as load_course_content_from_yaml # Use app's loader
    from tools.dialogs.exercise_preview_dialog import ExercisePreviewDialog
except ImportError as e:
    logging.error(f"Failed to import models from core. Ensure 'application' directory is on sys.path. Error: {e}")
    class Course: pass # Dummy classes for graceful degradation
    class Unit: pass
    class Lesson: pass
    class Exercise: pass
    class ExerciseOption: pass

# Correct relative imports for other modules within the 'tools' package
from .yaml_manager import load_manifest, save_manifest, create_new_course
from .widgets.manifest_editor_widget import ManifestEditorWidget
from .widgets.exercise_editor_widgets import (
    TranslationExerciseEditorWidget, MultipleChoiceExerciseEditorWidget, 
    FillInTheBlankExerciseEditorWidget
)
from .dialogs.csv_import_dialog import CsvImportDialog
from .dialogs.package_creation_dialog import PackageCreationDialog
from .course_validator import perform_manifest_validation, perform_course_content_validation 
from .csv_importer import import_csv_data, load_existing_course_data, save_course_data
from .course_packager import create_package_for_gui


logger = logging.getLogger(__name__)

class EditorWindow(QMainWindow):
    course_changed = Signal() # Emits when course data is structurally modified

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("LL Course Editor")
        self.setGeometry(100, 100, 1200, 800)

        self.current_manifest_path: str = None
        self.current_course_content_path: str = None
        self.manifest_data: dict = None
        self.course_data: Course = None 

        self._create_menu_bar()
        self._set_dirty_state(False)
        self._setup_ui()
        
        self.new_course()

    def _create_menu_bar(self):
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("File")

        new_action = QAction("New Course...", self)
        new_action.triggered.connect(self.new_course)
        file_menu.addAction(new_action)

        open_action = QAction("Open Course...", self)
        open_action.triggered.connect(self.open_course)
        file_menu.addAction(open_action)
        file_menu.addSeparator()

        save_action = QAction("Save Course", self)
        save_action.triggered.connect(self.save_course)
        file_menu.addAction(save_action)

        save_as_action = QAction("Save Course As...", self)
        save_as_action.triggered.connect(self.save_course_as)
        file_menu.addAction(save_as_action)
        
        tools_menu = menu_bar.addMenu("Tools")
        validate_action = QAction("Validate Current Course", self)
        validate_action.triggered.connect(self.validate_current_course)
        tools_menu.addAction(validate_action)
        import_csv_action = QAction("Import Exercises from CSV...", self)
        import_csv_action.triggered.connect(self.import_from_csv)
        tools_menu.addAction(import_csv_action)
        tools_menu.addSeparator()
        package_action = QAction("Create Course Package (.lcpkg)...", self)
        package_action.triggered.connect(self.create_course_package)
        tools_menu.addAction(package_action)
        
        file_menu.addSeparator()
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

    def _setup_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        outer_layout = QVBoxLayout(main_widget)

        self.splitter = QSplitter(Qt.Horizontal)
        # outer_layout.addWidget(self.splitter, 1) # Give splitter stretch factor

        # Left pane: Search bar and Tree view
        left_pane_widget = QWidget()
        left_pane_layout = QVBoxLayout(left_pane_widget)
        left_pane_layout.setContentsMargins(0,0,0,0) # No margin for left pane itself

        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search units, lessons, exercises...")
        self.search_bar.textChanged.connect(self._filter_tree_view)
        left_pane_layout.addWidget(self.search_bar)

        self.tree_widget = QTreeWidget()
        self.tree_widget.setHeaderLabels(["Course Structure"])
        self.tree_widget.setFont(QFont("Arial", 10))
        self.tree_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree_widget.customContextMenuRequested.connect(self._show_context_menu)
        self.tree_widget.itemSelectionChanged.connect(self._on_tree_item_selected)
        left_pane_layout.addWidget(self.tree_widget, 1) # Tree gets stretch factor

        tree_actions_layout = QHBoxLayout()
        self.expand_all_button = QPushButton("Expand All")
        self.expand_all_button.clicked.connect(self.tree_widget.expandAll)
        self.collapse_all_button = QPushButton("Collapse All")
        self.collapse_all_button.clicked.connect(self.tree_widget.collapseAll)
        tree_actions_layout.addWidget(self.expand_all_button)
        tree_actions_layout.addWidget(self.collapse_all_button)
        tree_actions_layout.addStretch(1) # Push buttons to left
        left_pane_layout.addLayout(tree_actions_layout)

        self.splitter.addWidget(left_pane_widget) # Add the entire left pane to splitter

        # Right pane: Editor details
        right_pane_widget = QWidget()
        right_pane_layout = QVBoxLayout(right_pane_widget)
        self.detail_editor_stacked_widget = QStackedWidget()
        right_pane_layout.addWidget(self.detail_editor_stacked_widget, 1) 

        self.item_actions_widget = QWidget() 
        item_actions_layout = QHBoxLayout(self.item_actions_widget)
        item_actions_layout.setContentsMargins(0,5,0,0) 
        self.move_up_button = QPushButton("Move Up ↑")
        self.move_up_button.clicked.connect(self._move_item_up)
        self.move_down_button = QPushButton("Move Down ↓")
        self.move_down_button.clicked.connect(self._move_item_down)
        self.preview_exercise_button = QPushButton("Preview Exercise ▶") # NEW BUTTON
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
        
        outer_layout.addWidget(self.splitter) # Add splitter to the main outer layout

        self.manifest_editor = ManifestEditorWidget()
        self.manifest_editor.data_changed.connect(self._set_dirty_state)
        self.detail_editor_stacked_widget.addWidget(self.manifest_editor) 

        self.current_editor_widget = None 
        self.current_selected_tree_item = None 

        self.status_bar = self.statusBar() # Get the QMainWindow's status bar
        self.current_file_label = QLabel("No course loaded")
        self.dirty_status_label = QLabel("") # Will show "Unsaved changes" or "Saved"
        self.dirty_status_label.setStyleSheet("padding-right: 10px;") # Add some padding
        
        self.status_bar.addPermanentWidget(self.current_file_label, stretch=1) # Stretch takes available space
        self.status_bar.addPermanentWidget(self.dirty_status_label)

        if self.is_dirty:
            self.dirty_status_label.setText("Unsaved Changes*")
            self.dirty_status_label.setStyleSheet("color: orange; padding-right: 10px; font-weight: bold;")
        else:
            self.dirty_status_label.setText("Saved")
            self.dirty_status_label.setStyleSheet("color: green; padding-right: 10px;")

    def _filter_tree_view(self, text: str):
        search_term = text.lower().strip()
        
        iterator = QTreeWidgetItemIterator(self.tree_widget)
        while iterator.value():
            item = iterator.value()
            item_data = item.data(0, Qt.UserRole)
            
            # Skip top-level non-data items or the manifest item for filtering content itself
            if not item_data or (isinstance(item_data, dict) and item_data.get("type") == "manifest"):
                if not search_term: # Always show manifest if search is empty
                    item.setHidden(False)
                else: # Hide manifest if searching, unless search term is "manifest"
                    item.setHidden("manifest" not in item.text(0).lower())
                iterator += 1
                continue

            item_text = item.text(0).lower()
            
            # Determine if the item itself matches
            matches = search_term in item_text
            
            # If it matches, ensure all its parents are visible and expanded
            if matches:
                item.setHidden(False)
                parent = item.parent()
                while parent:
                    parent.setHidden(False)
                    parent.setExpanded(True)
                    parent = parent.parent()
            else: # If item doesn't match, hide it initially
                item.setHidden(True)
            
            iterator += 1
            
        # Second pass: if a child is visible, its parent must be visible.
        # This is partially handled above, but a second pass ensures correctness if a parent didn't match
        # but a child did.
        if search_term: # Only do this complex visibility check if there's a search term
            iterator = QTreeWidgetItemIterator(self.tree_widget, QTreeWidgetItemIterator.All)
            items_to_show_parents_for = []
            while iterator.value():
                item = iterator.value()
                if not item.isHidden() and item.parent():
                    items_to_show_parents_for.append(item)
                iterator += 1
            
            for item_with_visible_child in items_to_show_parents_for:
                parent = item_with_visible_child.parent()
                while parent:
                    parent.setHidden(False)
                    # parent.setExpanded(True) # Expansion can be aggressive, might be better without
                    parent = parent.parent()
        
        # If search is empty, unhide all items
        if not search_term:
            iterator = QTreeWidgetItemIterator(self.tree_widget)
            while iterator.value():
                iterator.value().setHidden(False)
                iterator += 1
            # self.tree_widget.expandAll() # Optionally re-expand all if search is cleared

    def _set_dirty_state(self, dirty: bool = True):
        self.is_dirty = dirty
        self.setWindowTitle(f"LL Course Editor{' *' if dirty else ''} - "
                            f"{os.path.basename(self.current_manifest_path) if self.current_manifest_path else 'New Course'}")
        
    def _display_item_editor(self, item_data: Any):
        self._clear_editor_pane()
        
        if isinstance(item_data, dict) and item_data.get("type") == "manifest":
            self.current_editor_widget = self.manifest_editor
            self.manifest_editor.load_data(item_data.get("manifest_data", {}),
                                           item_data.get("course_obj", self.course_data))
            self.detail_editor_stacked_widget.setCurrentWidget(self.manifest_editor)
        elif isinstance(item_data, Unit):
            self.current_editor_widget = self._create_unit_editor_widget(item_data)
            self.detail_editor_stacked_widget.addWidget(self.current_editor_widget)
            self.detail_editor_stacked_widget.setCurrentWidget(self.current_editor_widget)
        elif isinstance(item_data, Lesson):
            self.current_editor_widget = self._create_lesson_editor_widget(item_data)
            self.detail_editor_stacked_widget.addWidget(self.current_editor_widget)
            self.detail_editor_stacked_widget.setCurrentWidget(self.current_editor_widget)
        elif isinstance(item_data, Exercise):
            self.current_editor_widget = self._create_exercise_editor_widget(item_data)
            self.detail_editor_stacked_widget.addWidget(self.current_editor_widget)
            self.detail_editor_stacked_widget.setCurrentWidget(self.current_editor_widget)
        else:
            self.current_editor_widget = QLabel("Select an item to edit its properties.")
            self.current_editor_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.detail_editor_stacked_widget.addWidget(self.current_editor_widget)
            self.detail_editor_stacked_widget.setCurrentWidget(self.current_editor_widget)

    def _clear_editor_pane(self):
        for i in reversed(range(self.detail_editor_stacked_widget.count())):
            widget = self.detail_editor_stacked_widget.widget(i)
            if widget is not self.manifest_editor:
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
            input_widget.setStyleSheet("") # Clear any error style
        self._set_dirty_state(True) # Change implies dirty state

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
        unit_title_edit.textChanged.connect(lambda text: self._update_unit_title(unit, text))
        unit_title_edit.textChanged.connect(lambda text: self._validate_line_edit_required(unit_title_edit, True)) # Connect validation
        title_layout.addWidget(unit_title_edit)
        layout.addLayout(title_layout)
        layout.addStretch(1)
        widget.unit_id_edit = unit_id_edit
        widget.unit_title_edit = unit_title_edit
        self._validate_line_edit_required(unit_title_edit, True) # Initial validation
        return widget

    def _update_unit_title(self, unit: Unit, new_title: str):
        unit.title = new_title.strip() # Ensure stripped for data consistency
        self._set_dirty_state(True)
        if self.current_selected_tree_item and self.current_selected_tree_item.data(0, Qt.UserRole) is unit:
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
        title_label = QLabel("Title: *") # Mark as required
        title_layout.addWidget(title_label)
        lesson_title_edit = QLineEdit(lesson.title)
        lesson_title_edit.textChanged.connect(lambda text: self._update_lesson_title(lesson, text))
        lesson_title_edit.textChanged.connect(lambda text: self._validate_line_edit_required(lesson_title_edit, True)) # Connect validation
        title_layout.addWidget(lesson_title_edit)
        layout.addLayout(title_layout)
        layout.addStretch(1)
        widget.lesson_id_edit = lesson_id_edit
        widget.lesson_title_edit = lesson_title_edit
        self._validate_line_edit_required(lesson_title_edit, True) # Initial validation
        return widget

    def _update_lesson_title(self, lesson: Lesson, new_title: str):
        lesson.title = new_title.strip() # Ensure stripped
        self._set_dirty_state(True)
        if self.current_selected_tree_item and self.current_selected_tree_item.data(0, Qt.UserRole) is lesson:
            self.current_selected_tree_item.setText(0, new_title.strip())

    def _create_exercise_editor_widget(self, exercise: Exercise):
        target_lang = self.course_data.target_language if self.course_data else "Target Language"
        source_lang = self.course_data.source_language if self.course_data else "Source Language"
        if exercise.type == "translate_to_target" or exercise.type == "translate_to_source":
            widget = TranslationExerciseEditorWidget(exercise, target_lang, source_lang)
        elif exercise.type == "multiple_choice_translation":
            widget = MultipleChoiceExerciseEditorWidget(exercise, target_lang, source_lang)
        elif exercise.type == "fill_in_the_blank":
            widget = FillInTheBlankExerciseEditorWidget(exercise, target_lang, source_lang)
        else:
            widget = QLabel(f"No editor for exercise type: {exercise.type}")
            widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if hasattr(widget, 'data_changed'):
            widget.data_changed.connect(self._set_dirty_state)
        return widget
        
    def _on_tree_item_selected(self):
        selected_items = self.tree_widget.selectedItems()
        self.current_selected_tree_item = None # Reset
        self.item_actions_widget.setVisible(False) # Hide move buttons by default

        if not selected_items:
            self._display_item_editor(None)
            return

        self.current_selected_tree_item = selected_items[0]
        item_data = self.current_selected_tree_item.data(0, Qt.UserRole)
        self._display_item_editor(item_data)

        # Manage Move Up/Down buttons visibility and enabled state
        if isinstance(item_data, (Unit, Lesson, Exercise)):
            self.item_actions_widget.setVisible(True)
            parent_list, current_index = self._get_item_list_and_index(item_data)
            if parent_list is not None and current_index is not None:
                self.move_up_button.setEnabled(current_index > 0)
                self.move_down_button.setEnabled(current_index < len(parent_list) - 1)
            else: # Should not happen if item is in tree
                self.move_up_button.setEnabled(False)
                self.move_down_button.setEnabled(False)
            self.preview_exercise_button.setEnabled(isinstance(item_data, Exercise))
        else: # Manifest or other non-orderable item
            self.item_actions_widget.setVisible(False)

    def _get_item_list_and_index(self, item_data_obj: Any) -> tuple[Optional[List], Optional[int]]:
        """Helper to get the list and index of an item for reordering."""
        if isinstance(item_data_obj, Unit):
            try: return self.course_data.units, self.course_data.units.index(item_data_obj)
            except ValueError: return None, None
        elif isinstance(item_data_obj, Lesson):
            parent_unit_item = self.current_selected_tree_item.parent()
            if parent_unit_item:
                parent_unit: Unit = parent_unit_item.data(0, Qt.UserRole)
                if parent_unit and isinstance(parent_unit, Unit):
                    try: return parent_unit.lessons, parent_unit.lessons.index(item_data_obj)
                    except ValueError: return None, None
        elif isinstance(item_data_obj, Exercise):
            parent_lesson_item = self.current_selected_tree_item.parent()
            if parent_lesson_item:
                parent_lesson: Lesson = parent_lesson_item.data(0, Qt.UserRole)
                if parent_lesson and isinstance(parent_lesson, Lesson):
                    try: return parent_lesson.exercises, parent_lesson.exercises.index(item_data_obj)
                    except ValueError: return None, None
        return None, None

    def _move_item_up(self):
        if not self.current_selected_tree_item: return
        item_data = self.current_selected_tree_item.data(0, Qt.UserRole)
        parent_list, current_index = self._get_item_list_and_index(item_data)

        if parent_list is not None and current_index is not None and current_index > 0:
            parent_list.insert(current_index - 1, parent_list.pop(current_index))
            self.update_tree_view() # Rebuild tree
            self._set_dirty_state(True)
            self._expand_and_select_item(item_data) # Reselect the moved item
            self._on_tree_item_selected() # Refresh button states

    def _move_item_down(self):
        if not self.current_selected_tree_item: return
        item_data = self.current_selected_tree_item.data(0, Qt.UserRole)
        parent_list, current_index = self._get_item_list_and_index(item_data)

        if parent_list is not None and current_index is not None and current_index < len(parent_list) - 1:
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
                
                duplicate_unit_action = QAction("Duplicate Unit", self) # New
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
                
                duplicate_lesson_action = QAction("Duplicate Lesson", self) # New
                duplicate_lesson_action.triggered.connect(lambda: self._duplicate_lesson(item))
                menu.addAction(duplicate_lesson_action)
                menu.addSeparator()
                
                delete_lesson_action = QAction("Delete Lesson", self)
                delete_lesson_action.triggered.connect(lambda: self._delete_lesson(item))
                menu.addAction(delete_lesson_action)
            elif isinstance(item_data, Exercise):
                duplicate_exercise_action = QAction("Duplicate Exercise", self) # New
                duplicate_exercise_action.triggered.connect(lambda: self._duplicate_exercise(item))
                menu.addAction(duplicate_exercise_action)
                menu.addSeparator()

                delete_exercise_action = QAction("Delete Exercise", self)
                delete_exercise_action.triggered.connect(lambda: self._delete_exercise(item))
                menu.addAction(delete_exercise_action)
        
        menu.exec(self.tree_widget.viewport().mapToGlobal(position))

    def _preview_exercise(self): # NEW SLOT
        if not self.current_selected_tree_item:
            QMessageBox.warning(self, "Preview Error", "Please select an exercise in the tree to preview.")
            return

        item_data = self.current_selected_tree_item.data(0, Qt.UserRole)
        if not isinstance(item_data, Exercise):
            QMessageBox.warning(self, "Preview Error", "Only exercises can be previewed. Please select an exercise.")
            return

        # Ensure current editor content is applied to the exercise object before previewing
        # This is critical if the user made changes but hasn't switched focus or saved.
        if isinstance(self.current_editor_widget, (TranslationExerciseEditorWidget, MultipleChoiceExerciseEditorWidget, FillInTheBlankExerciseEditorWidget)):
             # The editor widgets update the item_data directly via signal connections,
             # so the item_data should already be up-to-date.
             # However, if there's a specific "apply" mechanism or if some fields are only updated on focus loss,
             # this might need an explicit call. For our current setup, it should be fine.
             pass # Data is already updated by textChanged/button clicks.

        # Pass course languages and base directory for audio/image path resolution in preview
        course_languages = {
            'target': self.course_data.target_language if self.course_data else "Target Language",
            'source': self.course_data.source_language if self.course_data else "Source Language"
        }
        course_content_base_dir = None
        if self.current_course_content_path:
            course_content_base_dir = os.path.dirname(self.current_course_content_path)
        
        # Open the preview dialog
        dialog = ExercisePreviewDialog(item_data, course_languages, course_content_base_dir, self)
        dialog.exec()

    # --- Duplicate Methods ---
    def _generate_new_ids_for_exercise(self, exercise: Exercise):
        exercise.exercise_id = f"ex_{uuid.uuid4().hex[:8]}"
        # Options don't typically have IDs in this model

    def _generate_new_ids_for_lesson(self, lesson: Lesson):
        lesson.lesson_id = f"lesson_{uuid.uuid4().hex[:8]}"
        for ex in lesson.exercises:
            self._generate_new_ids_for_exercise(ex)

    def _generate_new_ids_for_unit(self, unit: Unit):
        unit.unit_id = f"unit_{uuid.uuid4().hex[:8]}"
        for l in unit.lessons:
            l.unit_id = unit.unit_id # Update parent unit_id ref
            self._generate_new_ids_for_lesson(l)

    def _duplicate_unit(self, original_unit_item: QTreeWidgetItem):
        original_unit: Unit = original_unit_item.data(0, Qt.UserRole)
        if not original_unit or not self.course_data: return

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
        parent_unit: Unit = parent_unit_item.data(0, Qt.UserRole) if parent_unit_item else None

        if not original_lesson or not parent_unit: return

        new_lesson = copy.deepcopy(original_lesson)
        new_lesson.unit_id = parent_unit.unit_id # Ensure correct parent unit_id
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
        parent_lesson: Lesson = parent_lesson_item.data(0, Qt.UserRole) if parent_lesson_item else None

        if not original_exercise or not parent_lesson: return

        new_exercise = copy.deepcopy(original_exercise)
        self._generate_new_ids_for_exercise(new_exercise)
        # Exercise titles aren't a direct field, use prompt or source_word for copy indication if desired
        if new_exercise.prompt: new_exercise.prompt += "_copy"
        elif new_exercise.source_word: new_exercise.source_word += "_copy"
        
        original_index = parent_lesson.exercises.index(original_exercise)
        parent_lesson.exercises.insert(original_index + 1, new_exercise)
        
        self.update_tree_view()
        self._set_dirty_state(True)
        self._expand_and_select_item(new_exercise)

    def _add_unit(self):
        if not self.course_data: return
        unit_id_suffix = str(uuid.uuid4().hex[:8])
        default_title = f"New Unit {len(self.course_data.units) + 1}"
        unit_title, ok = QInputDialog.getText(self, "New Unit", "Enter Unit Title:", text=default_title)
        if ok and unit_title and unit_title.strip():
            new_unit = Unit(unit_id=f"unit_{unit_id_suffix}", title=unit_title.strip(), lessons=[])
            self.course_data.units.append(new_unit)
            self.update_tree_view()
            self._set_dirty_state(True)
            self._expand_and_select_item(new_unit)
        elif ok:
            QMessageBox.warning(self, "Invalid Input", "Unit title cannot be empty.")

    def _delete_unit(self, item: QTreeWidgetItem):
        unit_to_delete: Unit = item.data(0, Qt.UserRole)
        if not unit_to_delete: return
        reply = QMessageBox.question(self, "Delete Unit", 
                                     f"Are you sure you want to delete unit '{unit_to_delete.title}' and all its contents?",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.course_data.units = [u for u in self.course_data.units if u.unit_id != unit_to_delete.unit_id]
            self.update_tree_view()
            self._set_dirty_state(True)
            self._clear_editor_pane() 
            self.item_actions_widget.setVisible(False)


    def _add_lesson(self, unit_item: QTreeWidgetItem):
        unit: Unit = unit_item.data(0, Qt.UserRole)
        if not unit: return
        lesson_id_suffix = str(uuid.uuid4().hex[:8])
        default_title = f"New Lesson {len(unit.lessons) + 1}"
        lesson_title, ok = QInputDialog.getText(self, "New Lesson", "Enter Lesson Title:", text=default_title)
        if ok and lesson_title and lesson_title.strip():
            new_lesson = Lesson(lesson_id=f"lesson_{lesson_id_suffix}", title=lesson_title.strip(), exercises=[], unit_id=unit.unit_id)
            unit.lessons.append(new_lesson)
            self.update_tree_view()
            self._set_dirty_state(True)
            self._expand_and_select_item(new_lesson)
        elif ok:
            QMessageBox.warning(self, "Invalid Input", "Lesson title cannot be empty.")

    def _delete_lesson(self, item: QTreeWidgetItem):
        lesson_to_delete: Lesson = item.data(0, Qt.UserRole)
        if not lesson_to_delete: return
        reply = QMessageBox.question(self, "Delete Lesson", 
                                     f"Are you sure you want to delete lesson '{lesson_to_delete.title}' and all its exercises?",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            parent_unit_item = item.parent()
            parent_unit: Unit = parent_unit_item.data(0, Qt.UserRole) if parent_unit_item else None
            if parent_unit:
                parent_unit.lessons = [l for l in parent_unit.lessons if l.lesson_id != lesson_to_delete.lesson_id]
                self.update_tree_view()
                self._set_dirty_state(True)
                self._clear_editor_pane()
                self.item_actions_widget.setVisible(False)


    def _add_exercise(self, lesson_item: QTreeWidgetItem):
        lesson: Lesson = lesson_item.data(0, Qt.UserRole)
        if not lesson: return

        ex_types = ["translate_to_target", "translate_to_source", "multiple_choice_translation", "fill_in_the_blank"]
        item_type_name, ok = QInputDialog.getItem(self, "New Exercise", "Select Exercise Type:", ex_types, 0, False)
        
        if ok and item_type_name:
            exercise_id_suffix = str(uuid.uuid4().hex[:8])
            new_exercise = Exercise(exercise_id=f"ex_{exercise_id_suffix}", type=item_type_name)
            lesson.exercises.append(new_exercise)
            self.update_tree_view()
            self._set_dirty_state(True)
            self._expand_and_select_item(new_exercise)

    def _delete_exercise(self, item: QTreeWidgetItem):
        exercise_to_delete: Exercise = item.data(0, Qt.UserRole)
        if not exercise_to_delete: return
        reply = QMessageBox.question(self, "Delete Exercise", 
                                     f"Are you sure you want to delete this exercise?",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            parent_lesson_item = item.parent()
            parent_lesson: Lesson = parent_lesson_item.data(0, Qt.UserRole) if parent_lesson_item else None
            if parent_lesson:
                parent_lesson.exercises = [e for e in parent_lesson.exercises if e.exercise_id != exercise_to_delete.exercise_id]
                self.update_tree_view()
                self._set_dirty_state(True)
                self._clear_editor_pane()
                self.item_actions_widget.setVisible(False)
    
    def _expand_and_select_item(self, item_data_obj: Any):
        def find_and_select(parent_item, target_data_obj):
            for i in range(parent_item.childCount()):
                child_item = parent_item.child(i)
                if child_item.data(0, Qt.UserRole) is target_data_obj:
                    self.tree_widget.setCurrentItem(child_item) # Selects the item
                    self.tree_widget.expandItem(parent_item)    # Ensure parent is expanded
                    if child_item.childCount() > 0:             # If the item itself has children, expand it
                        self.tree_widget.expandItem(child_item)
                    self.tree_widget.scrollToItem(child_item)   # Scroll to make it visible
                    return True
                if find_and_select(child_item, target_data_obj):
                    return True
            return False

        hidden_root = self.tree_widget.invisibleRootItem()
        find_and_select(hidden_root, item_data_obj)


    def update_tree_view(self):
        # Store expanded state and selection
        expanded_items_data = {} # Store item_data -> isExpanded
        selected_item_data = None
        
        current_sel_item = self.tree_widget.currentItem()
        if current_sel_item:
            selected_item_data = current_sel_item.data(0, Qt.UserRole)

        iterator = QTreeWidgetItemIterator(self.tree_widget)
        while iterator.value():
            item = iterator.value()
            item_data = item.data(0, Qt.UserRole)
            if item_data: # Only store if data exists (skips header)
                expanded_items_data[id(item_data)] = item.isExpanded() # Use id for hashable key
            iterator += 1

        self.tree_widget.clear()
        if not self.course_data:
            return

        manifest_item_data = {"type": "manifest", "manifest_data": self.manifest_data, "course_obj": self.course_data}
        manifest_item = QTreeWidgetItem(self.tree_widget, ["Manifest Info"])
        manifest_item.setData(0, Qt.UserRole, manifest_item_data)
        manifest_item.setFont(0, QFont("Arial", 11, QFont.Bold))
        if id(manifest_item_data) in expanded_items_data and expanded_items_data[id(manifest_item_data)]:
            manifest_item.setExpanded(True)


        for unit in self.course_data.units:
            unit_item = QTreeWidgetItem(self.tree_widget, [unit.title])
            unit_item.setData(0, Qt.UserRole, unit)
            unit_item.setFont(0, QFont("Arial", 10, QFont.Bold))
            if id(unit) in expanded_items_data and expanded_items_data[id(unit)]:
                unit_item.setExpanded(True)

            for lesson in unit.lessons:
                lesson_item = QTreeWidgetItem(unit_item, [lesson.title])
                lesson_item.setData(0, Qt.UserRole, lesson)
                if id(lesson) in expanded_items_data and expanded_items_data[id(lesson)]:
                    lesson_item.setExpanded(True)

                for idx, exercise in enumerate(lesson.exercises):
                    ex_display_text = f"[{exercise.type}] {exercise.prompt or exercise.source_word or exercise.sentence_template or 'No Prompt'}"
                    exercise_item = QTreeWidgetItem(lesson_item, [ex_display_text])
                    exercise_item.setData(0, Qt.UserRole, exercise)
                    # Exercises are leaf nodes, no need to manage expanded state

        # Restore selection if possible
        if selected_item_data:
            self._expand_and_select_item(selected_item_data)


    def new_course(self):
        if self.is_dirty:
            reply = QMessageBox.question(self, "Unsaved Changes",
                                         "You have unsaved changes. Do you want to save them before creating a new course?",
                                         QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
            if reply == QMessageBox.Save:
                if not self.save_course(): return
            elif reply == QMessageBox.Cancel: return

        self.manifest_data, self.course_data = create_new_course()
        self.current_manifest_path = None
        self.current_course_content_path = None
        self.update_tree_view()
        self._set_dirty_state(False)
        self._clear_editor_pane()
        self.tree_widget.setCurrentItem(self.tree_widget.topLevelItem(0))
        self.item_actions_widget.setVisible(False)

        self.current_file_label.setText("New Course (Unsaved)")
        self._set_dirty_state(False) # A new course is initially not "dirty" from a file perspective
        self.status_bar.showMessage("New course created.", 3000)


    def open_course(self):
        if self.is_dirty:
            reply = QMessageBox.question(self, "Unsaved Changes",
                                         "You have unsaved changes. Do you want to save them before opening a new course?",
                                         QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
            if reply == QMessageBox.Save:
                if not self.save_course():
                    return
            elif reply == QMessageBox.Cancel:
                return

        manifest_file, _ = QFileDialog.getOpenFileName(self, "Open Manifest File", 
                                                       "", "YAML Files (*.yaml *.yml);;All Files (*)")
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
            description=description
        )

        if not self.course_data:
            QMessageBox.critical(self, "Load Error", "Failed to load course content file.")
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
        return self._do_save(self.current_manifest_path, self.current_course_content_path)

    def save_course_as(self):
        manifest_file, _ = QFileDialog.getSaveFileName(self, "Save Manifest File As", "manifest.yaml", "YAML Files (*.yaml *.yml);;All Files (*)")
        if not manifest_file: return False

        manifest_dir = os.path.dirname(manifest_file)
        course_id_for_filename = self.manifest_data.get("course_id", str(uuid.uuid4().hex[:8])) 
        content_filename_from_manifest = self.manifest_data.get("content_file", f"course_{course_id_for_filename}.yaml")
        content_file_path = os.path.join(manifest_dir, content_filename_from_manifest)
        self.manifest_data['content_file'] = os.path.basename(content_file_path)
        return self._do_save(manifest_file, content_file_path)

    def _do_save(self, manifest_file: str, content_file: str):
        if not self.manifest_data or not self.course_data:
            QMessageBox.warning(self, "Save Error", "No course data to save.")
            return False

        if self.current_editor_widget == self.manifest_editor:
            self.manifest_editor.apply_changes_to_data(self.manifest_data, self.course_data)

        if not save_manifest(self.manifest_data, manifest_file):
            QMessageBox.critical(self, "Save Error", "Failed to save manifest file.")
            return False

        course_data_to_save_dict = self.course_data.to_dict() # Uses the to_dict from core.models.Course
        # Use save_course_data from csv_importer module (which uses yaml.safe_dump)
        try:
            with open(content_file, 'w', encoding='utf-8') as f:
                yaml.safe_dump(course_data_to_save_dict, f, indent=2, sort_keys=False, allow_unicode=True)
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Failed to save course content file: {e}")
            return False
        
        self.current_manifest_path = manifest_file
        self.current_course_content_path = content_file
        self.current_file_label.setText(os.path.basename(self.current_manifest_path))
        self._set_dirty_state(False) # Now it's saved
        self.status_bar.showMessage("Course saved successfully!", 3000)
        QMessageBox.information(self, "Save Successful", "Course and Manifest saved successfully!")
        return True

    def closeEvent(self, event):
        if self.is_dirty:
            reply = QMessageBox.question(self, "Unsaved Changes",
                                         "You have unsaved changes. Do you want to save them before exiting?",
                                         QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
            if reply == QMessageBox.Save:
                if not self.save_course(): event.ignore(); return
            elif reply == QMessageBox.Cancel: event.ignore(); return
        event.accept()

    # --- Slots for Integrated Tools ---

    def validate_current_course(self):
        if not self.manifest_data or not self.course_data:
            QMessageBox.warning(self, "Validation Error", "No course loaded to validate.")
            return
        if not self.current_manifest_path:
            QMessageBox.warning(self, "Validation Error", "Manifest path unknown. Please save the course first.")
            return
        if self.is_dirty:
            reply = QMessageBox.question(self, "Unsaved Changes",
                                         "You have unsaved changes. It's recommended to save before validating. Save now?",
                                         QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
            if reply == QMessageBox.Save:
                if not self.save_course(): return
            elif reply == QMessageBox.Cancel: return

        all_errors = []
        logger.info(f"Validating manifest: {self.current_manifest_path}")
        manifest_errors = perform_manifest_validation(self.manifest_data, self.current_manifest_path)
        all_errors.extend(manifest_errors)

        if self.current_course_content_path:
            course_content_base_dir = os.path.dirname(self.current_course_content_path)
            content_errors = perform_course_content_validation(self.course_data, course_content_base_dir) # Pass base_dir
            all_errors.extend(content_errors)
        else:
            all_errors.append("Error: Course content path is unknown, cannot validate asset file paths.")

        logger.info(f"Validating course content for: {self.course_data.title}")
        content_errors = perform_course_content_validation(self.course_data, course_content_base_dir)
        all_errors.extend(content_errors)

        if not all_errors:
            QMessageBox.information(self, "Validation Result", "Validation Successful! No errors found.")
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
             QMessageBox.warning(self, "Import Error", "Please open or create a course first before importing CSV data.")
             return
        if not self.current_course_content_path:
            QMessageBox.warning(self, "Import Error", "Course content file path is not set. Please save your course first.")
            return

        selected_item = self.tree_widget.currentItem()
        default_unit_id, default_lesson_id = "", ""
        if selected_item:
            item_data = selected_item.data(0, Qt.UserRole)
            if isinstance(item_data, Lesson):
                default_lesson_id = item_data.lesson_id
                if item_data.unit_id: default_unit_id = item_data.unit_id
            elif isinstance(item_data, Unit):
                default_unit_id = item_data.unit_id

        dialog = CsvImportDialog(self, default_unit_id, default_lesson_id)
        if dialog.exec() == QDialog.Accepted:
            data = dialog.get_data()
            course_dict_for_import = load_existing_course_data(self.current_course_content_path)
            if not course_dict_for_import:
                QMessageBox.critical(self, "Import Error", f"Could not load current course content from {self.current_course_content_path}")
                return

            success, messages = import_csv_data(
                csv_filepath=data["csv_filepath"],
                existing_course_data=course_dict_for_import,
                exercise_type=data["exercise_type"],
                unit_id=data["unit_id"], unit_title=data["unit_title"],
                lesson_id=data["lesson_id"], lesson_title=data["lesson_title"],
                **data["custom_cols"]
            )
            result_message = "\n".join(messages)
            if success:
                save_course_data(course_dict_for_import, self.current_course_content_path)
                reloaded_course = load_course_content_from_yaml(self.current_course_content_path, self.manifest_data)
                if reloaded_course:
                    self.course_data = reloaded_course
                    self.update_tree_view()
                    self._set_dirty_state(False)
                    QMessageBox.information(self, "Import Successful", f"CSV data imported.\n{result_message}")
                else:
                    QMessageBox.critical(self, "Import Error", "CSV imported, but failed to reload course data into editor.")
            else:
                QMessageBox.warning(self, "Import Failed", f"Could not import CSV data.\n{result_message}")

    def create_course_package(self):
        if not self.current_manifest_path:
            QMessageBox.warning(self, "Packaging Error", "Please open or save a course (manifest) first.")
            return
        
        default_package_name_stem = ""
        if self.manifest_data:
            course_id = self.manifest_data.get("course_id", "course").replace(' ', '_')
            version = self.manifest_data.get("version", "1.0").replace(' ', '_')
            default_package_name_stem = f"{course_id}_{version}"

        dialog = PackageCreationDialog(self, self.current_manifest_path, default_package_name_stem)
        if dialog.exec() == QDialog.Accepted:
            data = dialog.get_data()
            success, package_path, messages = create_package_for_gui(
                manifest_filepath=data["manifest_filepath"],
                output_dir_override=data["output_dir"],
                package_name_override=data["package_name_override"]
            )
            result_message = "\n".join(messages)
            if success and package_path:
                QMessageBox.information(self, "Packaging Successful", f"Course packaged successfully!\nPackage at: {package_path}\n\nDetails:\n{result_message}\nUnzip it using 7zip and place it in the same folder as main.")
            else:
                QMessageBox.critical(self, "Packaging Failed", f"Could not create course package.\n\nDetails:\n{result_message}")