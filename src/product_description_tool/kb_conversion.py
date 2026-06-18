from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

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
})

# Complete set of direct-read and commonly known convertible extensions.
# Runtime support is capability-based: any non-direct KB file may be offered
# for conversion, and MarkItDown decides whether it can be converted.
ALL_KB_EXTENSIONS: frozenset[str] = DIRECT_READ_EXTENSIONS | CONVERTIBLE_EXTENSIONS


class MarkItDownUnavailableError(RuntimeError):
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
    def _converter_identity() -> str:
        try:
            from markitdown import __version__ as md_version
            return f"markitdown-{md_version}"
        except ImportError:
            return "markitdown-unavailable"

    def _cache_key(self, source_path: Path) -> str:
        source_hash = self._source_hash(source_path)
        suffix = source_path.suffix.lower().lstrip(".") or "unknown"
        converter_id = self._converter_identity()
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
            "converter_identity": self._converter_identity(),
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

    def _check_markitdown(self) -> bool:
        if self._markitdown_available is None:
            try:
                import markitdown  # noqa: F401
                self._markitdown_available = True
            except ImportError:
                self._markitdown_available = False
        return self._markitdown_available

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
        """Check whether MarkItDown is importable for conversion."""
        return self._check_markitdown()

    def validate_supported(self, file_path: Path) -> str | None:
        """Validate that *file_path* has a supported type.

        Returns an error message string if conversion is required but
        MarkItDown is unavailable.
        Returns ``None`` when the file can be used.
        """
        classification = self.classify_suffix(file_path.suffix.lower())
        if classification == "convertible" and not self._check_markitdown():
            return (
                f"file '{file_path.name}' requires conversion to Markdown "
                "but MarkItDown is not available"
            )
        return None

    def load_markdown(self, file_path: Path, kb_root: Path) -> str:
        """Load KB file content as Markdown.

        For direct-read types (``.md``, ``.markdown``, ``.csv``) the UTF-8
        text is returned as-is.  For convertible types the file is converted
        through MarkItDown, with transparent caching by source content hash.

        Args:
            file_path: Resolved path of the KB file (must be under *kb_root*).
            kb_root: Resolved KB root directory.

        Returns:
            Markdown string content.

        Raises:
            ValueError: Path escape or not-a-file.
            FileNotFoundError: File does not exist.
            MarkItDownUnavailableError: Conversion needed but MarkItDown is
                not importable.
            ConversionFailedError: Conversion attempt failed.
            UnsupportedFileTypeError: Reserved for future explicit hard rejects.
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

        classification = self.classify_suffix(resolved_path.suffix.lower())

        if classification == "direct_read":
            return resolved_path.read_text(encoding="utf-8")

        # Check cache first
        cached = self._cache.get_cached_content(resolved_path)
        if cached is not None:
            return cached

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
