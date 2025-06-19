# application/tools/widgets/course_tree_widget.py

import logging
import json
import uuid
from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem, QMessageBox
from PySide6.QtCore import Qt, QMimeData, QByteArray, Signal
from typing import Any, List, Optional
from application.core.models import Course, Unit, Lesson, Exercise


logger = logging.getLogger(__name__)

# Define a custom MIME type for our draggable items
_LL_ITEM_MIME_TYPE = "application/x-lingua-learn-item"


class CourseTreeWidget(QTreeWidget):
    # Signal to notify EditorWindow about a data model change requiring tree refresh
    # Emits (moved_obj, new_parent_obj)
    data_model_reordered = Signal(object, object)

    def __init__(self, course_data: Any, parent=None):
        super().__init__(parent)
        self.course_data = course_data  # Reference to the top-level Course object
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        # Use DragDropMode.DragDrop for full control over drop logic
        self.setDragDropMode(QTreeWidget.DragDrop)
        self.setSelectionMode(
            QTreeWidget.SingleSelection
        )  # Ensure only one item dragged at a time

    def supportedDropActions(self) -> Qt.DropActions:
        return Qt.MoveAction  # We only support moving items

    def mimeTypes(self) -> List[str]:
        """Declare the custom MIME types this widget can provide for drag operations."""
        return [_LL_ITEM_MIME_TYPE]

    def mimeData(self, items: List[QTreeWidgetItem]) -> QMimeData:
        """
        Creates a QMimeData object containing the data for the dragged items.
        We serialize the unique ID of the underlying Python object.
        """
        mime_data = QMimeData()
        if not items:
            return mime_data

        item = items[0]  # Assuming SingleSelection, so only one item
        obj = item.data(0, Qt.UserRole)

        if obj is None:
            return mime_data

        # Store object's ID and type for later lookup
        item_data = {
            "id": id(obj),  # Unique ID of the Python object in memory
            "type": type(obj).__name__,  # Class name for type checking
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
        """
        Handles the drop event. Deserializes the MIME data, identifies the
        dragged object, determines the new parent and position, and updates
        the underlying data model.
        """
        if not data.hasFormat(_LL_ITEM_MIME_TYPE):
            logger.warning("Drop event: MIME data format not supported.")
            return False
        if action != Qt.MoveAction:
            logger.warning("Drop event: Only MoveAction is supported.")
            return False

        try:
            json_data = data.data(_LL_ITEM_MIME_TYPE).data().decode("utf-8")
            item_data = json.loads(json_data)
            dragged_obj_id = item_data.get("id")
            dragged_obj_type_str = item_data.get("type")
        except (json.JSONDecodeError, AttributeError, TypeError) as e:
            logger.error(f"Failed to parse MIME data: {e}")
            return False

        # Find the actual Python object being dragged
        dragged_obj, original_parent_obj, original_list, original_index = (
            self._find_obj_and_context_by_id(dragged_obj_id, self.course_data)
        )

        if not dragged_obj:
            logger.error(f"Dragged object with ID {dragged_obj_id} not found in model.")
            return False

        # Determine the target parent object based on the drop location
        new_parent_obj = None
        if parent_item:
            new_parent_obj = parent_item.data(0, Qt.UserRole)
            if (
                new_parent_obj is None
            ):  # Dropped on manifest item or other non-data item
                logger.warning(f"Drop on invalid parent item: {parent_item.text(0)}")
                QMessageBox.warning(
                    self, "Invalid Drop Location", "Cannot drop items here."
                )
                return False

        # Validate the drop type (e.g., Unit can only be top-level, Lesson in Unit, Exercise in Lesson)
        is_valid_drop = self._validate_drop_target(dragged_obj, new_parent_obj)
        if not is_valid_drop:
            QMessageBox.warning(
                self,
                "Invalid Move",
                f"A {type(dragged_obj).__name__} cannot be dropped into a {type(new_parent_obj).__name__ if new_parent_obj else 'top-level'}.",
            )
            return False

        # Determine the target list (where the object will be inserted)
        target_list: Optional[List[Any]] = self._get_target_list(new_parent_obj)
        if target_list is None:
            logger.error(
                f"Could not determine target list for new parent {new_parent_obj}."
            )
            QMessageBox.critical(
                self, "Internal Error", "Could not determine target list for drop."
            )
            return False

        # Calculate the new index
        # 'index' from dropMimeData is the row where data should be inserted.
        # If dropping onto an item (index == -1), it means it should be a child.
        # However, our drop validation already directs 'OnItem' drops to valid parents,
        # so 'index' here should generally be a valid sibling insertion point, or -1 for 'OnItem' child.
        # In this implementation, we use 'index' as the insertion point into the target list.
        new_insert_index = index if index != -1 else len(target_list)

        # Handle moving within the same list vs. moving to a new list
        if original_list is target_list:
            if original_index < new_insert_index:
                new_insert_index -= (
                    1  # Adjust index if removing from before insert point
                )
            moved_obj_from_list = original_list.pop(original_index)
            target_list.insert(new_insert_index, moved_obj_from_list)
        else:
            # Moving to a new parent/list
            if (
                original_list and dragged_obj in original_list
            ):  # Ensure it's still there
                original_list.remove(dragged_obj)  # Remove by value, not index
            else:
                logger.error(
                    f"Dragged object {dragged_obj_id} not found in its original list during removal."
                )
                return (
                    False  # Should not happen if _find_obj_and_context_by_id is robust
                )

            # Update parent references if moving a Lesson to a new Unit
            if isinstance(dragged_obj, Lesson) and isinstance(new_parent_obj, Unit):
                dragged_obj.unit_id = new_parent_obj.unit_id
                # Regenerate exercise_ids for children for consistency if parent changes
                for ex in dragged_obj.exercises:
                    # Regenerate exercise_id to reflect new lesson_id context if needed
                    # For simplicity, we just assign a new UUID part, assuming lesson_id is part of ex_id prefix
                    # A more robust ID system might be fully UUID-based.
                    ex.exercise_id = f"{dragged_obj.lesson_id}_ex{dragged_obj.exercises.index(ex)}_{uuid.uuid4().hex[:4]}"

            target_list.insert(new_insert_index, dragged_obj)

        # Emit signal to EditorWindow to refresh tree view
        self.data_model_reordered.emit(dragged_obj, new_parent_obj)
        return True

    def _validate_drop_target(self, dragged_obj: Any, new_parent_obj: Any) -> bool:
        """
        Validates if dragged_obj can be dropped as a child of new_parent_obj.
        """
        if isinstance(dragged_obj, Unit):
            # Units can only be top-level items (no parent_obj)
            return new_parent_obj is None
        elif isinstance(dragged_obj, Lesson):
            # Lessons can only be children of Units
            return isinstance(new_parent_obj, Unit)
        elif isinstance(dragged_obj, Exercise):
            # Exercises can only be children of Lessons
            return isinstance(new_parent_obj, Lesson)
        return False  # Unknown object type

    def _get_target_list(self, new_parent_obj: Any) -> Optional[List[Any]]:
        """
        Returns the specific Python list where the dragged object should be inserted.
        """
        if new_parent_obj is None:  # Top-level (for Units)
            return self.course_data.units
        elif isinstance(new_parent_obj, Unit):
            if not hasattr(new_parent_obj, "lessons"):
                new_parent_obj.lessons = []  # Initialize if not present
            return new_parent_obj.lessons
        elif isinstance(new_parent_obj, Lesson):
            if not hasattr(new_parent_obj, "exercises"):
                new_parent_obj.exercises = []  # Initialize if not present
            return new_parent_obj.exercises
        return None

    def _find_obj_and_context_by_id(
        self,
        obj_id: int,
        current_obj: Any,
        parent_obj: Any = None,
        current_list: Optional[List[Any]] = None,
    ) -> tuple[Any, Any, Optional[List[Any]], int]:
        """
        Recursively finds the Python object by its ID and returns its context (parent, list, index).
        Returns (found_obj, parent_of_found_obj, list_containing_found_obj, index_in_list).
        """
        if id(current_obj) == obj_id:
            return (
                current_obj,
                parent_obj,
                current_list,
                current_list.index(current_obj) if current_list else -1,
            )

        # Search in lists (units, lessons, exercises)
        if isinstance(current_obj, (Course, Unit, Lesson)):
            if hasattr(current_obj, "units") and isinstance(current_obj.units, list):
                for i, unit in enumerate(current_obj.units):
                    found_obj, p_obj, l_list, idx = self._find_obj_and_context_by_id(
                        obj_id, unit, current_obj, current_obj.units
                    )
                    if found_obj:
                        return found_obj, p_obj, l_list, idx

            if hasattr(current_obj, "lessons") and isinstance(
                current_obj.lessons, list
            ):
                for i, lesson in enumerate(current_obj.lessons):
                    found_obj, p_obj, l_list, idx = self._find_obj_and_context_by_id(
                        obj_id, lesson, current_obj, current_obj.lessons
                    )
                    if found_obj:
                        return found_obj, p_obj, l_list, idx

            if hasattr(current_obj, "exercises") and isinstance(
                current_obj.exercises, list
            ):
                for i, exercise in enumerate(current_obj.exercises):
                    found_obj, p_obj, l_list, idx = self._find_obj_and_context_by_id(
                        obj_id, exercise, current_obj, current_obj.exercises
                    )
                    if found_obj:
                        return found_obj, p_obj, l_list, idx

        return None, None, None, -1  # Not found
