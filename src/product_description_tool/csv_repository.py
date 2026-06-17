from __future__ import annotations

import csv
import io
import re
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
        effective = self._dialect_from_config(config)

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

    @staticmethod
    def _normalize_export_order(
        configured: list[str], current_headers: list[str]
    ) -> list[str]:
        """Normalize export column order.

        - Keep first occurrence of each column name present in *current_headers*.
        - Ignore names not present in *current_headers* (stale).
        - Append any *current_headers* not yet listed, preserving document order.
        """
        ordered: list[str] = []
        for h in configured:
            if h in current_headers and h not in ordered:
                ordered.append(h)
        for h in current_headers:
            if h not in ordered:
                ordered.append(h)
        return ordered

    def save(self, path: str | Path, document: CsvDocument, config: CsvConfig) -> None:
        target_path = Path(path)
        all_headers = list(document.headers)

        # Determine export column order: configured export_order is
        # normalized (deduplicated, stale names removed, missing current
        # headers appended), then falls back to document header order.
        export_headers = self._normalize_export_order(config.export_order, all_headers)

        effective = self._dialect_from_config(config)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        with target_path.open(
            "w",
            encoding=config.encoding,
            newline=config.newline,
        ) as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=export_headers,
                delimiter=effective.delimiter,
                quotechar=effective.quotechar,
                lineterminator=effective.lineterminator,
            )
            if config.write_header:
                writer.writeheader()
            for row in document.rows:
                output = {}
                for header in export_headers:
                    value = row.get(header, "")
                    field_config = config.fields.get(header)
                    if field_config and field_config.strip_html_whitespace:
                        value = re.sub(r"\s+", " ", value).strip()
                    output[header] = value
                writer.writerow(output)

    def ensure_column(self, document: CsvDocument, column_name: str) -> None:
        if not column_name:
            return
        if column_name not in document.headers:
            document.headers.append(column_name)
        for row in document.rows:
            row.setdefault(column_name, "")

    def _dialect_from_config(self, config: CsvConfig) -> CsvDialectSettings:
        return CsvDialectSettings(
            delimiter=config.delimiter,
            quotechar=config.quotechar,
            lineterminator=config.newline or CsvDialectSettings().lineterminator,
        )
