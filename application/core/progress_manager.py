import json
import os
import logging
from typing import Dict, Set, Optional, Any, List
from PySide6.QtCore import QStandardPaths
from collections import defaultdict
from datetime import datetime, timedelta

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

        self.exercise_srs_data: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            'last_reviewed': None, 
            'next_review_due': None, 
            'interval_days': 0, 
            'ease_factor': 2.5, 
            'repetitions': 0, 
            'correct_in_a_row': 0
        })
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
                raw_srs_data = data.get('exercise_srs_data', {})
                for ex_id, srs_attrs in raw_srs_data.items():
                    if srs_attrs.get('last_reviewed'):
                        srs_attrs['last_reviewed'] = datetime.fromisoformat(srs_attrs['last_reviewed'])
                    if srs_attrs.get('next_review_due'):
                        srs_attrs['next_review_due'] = datetime.fromisoformat(srs_attrs['next_review_due'])
                    self.exercise_srs_data[ex_id] = srs_attrs
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
        srs_data_for_save = {}
        for ex_id, srs_attrs in self.exercise_srs_data.items():
            srs_copy = srs_attrs.copy() # Make a copy to modify
            if srs_copy.get('last_reviewed'):
                srs_copy['last_reviewed'] = srs_copy['last_reviewed'].isoformat()
            if srs_copy.get('next_review_due'):
                srs_copy['next_review_due'] = srs_copy['next_review_due'].isoformat()
            srs_data_for_save[ex_id] = srs_copy

        data = {
            'exercise_srs_data': srs_data_for_save,
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

    def _calculate_srs_parameters(self, srs_attrs: Dict[str, Any], quality_score_sm2: int):
        """
        Implements the SM-2 algorithm.
        quality_score_sm2: 0-5 (0: complete blackout, 1: incorrect but recognized, 2: incorrect, easy to remember
                                3: correct, but hesitated, 4: correct, easy, 5: correct, perfect recall)
        """
        q = quality_score_sm2

        if q < 3: # Incorrect answer (quality 0, 1, 2)
            srs_attrs['repetitions'] = 0 
            srs_attrs['interval_days'] = 0 # Immediately due again
            srs_attrs['correct_in_a_row'] = 0 
            srs_attrs['ease_factor'] = max(1.3, srs_attrs['ease_factor'] - 0.20) 
        else: # Correct answer (quality 3, 4, 5)
            srs_attrs['correct_in_a_row'] += 1 
            srs_attrs['repetitions'] += 1 

            if srs_attrs['repetitions'] == 1:
                srs_attrs['interval_days'] = 1
            elif srs_attrs['repetitions'] == 2:
                srs_attrs['interval_days'] = 6
            else:
                srs_attrs['interval_days'] = round(srs_attrs['interval_days'] * srs_attrs['ease_factor'])
            
            srs_attrs['ease_factor'] += (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))
            srs_attrs['ease_factor'] = max(1.3, srs_attrs['ease_factor']) # Ensure ease factor doesn't drop below 1.3
        
        srs_attrs['last_reviewed'] = datetime.now()
        srs_attrs['next_review_due'] = srs_attrs['last_reviewed'] + timedelta(days=srs_attrs['interval_days'])

    def update_exercise_srs_data(self, exercise_id: str, is_correct: bool, xp_awarded: int = 10, quality_score_sm2: int = 4):
        """
        Updates SRS parameters for an exercise and adds XP.
        is_correct: True if user answered correctly, False otherwise.
        quality_score_sm2: Quality rating from 0-5 for SM-2 algorithm.
        """
        srs_attrs = self.exercise_srs_data[exercise_id] 
        # If is_correct is False, force quality_score_sm2 to 0 for SM-2
        if not is_correct and quality_score_sm2 >= 3: # Ensure incorrect answers don't get high quality
            logger.warning(f"Forcing SM2 quality to 0 for incorrect answer on {exercise_id}")
            quality_score_sm2 = 0 

        self._calculate_srs_parameters(srs_attrs, quality_score_sm2) # Pass granular quality
        
        if is_correct: # XP awarded only for correct answers
            self.xp += xp_awarded 
        
        self.save_progress()
        logger.debug(f"SRS updated for {exercise_id}: next_review_due={srs_attrs['next_review_due']}, interval={srs_attrs['interval_days']}, XP={self.xp}")

    def get_exercise_srs_data(self, exercise_id: str) -> Dict[str, Any]:
        """Returns the current SRS attributes for a specific exercise."""
        return self.exercise_srs_data[exercise_id] # Will create default entry if not exists

    def get_due_exercises(self, all_course_exercises: List[Any], limit: int = 20) -> List[Any]:
        """
        Returns a list of exercise objects that are due for review, sorted by due date.
        all_course_exercises: A flat list of all Exercise objects in the course.
        """
        due_exercises = []
        now = datetime.now()

        # Iterate through all exercises in the course to find their SRS data
        for exercise in all_course_exercises:
            srs_attrs = self.exercise_srs_data[exercise.exercise_id] # Get/create SRS data

            # An exercise is due if:
            # 1. It has never been reviewed (repetitions == 0)
            # 2. Its next_review_due date is past or today.
            if srs_attrs['repetitions'] == 0 or (srs_attrs['next_review_due'] and srs_attrs['next_review_due'] <= now):
                due_exercises.append(exercise)
        
        # Sort due exercises: prioritize those due earlier, then those with lower repetitions
        due_exercises.sort(key=lambda ex: (self.exercise_srs_data[ex.exercise_id]['next_review_due'] or datetime.min, 
                                            self.exercise_srs_data[ex.exercise_id]['repetitions']))
        
        return due_exercises[:limit] # Return up to the limit

    def get_lesson_completion_status(self, lesson_id: str, all_exercises_in_lesson: List[Any]) -> bool:
        """Determines if a lesson is considered 'completed' for display purposes."""
        # A lesson is completed if all its exercises have been reviewed at least once.
        # This is a simplified definition of completion.
        if not all_exercises_in_lesson: # An empty lesson is technically completed
            return True
        
        for exercise in all_exercises_in_lesson:
            srs_attrs = self.exercise_srs_data[exercise.exercise_id]
            if srs_attrs['repetitions'] == 0: # If any exercise hasn't been done
                return False
        return True

    def get_total_xp(self) -> int:
        return self.xp

    def is_lesson_completed(self, lesson_id: str, course_manager_ref: Any) -> bool:
        """
        Checks if a lesson is completed based on all its exercises being reviewed at least once.
        Requires a reference to CourseManager to get lesson exercises.
        """
        lesson_exercises = course_manager_ref.get_exercises(lesson_id)
        return self.get_lesson_completion_status(lesson_id, lesson_exercises)

    def mark_lesson_completed(self, lesson_id: str, score: int = 0):
        """
        This method is now less relevant. XP is awarded per exercise.
        Lesson completion is now derived from SRS status of its exercises.
        This function might just be a placeholder or removed.
        """
        logger.warning(f"mark_lesson_completed({lesson_id}) called. XP is now managed per exercise.")
        # If still needed for some other purpose, keep. Otherwise remove.
        # For now, it will simply do nothing more than log a warning.

    def is_lesson_unlocked(self, lesson_id: str, unit_lessons: list, all_units: list, course_manager_ref: Any) -> bool:
        """
        Determines if a lesson is unlocked, using SRS completion status.
        Requires a reference to CourseManager to check completion status of exercises in lessons.
        """
        # Find the unit and lesson index - (unchanged logic)
        current_unit_id = None
        lesson_idx_in_unit = -1
        
        for unit in all_units:
            for i, lesson in enumerate(unit.lessons):
                if lesson.lesson_id == lesson_id:
                    current_unit_id = unit.unit_id
                    lesson_idx_in_unit = i
                    if unit_lessons[0].unit_id == current_unit_id:
                         pass 
                    else: 
                        found_unit_lessons = None
                        for u_search in all_units:
                            if u_search.unit_id == current_unit_id:
                                found_unit_lessons = u_search.lessons
                                break
                        if not found_unit_lessons: return False
                        unit_lessons = found_unit_lessons
                    break
            if current_unit_id: break
        
        if current_unit_id is None:
            logger.warning(f"Lesson {lesson_id} not found in course structure for unlocking check.")
            return False 

        # First lesson of the first unit is always unlocked
        if all_units[0].unit_id == current_unit_id and lesson_idx_in_unit == 0:
            return True

        # Check previous lesson in the same unit
        if lesson_idx_in_unit > 0:
            prev_lesson = unit_lessons[lesson_idx_in_unit - 1]
            return self.is_lesson_completed(prev_lesson.lesson_id, course_manager_ref)
        
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
                    if not self.is_lesson_completed(prev_unit_lesson.lesson_id, course_manager_ref):
                        return False 
                return True 
            elif unit_idx_in_course == 0:
                 return True 

        return False