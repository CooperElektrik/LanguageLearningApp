"""fill_in_the_blank was missing from the CSV importer; lock it in."""

from tools import csv_importer


def _write_csv(tmp_path, text):
    path = tmp_path / "fib.csv"
    path.write_text(text, encoding="utf-8")
    return str(path)


def test_fill_in_the_blank_import(tmp_path):
    csv_path = _write_csv(
        tmp_path,
        "sentence_template,correct_option,incorrect_1,incorrect_2,translation_hint\n"
        "Toi __BLANK__ vui,rat,khong,chua,I am happy\n",
    )
    course_data = {"units": []}

    success, messages = csv_importer.import_csv_data(
        csv_filepath=csv_path,
        existing_course_data=course_data,
        exercise_type="fill_in_the_blank",
        unit_id="u1",
        unit_title="Unit 1",
        lesson_id="u1l1",
        lesson_title="Lesson 1",
        incorrect_options_cols=["incorrect_1", "incorrect_2"],
    )

    assert success, messages
    exercises = course_data["units"][0]["lessons"][0]["exercises"]
    assert len(exercises) == 1
    ex = exercises[0]
    assert ex["type"] == "fill_in_the_blank"
    assert ex["sentence_template"] == "Toi __BLANK__ vui"
    assert ex["correct_option"] == "rat"
    assert ex["options"] == ["rat", "khong", "chua"]
    assert ex["translation_hint"] == "I am happy"


def test_fill_in_the_blank_requires_columns(tmp_path):
    csv_path = _write_csv(tmp_path, "prompt,answer\nhello,xin chao\n")
    course_data = {"units": []}

    success, messages = csv_importer.import_csv_data(
        csv_filepath=csv_path,
        existing_course_data=course_data,
        exercise_type="fill_in_the_blank",
        unit_id="u1",
        unit_title="Unit 1",
        lesson_id="u1l1",
        lesson_title="Lesson 1",
    )

    assert not success
    assert any("fill_in_the_blank" in m and "missing required columns" in m for m in messages)


def test_fill_in_the_blank_skips_incomplete_rows(tmp_path):
    csv_path = _write_csv(
        tmp_path,
        "sentence_template,correct_option\nToi __BLANK__ vui,rat\n,khong\n",
    )
    course_data = {"units": []}

    success, messages = csv_importer.import_csv_data(
        csv_filepath=csv_path,
        existing_course_data=course_data,
        exercise_type="fill_in_the_blank",
        unit_id="u1",
        unit_title="Unit 1",
        lesson_id="u1l1",
        lesson_title="Lesson 1",
    )

    assert success, messages
    exercises = course_data["units"][0]["lessons"][0]["exercises"]
    assert len(exercises) == 1
    assert exercises[0]["correct_option"] == "rat"
