from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from pathlib import Path

from product_description_tool.config import CsvReadSettings, CsvWriteSettings


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


# -- Delimiter candidates (most likely first) --
_DELIMITER_CANDIDATES = [",", ";", "\t", "|", "^", "~", ":"]


class CsvRepository:
    @staticmethod
    def detect_settings(path: str | Path) -> CsvReadSettings:
        """Inspect a CSV file and return detected import parsing settings.

        Heuristics cover encoding, delimiter, quotechar, and newline.
        If a heuristic cannot determine a usable value, the corresponding
        ``CsvReadSettings`` default is used.
        """
        source_path = Path(path)
        try:
            raw = source_path.read_bytes()
        except OSError:
            return CsvReadSettings()

        # 1. Detect encoding --------------------------------------------------
        encoding = CsvRepository._detect_encoding(raw)

        # 2. Decode text for further checks -----------------------------------
        try:
            text = raw.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            text = raw.decode("utf-8", errors="replace")

        # 3. Detect newline ---------------------------------------------------
        newline = CsvRepository._detect_newline(raw)

        # 4. Detect delimiter and quotechar ----------------------------------
        delimiter, quotechar = CsvRepository._detect_dialect(text, newline)

        return CsvReadSettings(
            encoding=encoding,
            delimiter=delimiter,
            quotechar=quotechar,
            newline=newline,
        )

    @staticmethod
    def _detect_encoding(raw: bytes) -> str:
        """Detect file encoding from raw bytes.

        Recognises BOM signatures, then tries strict UTF-8, and finally
        falls back to latin-1 (which never fails).
        """
        if raw.startswith(b"\xef\xbb\xbf"):
            return "utf-8-sig"
        if raw.startswith(b"\xff\xfe"):
            return "utf-16-le"
        if raw.startswith(b"\xfe\xff"):
            return "utf-16-be"
        try:
            raw.decode("utf-8")
            return "utf-8"
        except UnicodeDecodeError:
            return "latin-1"

    @staticmethod
    def _detect_newline(raw: bytes) -> str:
        """Detect the dominant line-ending style in a byte buffer.

        Returns ``''`` (universal — safe for CSV reading/writing) for files
        dominated by ``\\r\\n`` or ``\\r``, or ``'\\n'`` for LF-only files.
        """
        crlf = raw.count(b"\r\n")
        lf = raw.count(b"\n") - crlf
        cr = raw.count(b"\r") - crlf

        if crlf > lf and crlf > cr:
            return ""  # CRLF dominant → universal mode
        if lf >= cr:
            return "\n"  # LF dominant
        return ""  # \r only → universal

    @staticmethod
    def _detect_dialect(text: str, newline: str) -> tuple[str, str]:
        """Detect delimiter and quotechar from decoded CSV text.

        Tries common delimiter/quotechar combinations against the first
        data lines and scores them for consistency and field count.
        Returns ``(';', '\"')`` when no reliable candidate is found.
        """
        lines = text.split(newline) if newline else text.splitlines()
        data_lines = [ln.strip() for ln in lines if ln.strip()][:20]
        if len(data_lines) < 2:
            return (";", '"')

        best_delim = ";"
        best_quote = '"'
        best_score = 0.0
        best_other_quote_count = 0

        other_q = {'"': "'", "'": '"'}

        for delim in _DELIMITER_CANDIDATES:
            for qchar in ('"', "'"):
                try:
                    field_counts: list[int] = []
                    all_fields: list[list[str]] = []
                    for ln in data_lines:
                        reader = csv.reader([ln], delimiter=delim, quotechar=qchar)
                        fields = next(reader)
                        field_counts.append(len(fields))
                        all_fields.append(fields)

                    if not field_counts:
                        continue

                    first_count = field_counts[0]
                    if first_count <= 1:
                        continue

                    all_same = all(c == first_count for c in field_counts)
                    consistency_score = first_count * 10.0 if all_same else float(first_count)

                    # Tiebreaker: prefer ; then , then others
                    delim_tiebreaker = {";": 0.5, ",": 0.4}.get(delim, 0.0)
                    total_score = consistency_score + delim_tiebreaker

                    # Secondary tiebreaker: count literal occurrences of the
                    # *other* quotechar — fewer suggests the candidate is right.
                    other_char = other_q[qchar]
                    other_count = sum(
                        f.count(other_char) for fields in all_fields for f in fields
                    )

                    if total_score > best_score or (
                        total_score == best_score
                        and other_count < best_other_quote_count
                    ):
                        best_score = total_score
                        best_delim = delim
                        best_quote = qchar
                        best_other_quote_count = other_count
                except Exception:  # noqa: BLE001
                    continue

        return best_delim, best_quote

    def load(self, path: str | Path, settings: CsvReadSettings) -> CsvDocument:
        source_path = Path(path)
        with source_path.open("r", encoding=settings.encoding, newline=settings.newline) as handle:
            text = handle.read()
        effective = self._dialect_from_settings(settings)

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

    def save(self, path: str | Path, document: CsvDocument, settings: CsvWriteSettings) -> None:
        target_path = Path(path)
        all_headers = list(document.headers)

        # Determine export column order: configured export_order is
        # normalized (deduplicated, stale names removed, missing current
        # headers appended), then falls back to document header order.
        export_headers = self._normalize_export_order(settings.export_order, all_headers)

        effective = self._dialect_from_settings(settings)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        with target_path.open(
            "w",
            encoding=settings.encoding,
            newline=settings.newline,
        ) as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=export_headers,
                delimiter=effective.delimiter,
                quotechar=effective.quotechar,
                lineterminator=effective.lineterminator,
            )
            if settings.write_header:
                writer.writeheader()
            for row in document.rows:
                output = {}
                for header in export_headers:
                    value = row.get(header, "")
                    field_config = settings.fields.get(header)
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

    @staticmethod
    def _dialect_from_settings(settings: CsvReadSettings | CsvWriteSettings) -> CsvDialectSettings:
        return CsvDialectSettings(
            delimiter=settings.delimiter,
            quotechar=settings.quotechar,
            lineterminator=settings.newline or CsvDialectSettings().lineterminator,
        )
