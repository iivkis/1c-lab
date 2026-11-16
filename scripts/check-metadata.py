#!/usr/bin/env python3
"""Structural checks of a hierarchical 1C XML export (NOT a platform load test)."""
from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

MD = "{http://v8.1c.ru/8.3/MDClasses}"
XR = "{http://v8.1c.ru/8.3/xcf/readable}"
CFG_TYPE = "http://v8.1c.ru/8.1/data/enterprise/current-config"
FOLDERS = {
    "Catalog": "Catalogs",
    "Document": "Documents",
    "AccumulationRegister": "AccumulationRegisters",
    "CommonModule": "CommonModules",
    "DataProcessor": "DataProcessors",
    "Subsystem": "Subsystems",
    "Language": "Languages",
}
REQUIRED = {
    "Catalog": {"Товары", "Склады", "Поставщики", "Получатели"},
    "Document": {"ПриходнаяНакладная", "РасходнаяНакладная"},
    "AccumulationRegister": {
        "ОстаткиТоваров", "ПоступленияПоПоставщикам", "ВыдачиПоПолучателям"
    },
    "CommonModule": {"СкладскойУчетСервер", "СкладскиеОтчетыСервер"},
    "DataProcessor": {
        "Задача04Гипотенуза", "Задача12СуммаКвадратов",
        "Задача22Водоснабжение", "Задача26ОплатаТруда"
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
        is_form_layout = len(rel.parts) == 6 and rel.parts[0] == "DataProcessors" and rel.parts[2:] == ("Forms", "Форма", "Ext", "Form.xml")
        if lname(root) != ("Form" if is_form_layout else "MetaDataObject"):
            fail(f"{path} has an unexpected XML root")
        for obj in root.iter():
            value = obj.attrib.get("uuid")
            if value:
                if value in unique_ids:
                    fail(f"Duplicate metadata UUID {value} ({path})")
                unique_ids.add(value)

        if path == source:
            continue
        if len(rel.parts) > 2:
            if rel.parts[0] != "DataProcessors" or rel.parts[1] not in listed["DataProcessor"]:
                fail(f"Unregistered nested metadata file: {rel}")
            if len(rel.parts) == 4 and rel.parts[2:] == ("Forms", "Форма.xml"):
                if root.find(f"{MD}Form") is None:
                    fail(f"Missing form object in {rel}")
            elif not is_form_layout:
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
