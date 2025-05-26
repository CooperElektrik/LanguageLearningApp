import json
import os
import logging
from typing import Dict, Set, Optional
from PySide6.QtCore import QStandardPaths

logger = logging.getLogger(__name__)

class ProgressManager:
    def __init__(self, course_id: str, data_dir: str = "data"):
        self.course_id = course_id
        
        self.app_data_dir = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
        if not self.app_data_dir:
            logger.warning("Could not determine standard AppDataLocation. Falling back to current working directory.")
            self.app_data_dir = os.getcwd() # Fallback to current working directory

        self.progress_data_dir = os.path.join(self.app_data_dir, "LL", "Progress") # Specific subfolder
        self.progress_file = os.path.join(self.progress_data_dir, f"{self.course_id}_progress.json")
        
        self.completed_lessons: Set[str] = set()
        self.lesson_scores: Dict[str, int] = {}
        self.xp: int = 0

        self._ensure_data_dir_exists()
        self.load_progress()

    def _ensure_data_dir_exists(self):
        if not os.path.exists(self.progress_data_dir):
            try:
                os.makedirs(self.progress_data_dir, exist_ok=True)
                logger.info(f"Created progress data directory: {self.progress_data_dir}")
            except OSError as e:
                logger.error(f"Could not create progress data directory {self.progress_data_dir}: {e}")
                exit()
                
    def load_progress(self):
        if not os.path.exists(self.progress_file):
            logger.info(f"No progress file found for {self.course_id} at {self.progress_file}. Starting fresh.")
            self.save_progress() # Create an empty progress file
            return

        try:
            with open(self.progress_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.completed_lessons = set(data.get('completed_lessons', []))
                self.lesson_scores = data.get('lesson_scores', {})
                self.xp = data.get('xp', 0)
                logger.info(f"Progress loaded for course {self.course_id}.")
        except FileNotFoundError:
             logger.info(f"Progress file {self.progress_file} not found. A new one will be created on save.")
        except json.JSONDecodeError:
            logger.error(f"Error decoding JSON from progress file {self.progress_file}. Progress may be lost.")
            # Optionally, back up the corrupted file and start fresh
        except Exception as e:
            logger.error(f"Failed to load progress from {self.progress_file}: {e}")

    def save_progress(self):
        self._ensure_data_dir_exists() # Make sure dir exists before saving
        data = {
            'completed_lessons': list(self.completed_lessons),
            'lesson_scores': self.lesson_scores,
            'xp': self.xp
        }
        try:
            with open(self.progress_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
            logger.info(f"Progress saved for course {self.course_id} to {self.progress_file}")
        except IOError:
            logger.error(f"Could not write progress to file {self.progress_file}.")
        except Exception as e:
            logger.error(f"An unexpected error occurred while saving progress: {e}")


    def is_lesson_completed(self, lesson_id: str) -> bool:
        return lesson_id in self.completed_lessons

    def mark_lesson_completed(self, lesson_id: str, score: int = 10):
        self.completed_lessons.add(lesson_id)
        self.lesson_scores[lesson_id] = self.lesson_scores.get(lesson_id, 0) + score
        self.xp += score
        self.save_progress()
        logger.info(f"Lesson {lesson_id} marked completed. Total XP: {self.xp}")

    def get_lesson_score(self, lesson_id: str) -> int:
        return self.lesson_scores.get(lesson_id, 0)

    def get_total_xp(self) -> int:
        return self.xp

    def is_lesson_unlocked(self, lesson_id: str, unit_lessons: list, all_units: list) -> bool:
        """
        Determines if a lesson is unlocked.
        - The first lesson of the first unit is always unlocked.
        - A lesson is unlocked if the previous lesson in the same unit is completed.
        - The first lesson of a unit (other than the first unit) is unlocked if all lessons
          in the preceding unit are completed.
        """
        if not unit_lessons or not all_units: # Should not happen with a valid course
            return False

        # Find the unit and lesson index
        current_unit_id = None
        lesson_idx_in_unit = -1
        
        for unit in all_units:
            for i, lesson in enumerate(unit.lessons):
                if lesson.lesson_id == lesson_id:
                    current_unit_id = unit.unit_id
                    lesson_idx_in_unit = i
                    # Find the unit_lessons list specific to the current unit
                    if unit_lessons[0].unit_id == current_unit_id: # Make sure we have the correct unit's lessons
                         pass # unit_lessons is already the correct one
                    else: # Search for the correct unit_lessons in all_units
                        found_unit_lessons = None
                        for u_search in all_units:
                            if u_search.unit_id == current_unit_id:
                                found_unit_lessons = u_search.lessons
                                break
                        if not found_unit_lessons: return False # Should not happen
                        unit_lessons = found_unit_lessons
                    break
            if current_unit_id:
                break
        
        if current_unit_id is None:
            logger.warning(f"Lesson {lesson_id} not found in course structure for unlocking check.")
            return False # Lesson not found in course structure

        # First lesson of the first unit is always unlocked
        if all_units[0].unit_id == current_unit_id and lesson_idx_in_unit == 0:
            return True

        # Check previous lesson in the same unit
        if lesson_idx_in_unit > 0:
            prev_lesson_id_in_unit = unit_lessons[lesson_idx_in_unit - 1].lesson_id
            return self.is_lesson_completed(prev_lesson_id_in_unit)
        
        # If it's the first lesson of a subsequent unit (lesson_idx_in_unit == 0 and unit is not the first)
        if lesson_idx_in_unit == 0:
            unit_idx_in_course = -1
            for i, u in enumerate(all_units):
                if u.unit_id == current_unit_id:
                    unit_idx_in_course = i
                    break
            
            if unit_idx_in_course > 0: # It's not the first unit
                prev_unit = all_units[unit_idx_in_course - 1]
                # Check if all lessons in the previous unit are completed
                for prev_unit_lesson in prev_unit.lessons:
                    if not self.is_lesson_completed(prev_unit_lesson.lesson_id):
                        return False # Previous unit not fully completed
                return True # All lessons in previous unit completed
            elif unit_idx_in_course == 0: # Should have been caught by "first lesson of first unit"
                 return True 

        return False # Default to locked