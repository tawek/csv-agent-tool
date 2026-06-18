from __future__ import annotations

import hashlib
import importlib.metadata
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
import xml.etree.ElementTree as ET

import platformdirs


# Directly readable/editable KB file types (no conversion needed)
DIRECT_READ_EXTENSIONS: frozenset[str] = frozenset({".md", ".markdown", ".txt", ".csv"})

# File types that MarkItDown can convert to Markdown for viewing and prompt use.
# This list targets high-confidence local document formats.
# The service performs capability-based discovery at runtime by attempting
# conversion; unknown extensions are classified as unsupported.
CONVERTIBLE_EXTENSIONS: frozenset[str] = frozenset({
    ".pdf",
    ".pptx", ".ppt",
    ".docx", ".doc",
    ".xlsx", ".xls",
    ".html", ".htm",
    ".epub",
    ".odt", ".ods",
})

# Complete set of direct-read and commonly known convertible extensions.
# Runtime support is capability-based: any non-direct KB file may be offered
# for conversion, and MarkItDown decides whether it can be converted.
ALL_KB_EXTENSIONS: frozenset[str] = DIRECT_READ_EXTENSIONS | CONVERTIBLE_EXTENSIONS

ODT_NAMESPACES = {
    "office": "urn:oasis:names:tc:opendocument:xmlns:office:1.0",
    "style": "urn:oasis:names:tc:opendocument:xmlns:style:1.0",
    "table": "urn:oasis:names:tc:opendocument:xmlns:table:1.0",
    "text": "urn:oasis:names:tc:opendocument:xmlns:text:1.0",
    "fo": "urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0",
}
_LOCAL_CONVERTER_REVISION = "kb-local-v2"


def _ns_attr(namespace: str, name: str) -> str:
    return f"{{{ODT_NAMESPACES[namespace]}}}{name}"


def _strip_ns(tag: str) -> str:
    return tag.split("}", 1)[1] if "}" in tag else tag


class _OdtStyleIndex:
    """Index ODT styles needed for lightweight Markdown rendering."""

    def __init__(self, root: ET.Element) -> None:
        self._styles: dict[str, dict[str, str]] = {}
        self._text_bold: set[str] = set()
        self._text_code: set[str] = set()
        self._preformatted_paragraphs: set[str] = set()
        self._list_kinds: dict[str, str] = {}

        for style in root.findall(".//style:style", ODT_NAMESPACES):
            name = style.get(_ns_attr("style", "name"))
            if not name:
                continue
            parent = style.get(_ns_attr("style", "parent-style-name"), "")
            family = style.get(_ns_attr("style", "family"), "")
            self._styles[name] = {"parent": parent, "family": family}

            text_props = style.find("style:text-properties", ODT_NAMESPACES)
            if text_props is not None:
                font_weight = text_props.get(_ns_attr("fo", "font-weight"), "")
                font_family = " ".join(
                    filter(
                        None,
                        [
                            text_props.get(_ns_attr("fo", "font-family"), ""),
                            text_props.get(_ns_attr("style", "font-name"), ""),
                        ],
                    )
                ).lower()
                if font_weight == "bold" or "strong" in parent.lower() or "strong" in name.lower():
                    self._text_bold.add(name)
                if "mono" in font_family or "source" in parent.lower() or "code" in parent.lower():
                    self._text_code.add(name)

            if family == "paragraph" and (
                "preformatted" in parent.lower() or "preformatted" in name.lower()
            ):
                self._preformatted_paragraphs.add(name)

        for list_style in root.findall(".//text:list-style", ODT_NAMESPACES):
            name = list_style.get(_ns_attr("style", "name"))
            if not name or not list(list_style):
                continue
            first_child = _strip_ns(list(list_style)[0].tag)
            self._list_kinds[name] = "ordered" if first_child == "list-level-style-number" else "unordered"

    def is_preformatted_paragraph(self, style_name: str | None) -> bool:
        return bool(style_name and style_name in self._preformatted_paragraphs)

    def is_bold_text(self, style_name: str | None) -> bool:
        return bool(style_name and style_name in self._text_bold)

    def is_code_text(self, style_name: str | None) -> bool:
        return bool(style_name and style_name in self._text_code)

    def list_kind(self, style_name: str | None) -> str:
        if not style_name:
            return "unordered"
        return self._list_kinds.get(style_name, "unordered")


