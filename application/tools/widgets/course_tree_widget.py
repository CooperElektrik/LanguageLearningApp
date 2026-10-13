# application/tools/widgets/course_tree_widget.py

import json
import logging
import uuid
from typing import Any

from PySide6.QtCore import QByteArray, QMimeData, Qt, Signal
from PySide6.QtWidgets import QMessageBox, QTreeWidget, QTreeWidgetItem

from application.core.models import Course, Exercise, Lesson, Unit

logger = logging.getLogger(__name__)

# Define a custom MIME type for our draggable items
_LL_ITEM_MIME_TYPE = "application/x-lingua-learn-item"

EXERCISE_TYPE_BADGES = {
    "multiple_choice_translation": "[MCQ]",
    "translate_to_target": "[TRANS→]",
    "translate_to_source": "[TRANS←]",
    "fill_in_the_blank": "[FIB]",
    "dictation": "[DICT]",
    "image_association": "[IMG-MCQ]",
    "listen_and_select": "[L&S]",
    "sentence_jumble": "[JUMB]",
    "context_block": "[CONT]",
    "pronunciation_practice": "[PRON]",
}


class CourseTreeWidget(QTreeWidget):
    """
    Hierarchical tree widget for course units, lessons, and exercises.
    Supports drag-and-drop reordering, status badges (audio, image, exercise type),
    and inline action triggers.
    """

    # Signal to notify EditorWindow about a data model change requiring tree refresh
    # Emits (moved_obj, new_parent_obj)
    data_model_reordered = Signal(object, object)
    inline_add_requested = Signal(str, object)  # ("unit"|"lesson"|"exercise", parent_obj)

    def __init__(self, course_data: Any = None, parent=None):
        super().__init__(parent)
        self.course_data = course_data  # Reference to the top-level Course object
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QTreeWidget.DragDrop)
        self.setSelectionMode(QTreeWidget.SingleSelection)
        self.itemClicked.connect(self._handle_item_clicked)

    def set_course_data(self, course_data: Any):
        self.course_data = course_data

    @staticmethod
    def get_exercise_type_badge(exercise_type: str) -> str:
        return EXERCISE_TYPE_BADGES.get(exercise_type, f"[{exercise_type[:4].upper()}]")

    @staticmethod
    def get_asset_badges(exercise: Exercise) -> str:
        parts = []
        if getattr(exercise, "audio_file", None):
            parts.append("[AUDIO]")
        if getattr(exercise, "image_file", None):
            parts.append("[IMAGE]")
        return " ".join(parts)

    def supportedDropActions(self) -> Qt.DropActions:
        return Qt.MoveAction

    def mimeTypes(self) -> list[str]:
        return [_LL_ITEM_MIME_TYPE]

    def mimeData(self, items: list[QTreeWidgetItem]) -> QMimeData:
        mime_data = QMimeData()
        if not items:
            return mime_data

        item = items[0]
        obj = item.data(0, Qt.UserRole)
        if obj is None or isinstance(obj, dict):
            return mime_data

        item_data = {
            "id": id(obj),
            "type": type(obj).__name__,
        }
        json_data = json.dumps(item_data).encode("utf-8")
        mime_data.setData(_LL_ITEM_MIME_TYPE, QByteArray(json_data))
        return mime_data

    def dropMimeData(
        self,
        parent_item: QTreeWidgetItem,
        index: int,
        data: QMimeData,
        action: Qt.DropAction,
    ) -> bool:
        if not data.hasFormat(_LL_ITEM_MIME_TYPE):
            return False
        if action != Qt.MoveAction:
            return False

        try:
            json_data = data.data(_LL_ITEM_MIME_TYPE).data().decode("utf-8")
            item_data = json.loads(json_data)
            dragged_obj_id = item_data.get("id")
        except (json.JSONDecodeError, AttributeError, TypeError) as e:
            logger.error(f"Failed to parse MIME data: {e}")
            return False

        dragged_obj, _orig_parent, original_list, original_index = self._find_obj_and_context_by_id(
            dragged_obj_id, self.course_data
        )

        if not dragged_obj:
            return False

        new_parent_obj = None
        if parent_item:
            new_parent_obj = parent_item.data(0, Qt.UserRole)
            if isinstance(new_parent_obj, dict):
                return False

        is_valid_drop = self._validate_drop_target(dragged_obj, new_parent_obj)
        if not is_valid_drop:
            QMessageBox.warning(
                self,
                "Invalid Move",
                f"A {type(dragged_obj).__name__} cannot be placed here.",
            )
            return False

        target_list = self._get_target_list(new_parent_obj)
        if target_list is None:
            return False

        new_insert_index = index if index != -1 else len(target_list)

        if original_list is target_list:
            if original_index < new_insert_index:
                new_insert_index -= 1
            moved_obj = original_list.pop(original_index)
            target_list.insert(new_insert_index, moved_obj)
        else:
            if original_list and dragged_obj in original_list:
                original_list.remove(dragged_obj)
            else:
                return False

            if isinstance(dragged_obj, Lesson) and isinstance(new_parent_obj, Unit):
                dragged_obj.unit_id = new_parent_obj.unit_id
                for ex in dragged_obj.exercises:
                    ex.exercise_id = f"{dragged_obj.lesson_id}_ex{dragged_obj.exercises.index(ex)}_{uuid.uuid4().hex[:4]}"

            target_list.insert(new_insert_index, dragged_obj)

        self.data_model_reordered.emit(dragged_obj, new_parent_obj)
        return True

    def _validate_drop_target(self, dragged_obj: Any, new_parent_obj: Any) -> bool:
        if isinstance(dragged_obj, Unit):
            return new_parent_obj is None
        elif isinstance(dragged_obj, Lesson):
            return isinstance(new_parent_obj, Unit)
        elif isinstance(dragged_obj, Exercise):
            return isinstance(new_parent_obj, Lesson)
        return False

    def _get_target_list(self, new_parent_obj: Any) -> list[Any] | None:
        if new_parent_obj is None:
            return self.course_data.units if self.course_data else None
        elif isinstance(new_parent_obj, Unit):
            if not hasattr(new_parent_obj, "lessons") or new_parent_obj.lessons is None:
                new_parent_obj.lessons = []
            return new_parent_obj.lessons
        elif isinstance(new_parent_obj, Lesson):
            if not hasattr(new_parent_obj, "exercises") or new_parent_obj.exercises is None:
                new_parent_obj.exercises = []
            return new_parent_obj.exercises
        return None

    def _find_obj_and_context_by_id(
        self,
        obj_id: int,
        current_obj: Any,
        parent_obj: Any = None,
        current_list: list[Any] | None = None,
    ) -> tuple[Any, Any, list[Any] | None, int]:
        if id(current_obj) == obj_id:
            return (
                current_obj,
                parent_obj,
                current_list,
                current_list.index(current_obj) if current_list else -1,
            )

        if isinstance(current_obj, (Course, Unit, Lesson)):
            if hasattr(current_obj, "units") and isinstance(current_obj.units, list):
                for unit in current_obj.units:
                    found_obj, p_obj, l_list, idx = self._find_obj_and_context_by_id(
                        obj_id, unit, current_obj, current_obj.units
                    )
                    if found_obj:
                        return found_obj, p_obj, l_list, idx

            if hasattr(current_obj, "lessons") and isinstance(current_obj.lessons, list):
                for lesson in current_obj.lessons:
                    found_obj, p_obj, l_list, idx = self._find_obj_and_context_by_id(
                        obj_id, lesson, current_obj, current_obj.lessons
                    )
                    if found_obj:
                        return found_obj, p_obj, l_list, idx

            if hasattr(current_obj, "exercises") and isinstance(current_obj.exercises, list):
                for exercise in current_obj.exercises:
                    found_obj, p_obj, l_list, idx = self._find_obj_and_context_by_id(
                        obj_id, exercise, current_obj, current_obj.exercises
                    )
                    if found_obj:
                        return found_obj, p_obj, l_list, idx

        return None, None, None, -1

    def _handle_item_clicked(self, item: QTreeWidgetItem, column: int):
        data = item.data(0, Qt.UserRole)
        if isinstance(data, dict) and "action" in data:
            action = data.get("action")
            parent_target = data.get("target")
            if action in ["add_unit", "add_lesson", "add_exercise"]:
                self.inline_add_requested.emit(action.replace("add_", ""), parent_target)
