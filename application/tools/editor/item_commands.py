"""Item CRUD commands for the course editor.

These add/duplicate/delete operations were five near-identical method triples
buried in the 1,700-line ``EditorWindow``.  Grouping them here keeps the
god-class in check while leaving the calling code untouched (the methods are
still reached as ``self._add_lesson(...)`` etc.).

The mixin relies on host attributes supplied by ``EditorWindow``:
``course_data``, ``tree_widget``, ``item_actions_widget`` and the helpers
``update_tree_view``, ``_set_dirty_state``, ``_expand_and_select_item`` and
``_clear_editor_pane``.
"""

import copy
import uuid
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox, QTreeWidgetItem

from application.core.exercise_types import CREATABLE_EXERCISE_TYPES
from application.core.models import Exercise, Lesson, Unit

from .undo_commands import (
    AddExerciseCommand,
    AddLessonCommand,
    AddUnitCommand,
    DeleteExerciseCommand,
    DeleteLessonCommand,
    DeleteUnitCommand,
)


class ItemCommandsMixin:
    """Add / duplicate / delete operations using QUndoStack."""

    # --- ID regeneration -------------------------------------------------
    def _generate_new_ids_for_exercise(self, exercise: Exercise):
        ex_id = f"ex_{uuid.uuid4().hex[:8]}"
        exercise.exercise_id = ex_id
        exercise.id = ex_id

    def _generate_new_ids_for_lesson(self, lesson: Lesson):
        lesson.lesson_id = f"lesson_{uuid.uuid4().hex[:8]}"
        for ex in lesson.exercises:
            self._generate_new_ids_for_exercise(ex)

    def _generate_new_ids_for_unit(self, unit: Unit):
        unit.unit_id = f"unit_{uuid.uuid4().hex[:8]}"
        for lesson in unit.lessons:
            lesson.unit_id = unit.unit_id
            self._generate_new_ids_for_lesson(lesson)

    # --- Duplication -----------------------------------------------------
    def _duplicate_unit(self, original_unit_item: QTreeWidgetItem):
        original_unit: Unit = original_unit_item.data(0, Qt.UserRole)
        if not original_unit or not self.course_data:
            return

        new_unit = copy.deepcopy(original_unit)
        self._generate_new_ids_for_unit(new_unit)
        new_unit.title = f"{original_unit.title}_copy"

        original_index = self.course_data.units.index(original_unit)
        if hasattr(self, "undo_stack"):
            self.undo_stack.push(AddUnitCommand(self, new_unit, original_index + 1))
        else:
            self.course_data.units.insert(original_index + 1, new_unit)
            self.update_tree_view()
            self._set_dirty_state(True)
            self._expand_and_select_item(new_unit)

    def _duplicate_lesson(self, original_lesson_item: QTreeWidgetItem):
        original_lesson: Lesson = original_lesson_item.data(0, Qt.UserRole)
        parent_unit_item = original_lesson_item.parent()
        parent_unit: Unit = parent_unit_item.data(0, Qt.UserRole) if parent_unit_item else None

        if not original_lesson or not parent_unit:
            return

        new_lesson = copy.deepcopy(original_lesson)
        new_lesson.unit_id = parent_unit.unit_id
        self._generate_new_ids_for_lesson(new_lesson)
        new_lesson.title = f"{original_lesson.title}_copy"

        original_index = parent_unit.lessons.index(original_lesson)
        if hasattr(self, "undo_stack"):
            self.undo_stack.push(
                AddLessonCommand(self, parent_unit, new_lesson, original_index + 1)
            )
        else:
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
        if hasattr(self, "undo_stack"):
            self.undo_stack.push(
                AddExerciseCommand(self, parent_lesson, new_exercise, original_index + 1)
            )
        else:
            parent_lesson.exercises.insert(original_index + 1, new_exercise)
            self.update_tree_view()
            self._set_dirty_state(True)
            self._expand_and_select_item(new_exercise)

    # --- Units -----------------------------------------------------------
    def _add_unit(self, title: str | None = None):
        if not self.course_data:
            return
        unit_id_suffix = str(uuid.uuid4().hex[:8])
        unit_title = (
            title.strip()
            if title and title.strip()
            else f"New Unit {len(self.course_data.units) + 1}"
        )
        new_unit = Unit(unit_id=f"unit_{unit_id_suffix}", title=unit_title, lessons=[])
        if hasattr(self, "undo_stack"):
            self.undo_stack.push(AddUnitCommand(self, new_unit))
        else:
            self.course_data.units.append(new_unit)
            self.update_tree_view()
            self._set_dirty_state(True)
            self._expand_and_select_item(new_unit)

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
            if hasattr(self, "undo_stack"):
                self.undo_stack.push(DeleteUnitCommand(self, unit_to_delete))
            else:
                self.course_data.units = [
                    u for u in self.course_data.units if u.unit_id != unit_to_delete.unit_id
                ]
                self.update_tree_view()
                self._set_dirty_state(True)
                self._clear_editor_pane()
                self.item_actions_widget.setVisible(False)

    # --- Lessons ---------------------------------------------------------
    def _add_lesson(self, unit_or_item: Any, title: str | None = None):
        unit = unit_or_item if isinstance(unit_or_item, Unit) else unit_or_item.data(0, Qt.UserRole)
        if not unit:
            return
        lesson_id_suffix = str(uuid.uuid4().hex[:8])
        lesson_title = (
            title.strip() if title and title.strip() else f"New Lesson {len(unit.lessons) + 1}"
        )
        new_lesson = Lesson(
            lesson_id=f"lesson_{lesson_id_suffix}",
            title=lesson_title,
            exercises=[],
            unit_id=unit.unit_id,
        )
        if hasattr(self, "undo_stack"):
            self.undo_stack.push(AddLessonCommand(self, unit, new_lesson))
        else:
            unit.lessons.append(new_lesson)
            self.update_tree_view()
            self._set_dirty_state(True)
            self._expand_and_select_item(new_lesson)

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
            parent_unit: Unit = parent_unit_item.data(0, Qt.UserRole) if parent_unit_item else None
            if parent_unit:
                if hasattr(self, "undo_stack"):
                    self.undo_stack.push(DeleteLessonCommand(self, parent_unit, lesson_to_delete))
                else:
                    parent_unit.lessons = [
                        lesson
                        for lesson in parent_unit.lessons
                        if lesson.lesson_id != lesson_to_delete.lesson_id
                    ]
                    self.update_tree_view()
                    self._set_dirty_state(True)
                    self._clear_editor_pane()
                    self.item_actions_widget.setVisible(False)

    # --- Exercises -------------------------------------------------------
    def _add_exercise(self, lesson_or_item: Any, exercise_type: str | None = None):
        lesson = (
            lesson_or_item
            if isinstance(lesson_or_item, Lesson)
            else lesson_or_item.data(0, Qt.UserRole)
        )
        if not lesson:
            return

        item_type_name = exercise_type or CREATABLE_EXERCISE_TYPES[0]
        ex_id = f"{lesson.id}_{uuid.uuid4().hex[:8]}"
        new_exercise = Exercise(exercise_id=ex_id, id=ex_id, type=item_type_name)
        if hasattr(self, "undo_stack"):
            self.undo_stack.push(AddExerciseCommand(self, lesson, new_exercise))
        else:
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
            "Are you sure you want to delete this exercise?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            parent_lesson_item = item.parent()
            parent_lesson: Lesson = (
                parent_lesson_item.data(0, Qt.UserRole) if parent_lesson_item else None
            )
            if parent_lesson:
                if hasattr(self, "undo_stack"):
                    self.undo_stack.push(
                        DeleteExerciseCommand(self, parent_lesson, exercise_to_delete)
                    )
                else:
                    parent_lesson.exercises = [
                        e
                        for e in parent_lesson.exercises
                        if e.exercise_id != exercise_to_delete.exercise_id
                    ]
                    self.update_tree_view()
                    self._set_dirty_state(True)
                    self._clear_editor_pane()
                    self.item_actions_widget.setVisible(False)