def _wrap_inline_code(text: str) -> str:
    if not text or "\n" in text:
        return text
    if text.startswith("`") and text.endswith("`"):
        return text
    return f"`{text}`"


def _normalize_odt_text(text: str) -> str:
    return text.replace("\xa0", " ")


def _render_odt_children(element: ET.Element, styles: _OdtStyleIndex, *, in_code_block: bool) -> str:
    pieces: list[str] = []
    if element.text:
        pieces.append(_normalize_odt_text(element.text))
    for child in element:
        pieces.append(_render_odt_inline(child, styles, in_code_block=in_code_block))
        if child.tail:
            pieces.append(_normalize_odt_text(child.tail))
    return "".join(pieces)


def _render_odt_inline(element: ET.Element, styles: _OdtStyleIndex, *, in_code_block: bool) -> str:
    tag = _strip_ns(element.tag)
    if tag == "s":
        count = int(element.get(_ns_attr("text", "c"), "1"))
        return " " * count
    if tag == "tab":
        return "\t"
    if tag == "line-break":
        return "\n"

    text = _render_odt_children(element, styles, in_code_block=in_code_block)
    if tag == "span" and not in_code_block:
        style_name = element.get(_ns_attr("text", "style-name"))
        if styles.is_code_text(style_name):
            text = _wrap_inline_code(text)
        if styles.is_bold_text(style_name):
            text = f"**{text}**"
    return text


def _render_odt_paragraph(element: ET.Element, styles: _OdtStyleIndex) -> tuple[str, bool]:
    style_name = element.get(_ns_attr("text", "style-name"))
    is_preformatted = styles.is_preformatted_paragraph(style_name)
    text = _render_odt_children(element, styles, in_code_block=is_preformatted)
    return text.strip("\n"), is_preformatted


def _convert_odt_list(list_elem: ET.Element, styles: _OdtStyleIndex, depth: int = 0) -> str:
    lines: list[str] = []
    style_name = list_elem.get(_ns_attr("text", "style-name"))
    ordered = styles.list_kind(style_name) == "ordered"
    item_index = 1

    for item in list_elem.findall("text:list-item", ODT_NAMESPACES):
        first_paragraph = True
        for child in item:
            tag = _strip_ns(child.tag)
            indent = "  " * depth
            if tag == "p":
                text, _ = _render_odt_paragraph(child, styles)
                if not text.strip():
                    continue
                if first_paragraph:
                    marker = f"{item_index}." if ordered else "-"
                    lines.append(f"{indent}{marker} {text.strip()}")
                    first_paragraph = False
                else:
                    lines.append(f"{indent}  {text.strip()}")
            elif tag == "list":
                nested = _convert_odt_list(child, styles, depth + 1)
                if nested:
                    lines.append(nested)
        item_index += 1

    return "\n".join(lines)


def _odt_table_cell_text(cell: ET.Element, styles: _OdtStyleIndex) -> str:
    parts: list[str] = []
    for child in cell:
        tag = _strip_ns(child.tag)
        if tag == "p":
            text, _ = _render_odt_paragraph(child, styles)
            if text.strip():
                parts.append(text.strip())
        elif tag == "list":
            text = _convert_odt_list(child, styles)
            if text.strip():
                parts.append(text.strip())
    return "<br>".join(parts)


def _convert_odt_table(table_elem: ET.Element, styles: _OdtStyleIndex) -> str:
    rows: list[list[str]] = []
    row_elements: list[ET.Element] = []
    for child in table_elem:
        tag = _strip_ns(child.tag)
        if tag == "table-row":
            row_elements.append(child)
        elif tag == "table-header-rows":
            row_elements.extend(child.findall("table:table-row", ODT_NAMESPACES))

    for row in row_elements:
        row_cells: list[str] = []
        for cell in row.findall("table:table-cell", ODT_NAMESPACES):
            repeat = int(cell.get(_ns_attr("table", "number-columns-repeated"), "1"))
            cell_text = _odt_table_cell_text(cell, styles)
            row_cells.extend([cell_text] * repeat)
        if any(cell.strip() for cell in row_cells):
            rows.append(row_cells)

    if not rows:
        return ""

    column_count = max(len(row) for row in rows)
    normalized = [row + [""] * (column_count - len(row)) for row in rows]
    markdown_lines = [f"| {' | '.join(normalized[0])} |"]
    markdown_lines.append("| " + " | ".join(["---"] * column_count) + " |")
    for row in normalized[1:]:
        markdown_lines.append(f"| {' | '.join(row)} |")
    return "\n".join(markdown_lines)


