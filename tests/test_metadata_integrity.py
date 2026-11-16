"""Regression tests for completeness of declared 1C form metadata.

These are static source checks, not a platform import test.
"""
from pathlib import Path
import runpy
import shutil
import tempfile
import unittest
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src"
CHECK = runpy.run_path(str(ROOT / "scripts" / "check-metadata.py"))["check"]
MD = "{http://v8.1c.ru/8.3/MDClasses}"


class FormMetadataIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.src = Path(self.tempdir.name) / "src"
        shutil.copytree(SOURCE, self.src)

    def test_unmodified_tree_is_valid(self):
        self.assertEqual(CHECK(self.src), 0)

    def test_missing_form_declaration_file_is_rejected(self):
        path = self.src / "Documents/РасходнаяНакладная/Forms/ФормаДокумента.xml"
        path.unlink()
        with self.assertRaisesRegex(ValueError, "Declared form file is missing"):
            CHECK(self.src)

    def test_missing_form_layout_is_rejected(self):
        path = self.src / "DataProcessors/Задача04Гипотенуза/Forms/Форма/Ext/Form.xml"
        path.unlink()
        with self.assertRaisesRegex(ValueError, "Declared form file is missing"):
            CHECK(self.src)

    def test_default_form_must_refer_to_declared_form(self):
        path = self.src / "Documents/РасходнаяНакладная.xml"
        tree = ET.parse(path)
        document = tree.getroot().find(f"{MD}Document")
        default = document.find(f"{MD}Properties/{MD}DefaultObjectForm")
        self.assertIsNotNone(default)
        default.text = "Document.РасходнаяНакладная.Form.Несуществующая"
        tree.write(path, encoding="utf-8", xml_declaration=True)
        with self.assertRaisesRegex(ValueError, "Default form is not declared"):
            CHECK(self.src)


if __name__ == "__main__":
    unittest.main()
