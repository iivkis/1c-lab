"""Static regression tests for previously found defects.

These verify source invariants, NOT execution in 1C:Enterprise.
"""
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
INVOICE_FORMS = {
    "ПриходнаяНакладная": SRC / "Documents" / "ПриходнаяНакладная"
    / "Forms" / "ФормаДокумента" / "Ext" / "Form" / "Module.bsl",
    "РасходнаяНакладная": SRC / "Documents" / "РасходнаяНакладная"
    / "Forms" / "ФормаДокумента" / "Ext" / "Form" / "Module.bsl",
}


class RequirementsRegressionTests(unittest.TestCase):
    def test_export_uses_nonmodal_dialog_and_callback(self):
        config = (SRC / "Configuration.xml").read_text(encoding="utf-8")
        self.assertIn("<ModalityUseMode>DontUse</ModalityUseMode>", config)
        for name, path in INVOICE_FORMS.items():
            with self.subTest(name=name):
                code = path.read_text(encoding="utf-8")
                self.assertIn('Диалог.Показать(Новый ОписаниеОповещения(', code)
                self.assertRegex(
                    code, r"Процедура\s+ЭкспортВExcelЗавершение\s*\(",
                )
                self.assertNotIn("Если Диалог.Выбрать()", code)
                self.assertIn("ВыбранныеФайлы[0]", code)
                self.assertIn("ТипФайлаТабличногоДокумента.XLSX", code)

    def test_print_uses_bsl_document_properties(self):
        for name, path in INVOICE_FORMS.items():
            with self.subTest(name=name):
                code = path.read_text(encoding="utf-8")
                self.assertIn("Объект.Номер", code)
                self.assertIn("Объект.Дата", code)
                self.assertNotIn("Объект.Number", code)
                self.assertNotIn("Объект.Date", code)

    def test_expense_preview_aggregates_same_product_lines(self):
        form = INVOICE_FORMS["РасходнаяНакладная"].read_text(encoding="utf-8")
        self.assertIn("Для Каждого СтрокаТовара Из Объект.Товары Цикл", form)
        self.assertIn("Если СтрокаТовара.Товар = Товар Тогда", form)
        self.assertIn("РасходПоТовару = РасходПоТовару + СтрокаТовара.Количество;", form)
        self.assertIn("ОстатокПосле = ОстатокТовара - РасходПоТовару;", form)
        self.assertNotIn("ОстатокПосле = ОстатокТовара - Количество;", form)

    def test_preview_can_restore_posted_document_consumption(self):
        form = INVOICE_FORMS["РасходнаяНакладная"].read_text(encoding="utf-8")
        common = (
            SRC / "CommonModules" / "СкладскойУчетСервер" / "Ext" / "Module.bsl"
        ).read_text(encoding="utf-8")
        self.assertIn("ПолучитьОстатокДоРасхода(", form)
        self.assertRegex(
            common, r"Функция\s+ПолучитьОстатокДоРасхода\s*\("
        )
        self.assertIn("ДобавитьПрежнийРасход(Остатки, Склад, ПрежнийРегистратор)", common)

    def test_rejected_posting_does_not_count_persisted_draft_as_success(self):
        code = (
            SRC / "DataProcessors" / "ПроверкаЛабораторной"
            / "Ext" / "ObjectModule.bsl"
        ).read_text(encoding="utf-8")
        match = re.search(
            r"Процедура\s+ПроверитьОтказОтПроведения\s*\([^)]*\)"
            r"([\s\S]*?)КонецПроцедуры", code,
        )
        self.assertIsNotNone(match)
        body = match.group(1)
        self.assertIn("Накладная.ЭтоНовый()", body)
        self.assertNotIn("Или Не Накладная.Проведен", body)
        self.assertIn("ДопустимыйРасходСклад2", code)
        self.assertIn("СохранённаяНакладная", code)

    def test_real_platform_remains_separate_from_static_ci(self):
        script = (ROOT / "scripts" / "check-config-in-onec.sh").read_text(
            encoding="utf-8"
        )
        for command in ("/LoadConfigFromFiles", "/UpdateDBCfg", "/CheckConfig", "/DumpCfg", "/DumpResult"):
            self.assertIn(command, script)
        self.assertIn("1cv8t", script)


if __name__ == "__main__":
    unittest.main()
