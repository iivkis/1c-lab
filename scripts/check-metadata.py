#!/usr/bin/env python3
"""Structural checks of a hierarchical 1C XML export (NOT a platform load test)."""
from __future__ import annotations

import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

MD = "{http://v8.1c.ru/8.3/MDClasses}"
XR = "{http://v8.1c.ru/8.3/xcf/readable}"
CFG_TYPE = "http://v8.1c.ru/8.1/data/enterprise/current-config"
FOLDERS = {
    "Catalog": "Catalogs",
    "Document": "Documents",
    "Report": "Reports",
    "AccumulationRegister": "AccumulationRegisters",
    "CommonModule": "CommonModules",
    "DataProcessor": "DataProcessors",
    "Subsystem": "Subsystems",
    "Language": "Languages",
}
REQUIRED = {
    "Catalog": {"Товары", "Склады", "Поставщики", "Получатели"},
    "Document": {"ПриходнаяНакладная", "РасходнаяНакладная"},
    "Report": {"КонтрольНеснижаемогоОстатка", "ПоступленияОтПоставщиков", "ВыдачаПолучателям", "ДиаграммаДвиженияТоваров"},
    "AccumulationRegister": {
        "ОстаткиТоваров", "ПоступленияПоПоставщикам", "ВыдачиПоПолучателям"
    },
    "CommonModule": {"СкладскойУчетСервер", "СкладскиеОтчетыСервер"},
    "DataProcessor": {
        "Задача04Гипотенуза", "Задача12СуммаКвадратов",
        "Задача22Водоснабжение", "Задача26ОплатаТруда", "АнализСкладскихДанных", "ПроверкаЛабораторной"
    },
    "Subsystem": {"Склад", "СкладскиеОтчеты", "ДополнительныеЗадачи", "Сервис"},
    "Language": {"Русский"},
}
DOC_REGISTERS = {
    "ПриходнаяНакладная": {"ОстаткиТоваров", "ПоступленияПоПоставщикам"},
    "РасходнаяНакладная": {"ОстаткиТоваров", "ВыдачиПоПолучателям"},
}


def lname(element: ET.Element) -> str:
    return element.tag.rpartition("}")[2]


def fail(message: str) -> None:
    raise ValueError(message)


def verify_document_form_paths(src: Path, form_path: Path, form: ET.Element) -> None:
    """Resolve DataPath fields against the document XML and form attributes."""
    doc_name = form_path.relative_to(src).parts[1]
    document_xml = src / "Documents" / (doc_name + ".xml")
    metadata_root = ET.parse(document_xml).getroot()
    doc = metadata_root.find(f"{MD}Document")
    if doc is None:
        fail(f"Document form has no parent document metadata: {form_path}")

    children = doc.find(f"{MD}ChildObjects")
    if children is None:
        fail(f"Document has no attributes/table sections: {document_xml}")

    doc_fields = {"Номер", "Дата", "Ссылка", "Проведен", "ПометкаУдаления"}
    section_fields: dict[str, set[str]] = {}
    for child in children:
        kind = lname(child)
        name = child.findtext(f"{MD}Properties/{MD}Name")
        if not name:
            continue
        if kind == "Attribute":
            doc_fields.add(name)
        elif kind == "TabularSection":
            doc_fields.add(name)
            fields = {"НомерСтроки"}
            for attribute in child.findall(f"{MD}ChildObjects/{MD}Attribute"):
                field = attribute.findtext(f"{MD}Properties/{MD}Name")
                if field:
                    fields.add(field)
            section_fields[name] = fields

    form_attrs = set()
    for element in form.iter():
        if lname(element) == "Attributes":
            form_attrs.update(
                child.get("name") for child in element
                if lname(child) == "Attribute" and child.get("name")
            )

    for element in form.iter():
        if lname(element) != "DataPath" or not element.text:
            continue
        data_path = element.text.strip()
        components = data_path.split(".")
        if components[0] == "Объект":
            if len(components) < 2 or components[1] not in doc_fields:
                fail(f"Unrecognized document DataPath {data_path}: {form_path}")
            if len(components) == 3 and components[2] not in section_fields.get(components[1], set()):
                fail(f"Unrecognized tabular DataPath {data_path}: {form_path}")
            if len(components) > 3 or (len(components) == 3 and components[1] not in section_fields):
                fail(f"Unsupported document DataPath {data_path}: {form_path}")
        elif components[0] not in form_attrs:
            fail(f"Unknown form attribute in DataPath {data_path}: {form_path}")


