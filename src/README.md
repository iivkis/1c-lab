# Исходники 1С:Предприятие

Здесь хранятся BSL-модули будущей конфигурации и (на следующих этапах) ее XML-метаданные.

**ВНИМАНИЕ:** текущий набор BSL-файлов — ещё не полная выгрузка «Конфигурация → Выгрузить конфигурацию в файлы». На данном этапе отсутствуют `Configuration.xml`, определения объектов и формы, поэтому загрузить всю конфигурацию из `src/` пока нельзя. BSL Language Server проверяет только синтаксис модулей.

Директории отражают будущую иерархическую выгрузку 1С:

- `Catalogs/Товары/Ext/ObjectModule.bsl`
- `Documents/ПриходнаяНакладная/Ext/ObjectModule.bsl`
- `Documents/РасходнаяНакладная/Ext/ObjectModule.bsl`
- `CommonModules/СкладскойУчетСервер/Ext/Module.bsl`
- `CommonModules/СкладскиеОтчетыСервер/Ext/Module.bsl`
- `DataProcessors/Задача.../Ext/ObjectModule.bsl`

Описание метаданных и процесса интеграции: [docs/IMPLEMENTATION.md](../docs/IMPLEMENTATION.md).
