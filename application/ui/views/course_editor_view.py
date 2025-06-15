import logging
import os
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QTreeView, QStackedWidget, QPushButton,
    QMessageBox, QToolBar, QMenu, QInputDialog, QLabel
)
from PySide6.QtGui import QStandardItemModel, QStandardItem, QIcon, QAction
from PySide6.QtCore import Qt, Signal

from core.course_manager import CourseManager
from core.models import Unit, Lesson, Exercise
from ui.widgets.editor_forms import UnitEditorForm, LessonEditorForm, ExerciseEditorForm
from core import yaml_serializer

logger = logging.getLogger(__name__)

class CourseEditorView(QWidget):
    editor_closed = Signal()

    def __init__(self, course_manager: CourseManager, parent=None):
        super().__init__(parent)
        self.course_manager = course_manager
        self.is_dirty = False # To track unsaved changes

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        self._setup_toolbar(main_layout)
        
        content_layout = QHBoxLayout()
        main_layout.addLayout(content_layout)

        # Left: Tree View
        self.tree_view = QTreeView()
        self.tree_model = QStandardItemModel()
        self.tree_view.setModel(self.tree_model)
        self.tree_view.setHeaderHidden(True)
        content_layout.addWidget(self.tree_view, 1)

        # Right: Editor Forms Stack
        self.form_stack = QStackedWidget()
        content_layout.addWidget(self.form_stack, 3)

        self._setup_forms()
        self._populate_tree()

        self.tree_view.selectionModel().selectionChanged.connect(self._on_selection_changed)
        self.tree_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree_view.customContextMenuRequested.connect(self._show_context_menu)

    def _setup_toolbar(self, layout):
        toolbar = QToolBar("Editor Toolbar")
        layout.addWidget(toolbar)

        save_action = QAction("Save Course", self)
        save_action.triggered.connect(self.save_course)
        toolbar.addAction(save_action)

        close_action = QAction("Close Editor", self)
        close_action.triggered.connect(self.close_editor)
        toolbar.addAction(close_action)

    def _setup_forms(self):
        self.welcome_widget = QLabel("Select an item from the tree to edit it.")
        self.welcome_widget.setAlignment(Qt.AlignCenter)
        self.form_stack.addWidget(self.welcome_widget)

        self.unit_form = UnitEditorForm()
        self.form_stack.addWidget(self.unit_form)
        self.lesson_form = LessonEditorForm()
        self.form_stack.addWidget(self.lesson_form)
        self.exercise_form = ExerciseEditorForm()
        self.form_stack.addWidget(self.exercise_form)
        
        # Connect data changed signals to a single handler
        self.unit_form.data_changed.connect(self._on_data_changed)
        self.lesson_form.data_changed.connect(self._on_data_changed)
        self.exercise_form.data_changed.connect(self._on_data_changed)

    def _populate_tree(self):
        self.tree_model.clear()
        root_item = self.tree_model.invisibleRootItem()
        course = self.course_manager.course
        if not course: return

        for unit in course.units:
            unit_item = QStandardItem(f"Unit: {unit.title}")
            unit_item.setData(unit, Qt.UserRole)
            for lesson in unit.lessons:
                lesson_item = QStandardItem(f"Lesson: {lesson.title}")
                lesson_item.setData(lesson, Qt.UserRole)
                for i, exercise in enumerate(lesson.exercises):
                    ex_item = QStandardItem(f"Ex {i+1}: {exercise.type}")
                    ex_item.setData(exercise, Qt.UserRole)
                    lesson_item.appendRow(ex_item)
                unit_item.appendRow(lesson_item)
            root_item.appendRow(unit_item)
        self.tree_view.expandAll()

    def _on_selection_changed(self, selected, deselected):
        if not selected.indexes():
            self.form_stack.setCurrentWidget(self.welcome_widget)
            return
        
        index = selected.indexes()[0]
        item = self.tree_model.itemFromIndex(index)
        data_obj = item.data(Qt.UserRole)

        if isinstance(data_obj, Unit):
            self.unit_form.load_data(data_obj)
            self.form_stack.setCurrentWidget(self.unit_form)
        elif isinstance(data_obj, Lesson):
            self.lesson_form.load_data(data_obj)
            self.form_stack.setCurrentWidget(self.lesson_form)
        elif isinstance(data_obj, Exercise):
            self.exercise_form.load_data(data_obj)
            self.form_stack.setCurrentWidget(self.exercise_form)
        else:
            self.form_stack.setCurrentWidget(self.welcome_widget)

    def _show_context_menu(self, position):
        # Basic context menu for adding/deleting items
        pass # To be implemented later for full functionality

    def save_course(self):
        """Saves the entire course (content, glossary, manifest) to their files."""
        logger.info("Attempting to save the course...")
        try:
            # Get paths from the course manager
            manifest_dir = os.path.dirname(self.course_manager.manifest_path)
            content_filename = self.course_manager.manifest_data.get("content_file")
            glossary_filename = self.course_manager.manifest_data.get("glossary_file")

            # Save course content
            if content_filename:
                content_filepath = os.path.join(manifest_dir, content_filename)
                yaml_serializer.save_course_to_yaml(self.course_manager.course, content_filepath)
            
            # Save glossary
            if glossary_filename:
                glossary_filepath = os.path.join(manifest_dir, glossary_filename)
                yaml_serializer.save_glossary_to_yaml(self.course_manager.glossary, glossary_filepath)
            
            # Save manifest (in case any top-level keys were changed, though we don't support that yet)
            yaml_serializer.save_manifest_to_yaml(self.course_manager.manifest_data, self.course_manager.manifest_path)
            
            QMessageBox.information(self, self.tr("Save Successful"), self.tr("The course has been saved successfully."))
            self.is_dirty = False
        except Exception as e:
            logger.error(f"Failed to save course: {e}", exc_info=True)
            QMessageBox.critical(self, self.tr("Save Failed"), self.tr("An error occurred while saving the course.\nCheck the logs for details."))

    def close_editor(self):
        if self.is_dirty:
            reply = QMessageBox.question(self, "Unsaved Changes",
                "You have unsaved changes. Do you want to save before closing?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
            if reply == QMessageBox.Save:
                self.save_course()
            elif reply == QMessageBox.Cancel:
                return
        self.editor_closed.emit()
    
    def _on_data_changed(self):
        """Marks the state as dirty and updates the text of the selected tree item."""
        self.is_dirty = True
        
        indexes = self.tree_view.selectionModel().selectedIndexes()
        if not indexes: return
        
        item = self.tree_model.itemFromIndex(indexes[0])
        data_obj = item.data(Qt.UserRole)
        
        # Update the display text in the tree
        if isinstance(data_obj, Unit):
            item.setText(f"Unit: {data_obj.title}")
        elif isinstance(data_obj, Lesson):
            item.setText(f"Lesson: {data_obj.title}")
        elif isinstance(data_obj, Exercise):
            item.setText(f"Ex {item.row() + 1}: {data_obj.type}")