def _convert_odt_document(xml_bytes: bytes) -> str:
    root = ET.fromstring(xml_bytes)
    styles = _OdtStyleIndex(root)
    text_root = root.find(".//office:body/office:text", ODT_NAMESPACES)
    if text_root is None:
        return ""

    blocks: list[str] = []
    preformatted_lines: list[str] = []

    def flush_preformatted() -> None:
        if preformatted_lines:
            blocks.append("```\n" + "\n".join(preformatted_lines).rstrip() + "\n```")
            preformatted_lines.clear()

    def visit(container: ET.Element) -> None:
        for child in container:
            tag = _strip_ns(child.tag)
            if tag in {"sequence-decls", "frame"}:
                continue
            if tag == "section":
                visit(child)
                continue
            if tag == "h":
                flush_preformatted()
                text = _render_odt_children(child, styles, in_code_block=False).strip()
                if text:
                    level = int(child.get(_ns_attr("text", "outline-level"), "1"))
                    blocks.append(f"{'#' * level} {text}")
                continue
            if tag == "p":
                text, is_preformatted = _render_odt_paragraph(child, styles)
                if is_preformatted:
                    if text.strip():
                        preformatted_lines.append(text.rstrip())
                    else:
                        flush_preformatted()
                    continue
                flush_preformatted()
                if text.strip():
                    blocks.append(text.strip())
                continue
            if tag == "list":
                flush_preformatted()
                text = _convert_odt_list(child, styles)
                if text.strip():
                    blocks.append(text)
                continue
            if tag == "table":
                flush_preformatted()
                text = _convert_odt_table(child, styles)
                if text.strip():
                    blocks.append(text)
                continue

    visit(text_root)
    flush_preformatted()
    return "\n\n".join(block for block in blocks if block.strip())


class ConversionBackendUnavailableError(RuntimeError):
    """Raised when the required file-conversion backend is unavailable."""


class MarkItDownUnavailableError(ConversionBackendUnavailableError):
    """Raised when MarkItDown is not installed or cannot be imported."""


class ConversionFailedError(RuntimeError):
    """Raised when a conversion attempt fails."""


class UnsupportedFileTypeError(ValueError):
    """Raised when a file type is not supported for conversion."""


