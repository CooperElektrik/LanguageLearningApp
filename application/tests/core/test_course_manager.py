def test_course_manager_initialization(course_manager):
    """Tests that the CourseManager initializes correctly."""
    assert course_manager.course is not None
    assert course_manager.get_course_title() == "Test Course"
    assert course_manager.get_target_language() == "Vietnamese"
    assert len(course_manager.get_glossary_entries()) == 2

def test_check_answer_translation(course_manager):
    """Tests answer checking for translation exercises."""
    exercise = course_manager.get_lesson("u1l1").exercises[0]
    is_correct, feedback = course_manager.check_answer(exercise, "Xin chào")
    assert is_correct is True
    
    is_correct, feedback = course_manager.check_answer(exercise, "wrong answer")
    assert is_correct is False
    assert "Correct: Xin chào" in feedback

def test_check_answer_mcq(course_manager):
    """Tests answer checking for multiple choice exercises."""
    exercise = course_manager.get_lesson("u1l1").exercises[1]
    is_correct, feedback = course_manager.check_answer(exercise, "con mèo")
    assert is_correct is True
    
    is_correct, feedback = course_manager.check_answer(exercise, "con chó")
    assert is_correct is False
    assert "Correct: con mèo" in feedback

def test_check_answer_jumble(course_manager):
    """Tests answer checking for sentence jumble exercises."""
    exercise = course_manager.get_lesson("u1l2").exercises[0]
    is_correct, feedback = course_manager.check_answer(exercise, "Tôi ăn táo")
    assert is_correct is True
    
    is_correct, feedback = course_manager.check_answer(exercise, "táo ăn Tôi")
    assert is_correct is False