def check(src: Path) -> int:
    source = (src / "Configuration.xml")
    if not source.is_file():
        fail("Missing src/Configuration.xml")
    manifest = ET.parse(source).getroot()
    if lname(manifest) != "MetaDataObject":
        fail("Configuration.xml has no MetaDataObject root")
    config = manifest.find(f"{MD}Configuration")
    if config is None:
        fail("Configuration.xml has no Configuration")
    child_objects = config.find(f"{MD}ChildObjects")
    if child_objects is None:
        fail("Configuration.xml has no ChildObjects")

    listed: dict[str, set[str]] = {kind: set() for kind in FOLDERS}
    for element in child_objects:
        kind = lname(element)
        if kind in listed:
            listed[kind].add(element.text or "")
    for kind, expected in REQUIRED.items():
        missing = expected - listed[kind]
        if missing:
            fail(f"Missing objects in Configuration.xml: {kind}: {sorted(missing)}")

    paths = list(src.rglob("*.xml"))
    unique_ids: set[str] = set()
    for path in paths:
        root = ET.parse(path).getroot()
        rel = path.relative_to(src)
        is_form_layout = (
            len(rel.parts) == 6
            and rel.parts[0] in {"DataProcessors", "Documents", "Reports"}
            and rel.parts[2] == "Forms"
            and rel.parts[4:] == ("Ext", "Form.xml")
        )
        is_dcs = (
            len(rel.parts) == 6
            and rel.parts[0] == "Reports"
            and rel.parts[2] == "Templates"
            and rel.parts[4:] == ("Ext", "Template.xml")
        )
        expected_root = "Form" if is_form_layout else "DataCompositionSchema" if is_dcs else "MetaDataObject"
        if lname(root) != expected_root:
            fail(f"{path} has an unexpected XML root")
        for obj in root.iter():
            value = obj.attrib.get("uuid")
            if value:
                if value in unique_ids:
                    fail(f"Duplicate metadata UUID {value} ({path})")
                unique_ids.add(value)

        if path == source:
            continue
        if is_form_layout and rel.parts[0] == "Documents":
            verify_document_form_paths(src, path, root)
        if is_form_layout:
            source_module = path.parent / "Form" / "Module.bsl"
            if not source_module.is_file():
                fail(f"Form has no BSL module: {source_module}")
            module = source_module.read_text(encoding="utf-8-sig")
            handlers = {
                (element.text or "").strip()
                for element in root.iter()
                if lname(element) in {"Action", "Event"}
                and (element.text or "").strip()
            }
            for handler in sorted(handlers):
                pattern = r"\b(?:Процедура|Функция)\s+" + re.escape(handler) + r"\s*\("
                if re.search(pattern, module, re.IGNORECASE) is None:
                    fail(f"Form {path} refers to missing BSL handler {handler}")
        if is_dcs:
            # Every report requires interactive warehouse and date parameters.
            variants = [
                e for e in root.iter() if lname(e) == "settingsVariant"
            ]
            if not variants:
                fail(f"Report DCS has no settings variant: {path}")
            for variant in variants:
                data_parameters = [
                    e for e in variant.iter() if lname(e) == "dataParameters"
                ]
                if len(data_parameters) != 1:
                    fail(f"Report DCS is missing user data parameters: {path}")
                actual = {}
                for item in data_parameters[0]:
                    name_el = next(
                        (e for e in item if lname(e) == "parameter"), None
                    )
                    setting_id = next(
                        (e for e in item if lname(e) == "userSettingID"), None
                    )
                    view = next(
                        (e for e in item if lname(e) == "viewMode"), None
                    )
                    if name_el is not None:
                        actual[name_el.text] = (
                            setting_id.text if setting_id is not None else "",
                            view.text if view is not None else "",
                        )
                needed = {"НачалоПериода", "КонецПериода", "Склад"}
                if needed - set(actual):
                    fail(f"Report DCS lacks parameters {sorted(needed - set(actual))}: {path}")
                if any(not actual[name][0] or actual[name][1] != "QuickAccess"
                       for name in needed):
                    fail(f"Report DCS parameters are not available in quick settings: {path}")
        if is_dcs:
            queries = [
                (element.text or "").strip()
                for element in root.iter()
                if lname(element) == "query"
            ]
            if not queries or not all("РегистрНакопления." in q for q in queries):
                fail(f"Report schema has no register-based query: {path}")
            if rel.parts[1] == "ДиаграммаДвиженияТоваров":
                if not any("StructureItemChart" in str(value)
                           for element in root.iter()
                           for value in element.attrib.values()):
                    fail(f"Report has no chart structure: {path}")
        if len(rel.parts) > 2:
            folder = rel.parts[0]
            kinds = [kind for kind, parent in FOLDERS.items() if parent == folder]
            if len(kinds) != 1 or rel.parts[1] not in listed[kinds[0]]:
                fail(f"Unregistered nested metadata file: {rel}")
            if len(rel.parts) == 4 and rel.parts[2] == "Forms" and path.suffix == ".xml":
                if root.find(f"{MD}Form") is None:
                    fail(f"Missing form object in {rel}")
            elif len(rel.parts) == 4 and rel.parts[2] == "Templates" and path.suffix == ".xml":
                if root.find(f"{MD}Template") is None:
                    fail(f"Missing template object in {rel}")
            elif not (is_form_layout or is_dcs):
                fail(f"Unexpected nested XML file: {rel}")
            continue
        if len(rel.parts) != 2 or rel.parts[0] not in FOLDERS.values():
            fail(f"Unexpected metadata XML path: {rel}")
        kind = next(k for k, folder in FOLDERS.items() if folder == rel.parts[0])
        metadata = root.find(f"{MD}{kind}")
        if metadata is None:
            fail(f"Wrong metadata kind for {path}; expected {kind}")
        name = metadata.findtext(f"{MD}Properties/{MD}Name")
        if name != path.stem or name not in listed[kind]:
            fail(f"Unregistered or mismatched metadata object {path}: {name}")

        for field in metadata.iter():
            if field.tag.endswith("}Type"):
                if (field.text or "").startswith("cfg:CatalogRef."):
                    ref = field.text.split(".", 1)[1]
                    if ref not in listed["Catalog"]:
                        fail(f"Unknown catalog reference {ref} in {path}")

        if kind == "DataProcessor":
            forms = metadata.find(f"{MD}ChildObjects")
            if forms is None or not any(e.text == "Форма" for e in forms):
                fail(f"DataProcessor has no UI form: {path}")

        if kind == "Report":
            forms = metadata.find(f"{MD}ChildObjects")
            if forms is None or not any(
                lname(e) == "Template" and e.text == "ОсновнаяСхемаКомпоновкиДанных"
                for e in forms
            ):
                fail(f"Report is missing the DCS template: {path}")
            dcs = src / "Reports" / name / "Templates" / "ОсновнаяСхемаКомпоновкиДанных" / "Ext" / "Template.xml"
            if not dcs.is_file():
                fail(f"Report DCS schema missing: {dcs}")
        if kind == "Document":
            record_nodes = metadata.find(f"{MD}Properties/{MD}RegisterRecords")
            refs = set()
            if record_nodes is not None:
                for child in record_nodes:
                    value = child.text or ""
                    if value.startswith("AccumulationRegister."):
                        refs.add(value.split(".", 1)[1])
            if refs != DOC_REGISTERS[name]:
                fail(f"Wrong registrar references in {path}: {sorted(refs)}")

    for kind, expected in REQUIRED.items():
        for name in expected:
            file = src / FOLDERS[kind] / f"{name}.xml"
            if not file.is_file():
                fail(f"Metadata file not found: {file}")

    bsl_files = list(src.rglob("*.bsl"))
    if not bsl_files:
        fail("No BSL files")
    for path in bsl_files:
        rel = path.relative_to(src)
        if len(rel.parts) < 4:
            fail(f"Unexpected BSL path: {path}")
        kind_folder, obj = rel.parts[:2]
        if not (src / kind_folder / f"{obj}.xml").is_file():
            fail(f"BSL module has no parent object XML: {path}")

    print(f"PASS: {len(paths)} XML metadata files parsed; {len(bsl_files)} BSL modules linked.")
    print("NOTE: XML structure checked, NOT imported into 1C:Enterprise.")
    return 0


if __name__ == "__main__":
    try:
        raise_code = check(Path(sys.argv[1] if len(sys.argv) > 1 else "src"))
    except (ET.ParseError, ValueError, OSError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise_code = 1
    sys.exit(raise_code)
