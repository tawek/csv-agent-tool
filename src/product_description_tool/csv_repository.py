from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from pathlib import Path

from product_description_tool.config import CsvConfig


@dataclass(slots=True)
class CsvDialectSettings:
    delimiter: str = ","
    quotechar: str = '"'
    lineterminator: str = "\r\n"


@dataclass(slots=True)
class CsvDocument:
    headers: list[str]
    rows: list[dict[str, str]]
    source_path: Path | None = None
    dialect: CsvDialectSettings = field(default_factory=CsvDialectSettings)


class CsvRepository:
    def load(self, path: str | Path, config: CsvConfig) -> CsvDocument:
        source_path = Path(path)
        with source_path.open("r", encoding=config.encoding, newline=config.newline) as handle:
            text = handle.read()
        dialect = self._detect_dialect(text)
        effective = self._apply_overrides(dialect, config)

        reader = csv.DictReader(
            io.StringIO(text),
            delimiter=effective.delimiter,
            quotechar=effective.quotechar,
        )
        rows = [
            {header: (row.get(header) or "") for header in (reader.fieldnames or [])}
            for row in reader
        ]
        headers = list(reader.fieldnames or [])
        return CsvDocument(headers=headers, rows=rows, source_path=source_path, dialect=effective)

    def save(self, path: str | Path, document: CsvDocument, config: CsvConfig) -> None:
        target_path = Path(path)
        headers = list(document.headers)
        if config.result_description and config.result_description not in headers:
            headers.append(config.result_description)

        effective = self._apply_overrides(document.dialect, config)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        with target_path.open(
            "w",
            encoding=config.encoding,
            newline=config.newline,
        ) as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=headers,
                delimiter=effective.delimiter,
                quotechar=effective.quotechar,
                lineterminator=effective.lineterminator,
            )
            if config.write_header:
                writer.writeheader()
            for row in document.rows:
                output = {header: row.get(header, "") for header in headers}
                writer.writerow(output)

    def ensure_column(self, document: CsvDocument, column_name: str) -> None:
        if not column_name:
            return
        if column_name not in document.headers:
            document.headers.append(column_name)
        for row in document.rows:
            row.setdefault(column_name, "")

    def _detect_dialect(self, text: str) -> CsvDialectSettings:
        sample = text[:4096]
        try:
            sniffed = csv.Sniffer().sniff(sample)
            return CsvDialectSettings(
                delimiter=sniffed.delimiter,
                quotechar=sniffed.quotechar,
            )
        except csv.Error:
            return CsvDialectSettings()

    def _apply_overrides(
        self,
        dialect: CsvDialectSettings,
        config: CsvConfig,
    ) -> CsvDialectSettings:
        return CsvDialectSettings(
            delimiter=config.delimiter or dialect.delimiter,
            quotechar=config.quotechar or dialect.quotechar,
            lineterminator=config.newline or dialect.lineterminator,
        )
