"""QUndoCommand classes for course editor operations."""

import copy
from typing import Any
from PySide6.QtGui import QUndoCommand
from application.core.models import Unit, Lesson, Exercise


class AddUnitCommand(QUndoCommand):
    def __init__(self, editor: Any, unit: Unit, index: int | None = None):
        super().__init__(f"Add Unit '{unit.title}'")
        self.editor = editor
        self.unit = unit
        self.index = index if index is not None else len(editor.course_data.units)

    def redo(self):
        self.editor.course_data.units.insert(self.index, self.unit)
        self.editor.update_tree_view()
        self.editor._expand_and_select_item(self.unit)

    def undo(self):
        if self.unit in self.editor.course_data.units:
            self.editor.course_data.units.remove(self.unit)
        self.editor.update_tree_view()
        self.editor._clear_editor_pane()
        self.editor.item_actions_widget.setVisible(False)


class DeleteUnitCommand(QUndoCommand):
    def __init__(self, editor: Any, unit: Unit):
        super().__init__(f"Delete Unit '{unit.title}'")
        self.editor = editor
        self.unit = unit
        self.index = editor.course_data.units.index(unit)

    def redo(self):
        if self.unit in self.editor.course_data.units:
            self.editor.course_data.units.remove(self.unit)
        self.editor.update_tree_view()
        self.editor._clear_editor_pane()
        self.editor.item_actions_widget.setVisible(False)

    def undo(self):
        self.editor.course_data.units.insert(self.index, self.unit)
        self.editor.update_tree_view()
        self.editor._expand_and_select_item(self.unit)


class AddLessonCommand(QUndoCommand):
    def __init__(self, editor: Any, unit: Unit, lesson: Lesson, index: int | None = None):
        super().__init__(f"Add Lesson '{lesson.title}'")
        self.editor = editor
        self.unit = unit
        self.lesson = lesson
        self.index = index if index is not None else len(unit.lessons)

    def redo(self):
        self.unit.lessons.insert(self.index, self.lesson)
        self.editor.update_tree_view()
        self.editor._expand_and_select_item(self.lesson)

    def undo(self):
        if self.lesson in self.unit.lessons:
            self.unit.lessons.remove(self.lesson)
        self.editor.update_tree_view()
        self.editor._clear_editor_pane()
        self.editor.item_actions_widget.setVisible(False)


class DeleteLessonCommand(QUndoCommand):
    def __init__(self, editor: Any, unit: Unit, lesson: Lesson):
        super().__init__(f"Delete Lesson '{lesson.title}'")
        self.editor = editor
        self.unit = unit
        self.lesson = lesson
        self.index = unit.lessons.index(lesson)

    def redo(self):
        if self.lesson in self.unit.lessons:
            self.unit.lessons.remove(self.lesson)
        self.editor.update_tree_view()
        self.editor._clear_editor_pane()
        self.editor.item_actions_widget.setVisible(False)

    def undo(self):
        self.unit.lessons.insert(self.index, self.lesson)
        self.editor.update_tree_view()
        self.editor._expand_and_select_item(self.lesson)


class AddExerciseCommand(QUndoCommand):
    def __init__(self, editor: Any, lesson: Lesson, exercise: Exercise, index: int | None = None):
        super().__init__(f"Add Exercise ({exercise.type})")
        self.editor = editor
        self.lesson = lesson
        self.exercise = exercise
        self.index = index if index is not None else len(lesson.exercises)

    def redo(self):
        self.lesson.exercises.insert(self.index, self.exercise)
        self.editor.update_tree_view()
        self.editor._expand_and_select_item(self.exercise)

    def undo(self):
        if self.exercise in self.lesson.exercises:
            self.lesson.exercises.remove(self.exercise)
        self.editor.update_tree_view()
        self.editor._clear_editor_pane()
        self.editor.item_actions_widget.setVisible(False)


class DeleteExerciseCommand(QUndoCommand):
    def __init__(self, editor: Any, lesson: Lesson, exercise: Exercise):
        super().__init__(f"Delete Exercise ({exercise.type})")
        self.editor = editor
        self.lesson = lesson
        self.exercise = exercise
        self.index = lesson.exercises.index(exercise)

    def redo(self):
        if self.exercise in self.lesson.exercises:
            self.lesson.exercises.remove(self.exercise)
        self.editor.update_tree_view()
        self.editor._clear_editor_pane()
        self.editor.item_actions_widget.setVisible(False)

    def undo(self):
        self.lesson.exercises.insert(self.index, self.exercise)
        self.editor.update_tree_view()
        self.editor._expand_and_select_item(self.exercise)
