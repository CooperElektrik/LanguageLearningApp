"""Tests for CoursePackager asset collection and glossary bundling."""

import os
import zipfile
import pytest
from application.tools.course_packager import create_package_for_gui


def test_course_packager_bundles_glossary_and_options(tmp_path):
    course_dir = tmp_path / "course"
    course_dir.mkdir()

    manifest_path = course_dir / "manifest.yaml"
    manifest_path.write_text(
        "course_id: test_pkg\n"
        "course_title: Packager Test\n"
        "content_file: content.yaml\n"
        "glossary_file: glossary.yaml\n"
        "target_language: Spanish\n"
        "source_language: English\n",
        encoding="utf-8",
    )

    (course_dir / "glossary.yaml").write_text("entries: []\n", encoding="utf-8")
    (course_dir / "content.yaml").write_text(
        "units:\n"
        "  - unit_id: u1\n"
        "    title: Unit 1\n"
        "    lessons:\n"
        "      - lesson_id: l1\n"
        "        title: Lesson 1\n"
        "        exercises:\n"
        "          - exercise_id: ex1\n"
        "            type: multiple_choice_translation\n"
        "            options:\n"
        "              - text: Opt 1\n"
        "                image_file: opt1.png\n",
        encoding="utf-8",
    )
    # Create the option image file
    (course_dir / "opt1.png").write_text("fake image content", encoding="utf-8")

    output_dir = tmp_path / "output"
    output_dir.mkdir()

    success, pkg_path, messages = create_package_for_gui(
        str(manifest_path), output_dir_override=str(output_dir)
    )

    assert success is True
    assert os.path.exists(pkg_path)

    with zipfile.ZipFile(pkg_path, "r") as zf:
        namelist = zf.namelist()
        assert "manifest.yaml" in namelist
        assert "content.yaml" in namelist
        assert "glossary.yaml" in namelist
        assert "opt1.png" in namelist