class ConversionCache:
    """Local cache of converted Markdown artifacts keyed by source content hash.

    Cache location: ``<platformdirs user_cache_dir>/kb-markitdown/``

    Cache keys incorporate:
    - SHA-256 hash of the source file bytes
    - The source file suffix
    - Converter identity (backend kind + version)
    """

    _CACHE_SUBDIR = "kb-markitdown"

    def __init__(self, cache_dir: str | Path | None = None) -> None:
        if cache_dir is None:
            cache_dir = platformdirs.user_cache_dir("product-description-tool")
        self._cache_root = Path(cache_dir) / self._CACHE_SUBDIR
        self._cache_root.mkdir(parents=True, exist_ok=True)

    @classmethod
    def default_cache_dir(cls) -> Path:
        """Return the default cache root directory."""
        return Path(platformdirs.user_cache_dir("product-description-tool")) / cls._CACHE_SUBDIR

    @staticmethod
    def _source_hash(source_path: Path) -> str:
        try:
            return hashlib.sha256(source_path.read_bytes()).hexdigest()
        except (OSError, PermissionError):
            return hashlib.sha256(b"").hexdigest()

    @staticmethod
    def _converter_identity(source_path: Path | None = None) -> str:
        suffix = source_path.suffix.lower() if source_path is not None else ""
        if suffix == ".odt":
            return f"odt-stdlib-{_LOCAL_CONVERTER_REVISION}"
        if suffix == ".ods":
            try:
                return f"odfpy-{importlib.metadata.version('odfpy')}"
            except importlib.metadata.PackageNotFoundError:
                return "odfpy-unavailable"
        try:
            from markitdown import __version__ as md_version
            return f"markitdown-{md_version}"
        except ImportError:
            return "markitdown-unavailable"

    def _cache_key(self, source_path: Path) -> str:
        source_hash = self._source_hash(source_path)
        suffix = source_path.suffix.lower().lstrip(".") or "unknown"
        converter_id = self._converter_identity(source_path)
        return f"{source_hash}-{suffix}-{converter_id}"

    def get_cached_path(self, source_path: Path) -> Path | None:
        """Return the path of a cached conversion artifact, or *None*."""
        key = self._cache_key(source_path)
        md_path = self._cache_root / f"{key}.md"
        meta_path = self._cache_root / f"{key}.meta.json"
        if md_path.exists() and meta_path.exists():
            return md_path
        return None

    def get_cached_content(self, source_path: Path) -> str | None:
        """Return cached conversion content, or *None*."""
        cached = self.get_cached_path(source_path)
        if cached is not None:
            return cached.read_text(encoding="utf-8")
        return None

    def store(self, source_path: Path, markdown_content: str) -> Path:
        """Store the converted markdown and return the cached file path.

        Writes both ``<key>.md`` (content) and ``<key>.meta.json`` (metadata).
        """
        key = self._cache_key(source_path)
        md_path = self._cache_root / f"{key}.md"
        meta_path = self._cache_root / f"{key}.meta.json"

        md_path.write_text(markdown_content, encoding="utf-8")
        meta = {
            "source_path": str(source_path.resolve()),
            "source_size": source_path.stat().st_size,
            "converter_identity": self._converter_identity(source_path),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
        return md_path


class KnowledgeBaseContentService:
    """Shared service for resolving KB file content.

    Provides:
    - Classification of file types (direct-read, convertible, unsupported)
    - Extension and availability validation
    - Markdown loading with transparent caching for convertible files
    """

    def __init__(self, cache: ConversionCache | None = None) -> None:
        self._cache = cache or ConversionCache()
        self._markitdown_available: bool | None = None
        self._odfpy_available: bool | None = None

    def _check_markitdown(self) -> bool:
        if self._markitdown_available is None:
            try:
                import markitdown  # noqa: F401
                self._markitdown_available = True
            except ImportError:
                self._markitdown_available = False
        return self._markitdown_available

    def _check_odfpy(self) -> bool:
        if self._odfpy_available is None:
            try:
                import odf  # noqa: F401
                self._odfpy_available = True
            except ImportError:
                self._odfpy_available = False
        return self._odfpy_available

    @staticmethod
    def classify_suffix(suffix: str) -> str:
        """Classify a suffix as ``'direct_read'`` or ``'convertible'``.

        Any non-direct file is treated as conversion-backed at runtime so the
        KB picker and viewer can stay capability-based instead of relying on a
        hardcoded allowlist.
        """
        s = suffix.lower()
        if s in DIRECT_READ_EXTENSIONS:
            return "direct_read"
        return "convertible"

    @staticmethod
    def is_supported_extension(suffix: str) -> bool:
        """Return True for any suffix handled by KB content loading."""
        return True

    def is_conversion_available(self) -> bool:
        """Check whether at least one conversion backend is importable."""
        return True

    def _odt_suffix(self, suffix: str) -> bool:
        return suffix.lower() == ".odt"

    def _ods_suffix(self, suffix: str) -> bool:
        return suffix.lower() == ".ods"

    def validate_supported(self, file_path: Path) -> str | None:
        """Validate that *file_path* has a supported type.

        Returns an error message string if conversion is required but the
        required backend is unavailable.  Returns ``None`` when the file
        can be used.
        """
        suffix = file_path.suffix.lower()
        classification = self.classify_suffix(suffix)
        if classification != "convertible":
            return None
        if self._odt_suffix(suffix):
            return None
        if self._ods_suffix(suffix):
            if not self._check_odfpy():
                return (
                    f"file '{file_path.name}' requires odfpy for ODF conversion "
                    "but it is not available"
                )
            return None
        if not self._check_markitdown():
            return (
                f"file '{file_path.name}' requires conversion to Markdown "
                "but MarkItDown is not available"
            )
        return None

    @staticmethod
    def _convert_odt(file_path: Path) -> str:
        """Extract structured Markdown from an ODT file using stdlib XML parsing."""
        try:
            with zipfile.ZipFile(file_path) as archive:
                content_xml = archive.read("content.xml")
        except (KeyError, zipfile.BadZipFile, OSError) as exc:
            raise ValueError(f"Invalid ODT file: {exc}") from exc
        return _convert_odt_document(content_xml)

    @staticmethod
    def _convert_ods(file_path: Path) -> str:
        """Extract text from an ODF spreadsheet using odfpy."""
        from odf import opendocument, table as odf_table, text as odf_text
        doc = opendocument.load(str(file_path))
        lines: list[str] = []
        for sheet in doc.getElementsByType(odf_table.Table):
            name = sheet.getAttribute("name") or "Sheet"
            lines.append(f"## {name}")
            for row in sheet.getElementsByType(odf_table.TableRow):
                cells: list[str] = []
                for cell in row.getElementsByType(odf_table.TableCell):
                    cell_text_parts: list[str] = []
                    for p in cell.getElementsByType(odf_text.P):
                        for child in p.childNodes:
                            if hasattr(child, "data"):
                                cell_text_parts.append(child.data)
                    cells.append("".join(cell_text_parts))
                line = " | ".join(cells)
                if line.strip():
                    lines.append(line)
            lines.append("")
        return "\n".join(lines)

    def load_markdown(self, file_path: Path, kb_root: Path) -> str:
        """Load KB file content as Markdown.

        For direct-read types (``.md``, ``.markdown``, ``.csv``) the UTF-8
        text is returned as-is.  For convertible types the file is converted
        through MarkItDown (or odfpy for ODF files), with transparent
        caching by source content hash.

        Args:
            file_path: Resolved path of the KB file (must be under *kb_root*).
            kb_root: Resolved KB root directory.

        Returns:
            Markdown string content.

        Raises:
            ValueError: Path escape or not-a-file.
            FileNotFoundError: File does not exist.
            ConversionBackendUnavailableError: Conversion needed but the
                required backend is not available.
            ConversionFailedError: Conversion attempt failed.
        """
        resolved_path = file_path.resolve()
        resolved_root = kb_root.resolve()

        # Path-boundary check
        try:
            resolved_path.relative_to(resolved_root)
        except ValueError:
            raise ValueError(
                f"Path '{resolved_path}' is outside the knowledge-base "
                f"directory '{resolved_root}'."
            )

        if not resolved_path.exists():
            raise FileNotFoundError(f"File not found: {resolved_path}")

        if not resolved_path.is_file():
            raise ValueError(f"Not a file: {resolved_path}")

        suffix = resolved_path.suffix.lower()
        classification = self.classify_suffix(suffix)

        if classification == "direct_read":
            return resolved_path.read_text(encoding="utf-8")

        # Check cache first
        cached = self._cache.get_cached_content(resolved_path)
        if cached is not None:
            return cached

        if self._odt_suffix(suffix):
            try:
                markdown_content = self._convert_odt(resolved_path)
                self._cache.store(resolved_path, markdown_content)
                return markdown_content
            except Exception as exc:
                raise ConversionFailedError(
                    f"Failed to convert '{resolved_path.name}': {exc}"
                ) from exc

        # ODS files use odfpy
        if self._ods_suffix(suffix):
            if not self._check_odfpy():
                raise ConversionBackendUnavailableError(
                    f"Cannot convert '{resolved_path.name}': "
                    "odfpy is not available."
                )
            try:
                markdown_content = self._convert_ods(resolved_path)
                self._cache.store(resolved_path, markdown_content)
                return markdown_content
            except Exception as exc:
                raise ConversionFailedError(
                    f"Failed to convert '{resolved_path.name}': {exc}"
                ) from exc

        # All other convertible types go through MarkItDown
        if not self._check_markitdown():
            raise MarkItDownUnavailableError(
                f"Cannot convert '{resolved_path.name}': "
                "MarkItDown is not available."
            )

        try:
            from markitdown import MarkItDown

            converter = MarkItDown()
            result = converter.convert(str(resolved_path))
            markdown_content = result.text_content
        except Exception as exc:
            raise ConversionFailedError(
                f"Failed to convert '{resolved_path.name}': {exc}"
            ) from exc

        self._cache.store(resolved_path, markdown_content)
        return markdown_content
