"""Tests for CoursePackager asset collection and glossary bundling."""

import os
import zipfile

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


def test_import_course_package_success(tmp_path):
    from application.core.course_loader import import_course_package

    # Package a real course
    course_dir = tmp_path / "course"
    course_dir.mkdir()
    manifest_path = course_dir / "manifest.yaml"
    manifest_path.write_text(
        "course_id: import_test\n"
        "course_title: Import Test Course\n"
        "content_file: content.yaml\n"
        "version: 1.0.0\n"
        "target_language: Spanish\n"
        "source_language: English\n",
        encoding="utf-8",
    )
    (course_dir / "content.yaml").write_text("units: []\n", encoding="utf-8")

    pkg_dir = tmp_path / "pkg"
    pkg_dir.mkdir()
    success, pkg_path, _ = create_package_for_gui(
        str(manifest_path), output_dir_override=str(pkg_dir)
    )
    assert success is True

    # Now import into a destination directory
    dest_dir = tmp_path / "imported_courses"
    dest_dir.mkdir()
    ok, msg, imported_manifest = import_course_package(pkg_path, str(dest_dir))
    assert ok is True
    assert imported_manifest is not None
    assert os.path.exists(imported_manifest)
    assert "Import Test Course" in msg


def test_import_course_package_invalid_zip(tmp_path):
    from application.core.course_loader import import_course_package

    fake_file = tmp_path / "bad.lcpkg"
    fake_file.write_text("not a zip", encoding="utf-8")

    ok, msg, manifest = import_course_package(str(fake_file), str(tmp_path))
    assert ok is False
    assert manifest is None


def test_course_packager_bundles_glossary_audio(tmp_path):
    course_dir = tmp_path / "course"
    course_dir.mkdir()

    manifest_path = course_dir / "manifest.yaml"
    manifest_path.write_text(
        "course_id: glossary_audio_test\n"
        "course_title: Glossary Audio Test\n"
        "content_file: content.yaml\n"
        "glossary_file: glossary.yaml\n"
        "target_language: Spanish\n"
        "source_language: English\n",
        encoding="utf-8",
    )

    (course_dir / "content.yaml").write_text("units: []\n", encoding="utf-8")

    # Glossary referencing audio files
    (course_dir / "glossary.yaml").write_text(
        "- word: hola\n"
        "  translation: hello\n"
        "  audio_file: audio/hola.mp3\n"
        "- word: adios\n"
        "  translation: goodbye\n"
        "  audio_file: adios.mp3\n",
        encoding="utf-8",
    )

    audio_dir = course_dir / "audio"
    audio_dir.mkdir()
    (audio_dir / "hola.mp3").write_text("fake audio 1", encoding="utf-8")
    (course_dir / "adios.mp3").write_text("fake audio 2", encoding="utf-8")

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
        assert "audio/hola.mp3" in namelist
        assert "adios.mp3" in namelist
