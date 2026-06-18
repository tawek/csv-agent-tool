from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from product_description_tool.kb_conversion import (
    ALL_KB_EXTENSIONS,
    CONVERTIBLE_EXTENSIONS,
    DIRECT_READ_EXTENSIONS,
    ConversionCache,
    ConversionFailedError,
    KnowledgeBaseContentService,
    MarkItDownUnavailableError,
)


# ===================================================================
# Extension classification tests
# ===================================================================


class TestClassification:
    def test_direct_read_extensions(self) -> None:
        assert ".md" in DIRECT_READ_EXTENSIONS
        assert ".markdown" in DIRECT_READ_EXTENSIONS
        assert ".txt" in DIRECT_READ_EXTENSIONS
        assert ".csv" in DIRECT_READ_EXTENSIONS
        assert len(DIRECT_READ_EXTENSIONS) == 4

    def test_convertible_extensions(self) -> None:
        assert ".pdf" in CONVERTIBLE_EXTENSIONS
        assert ".docx" in CONVERTIBLE_EXTENSIONS
        assert ".pptx" in CONVERTIBLE_EXTENSIONS
        assert ".xlsx" in CONVERTIBLE_EXTENSIONS
        assert ".html" in CONVERTIBLE_EXTENSIONS
        assert ".epub" in CONVERTIBLE_EXTENSIONS

    def test_all_kb_extensions_union(self) -> None:
        assert ALL_KB_EXTENSIONS == DIRECT_READ_EXTENSIONS | CONVERTIBLE_EXTENSIONS
        assert len(ALL_KB_EXTENSIONS) == len(DIRECT_READ_EXTENSIONS) + len(CONVERTIBLE_EXTENSIONS)

    def test_classify_suffix_direct_read(self) -> None:
        svc = KnowledgeBaseContentService()
        assert svc.classify_suffix(".md") == "direct_read"
        assert svc.classify_suffix(".txt") == "direct_read"
        assert svc.classify_suffix(".csv") == "direct_read"

    def test_classify_suffix_convertible(self) -> None:
        svc = KnowledgeBaseContentService()
        assert svc.classify_suffix(".pdf") == "convertible"
        assert svc.classify_suffix(".docx") == "convertible"
        assert svc.classify_suffix(".html") == "convertible"

    def test_classify_suffix_unsupported(self) -> None:
        svc = KnowledgeBaseContentService()
        assert svc.classify_suffix(".exe") == "convertible"
        assert svc.classify_suffix(".py") == "convertible"
        assert svc.classify_suffix(".jpg") == "convertible"

    def test_is_supported_extension(self) -> None:
        svc = KnowledgeBaseContentService()
        assert svc.is_supported_extension(".md") is True
        assert svc.is_supported_extension(".pdf") is True
        assert svc.is_supported_extension(".txt") is True
        assert svc.is_supported_extension(".exe") is True


# ===================================================================
# ConversionCache tests
# ===================================================================


class TestConversionCache:
    def test_cache_default_dir(self) -> None:
        path = ConversionCache.default_cache_dir()
        assert "kb-markitdown" in str(path)

    def test_cache_key_changes_with_content(self, tmp_path: Path) -> None:
        cache = ConversionCache(cache_dir=tmp_path)
        src = tmp_path / "test.pdf"
        src.write_bytes(b"hello world")
        key1 = cache._cache_key(src)
        src.write_bytes(b"different content")
        key2 = cache._cache_key(src)
        assert key1 != key2

    def test_cache_key_changes_with_extension(self, tmp_path: Path) -> None:
        cache = ConversionCache(cache_dir=tmp_path)
        src_a = tmp_path / "a.pdf"
        src_b = tmp_path / "a.docx"
        src_a.write_bytes(b"same content")
        src_b.write_bytes(b"same content")
        key_a = cache._cache_key(src_a)
        key_b = cache._cache_key(src_b)
        # same hash but different suffix -> different key
        assert key_a != key_b

    def test_store_and_retrieve(self, tmp_path: Path) -> None:
        cache = ConversionCache(cache_dir=tmp_path)
        src = tmp_path / "test.pdf"
        src.write_bytes(b"source content")
        md_content = "# Converted Markdown"
        stored_path = cache.store(src, md_content)
        assert stored_path.exists()
        assert stored_path.suffix == ".md"

        # Retrieve
        cached = cache.get_cached_path(src)
        assert cached is not None
        assert cached.read_text(encoding="utf-8") == md_content

        # Retrieve content
        content = cache.get_cached_content(src)
        assert content == md_content

    def test_metadata_written(self, tmp_path: Path) -> None:
        cache = ConversionCache(cache_dir=tmp_path)
        src = tmp_path / "test.pdf"
        src.write_bytes(b"content for metadata test")
        cache.store(src, "# md")
        # Find the meta file
        key = cache._cache_key(src)
        meta_path = cache._cache_root / f"{key}.meta.json"
        assert meta_path.exists()
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        assert meta["source_path"] == str(src.resolve())
        assert "converter_identity" in meta
        assert "created_at" in meta

    def test_cache_miss_returns_none(self, tmp_path: Path) -> None:
        cache = ConversionCache(cache_dir=tmp_path)
        src = tmp_path / "never_cached.pdf"
        src.write_bytes(b"content")
        assert cache.get_cached_path(src) is None
        assert cache.get_cached_content(src) is None

    def test_cache_invalidated_on_source_change(self, tmp_path: Path) -> None:
        cache = ConversionCache(cache_dir=tmp_path)
        src = tmp_path / "test.pdf"
        src.write_bytes(b"original")
        cache.store(src, "# Original")
        assert cache.get_cached_content(src) == "# Original"

        # Change source content
        src.write_bytes(b"modified")
        assert cache.get_cached_content(src) is None  # different hash -> miss

    def test_converter_identity(self) -> None:
        identity = ConversionCache._converter_identity()
        assert identity.startswith("markitdown-")


# ===================================================================
# KnowledgeBaseContentService tests
# ===================================================================


@pytest.fixture
def kb_dir(tmp_path: Path) -> Path:
    d = tmp_path / "kb"
    d.mkdir()
    (d / "help.md").write_text("# Help content", encoding="utf-8")
    (d / "data.csv").write_text("a,b\n1,2", encoding="utf-8")
    (d / "notes.txt").write_text("Some notes.", encoding="utf-8")
    return d


class TestKnowledgeBaseContentService:
    def test_validate_supported_accepts_direct_read(self, kb_dir: Path) -> None:
        svc = KnowledgeBaseContentService()
        assert svc.validate_supported(kb_dir / "help.md") is None
        assert svc.validate_supported(kb_dir / "data.csv") is None
        assert svc.validate_supported(kb_dir / "notes.txt") is None

    def test_validate_supported_accepts_runtime_convertible_file(self, kb_dir: Path) -> None:
        svc = KnowledgeBaseContentService()
        err = svc.validate_supported(kb_dir / "help.md")
        assert err is None
        bad = kb_dir / "script.py"
        bad.write_text("x=1")
        err = svc.validate_supported(bad)
        assert err is None

    def test_validate_supported_convertible_checks_markitdown(self, kb_dir: Path) -> None:
        """For convertible files, validate_supported checks MarkItDown availability."""
        svc = KnowledgeBaseContentService()
        pdf = kb_dir / "doc.pdf"
        pdf.write_bytes(b"%PDF-1.4 fake pdf")
        err = svc.validate_supported(pdf)
        # MarkItDown IS available in test env, so this should pass
        assert err is None

    def test_is_conversion_available(self) -> None:
        svc = KnowledgeBaseContentService()
        # Should be True since markitdown is installed in the dev env
        assert svc.is_conversion_available() is True

    # ------------------------------------------------------------------
    # load_markdown — direct-read types
    # ------------------------------------------------------------------

    def test_load_markdown_direct_read_md(self, kb_dir: Path) -> None:
        svc = KnowledgeBaseContentService()
        content = svc.load_markdown(kb_dir / "help.md", kb_dir)
        assert content == "# Help content"

    def test_load_markdown_direct_read_csv(self, kb_dir: Path) -> None:
        svc = KnowledgeBaseContentService()
        content = svc.load_markdown(kb_dir / "data.csv", kb_dir)
        assert "a,b" in content

    def test_load_markdown_direct_read_txt(self, kb_dir: Path) -> None:
        svc = KnowledgeBaseContentService()
        content = svc.load_markdown(kb_dir / "notes.txt", kb_dir)
        assert content == "Some notes."

    def test_load_markdown_direct_read_utf8(self, kb_dir: Path) -> None:
        """Verify UTF-8 text is returned correctly."""
        path = kb_dir / "utf8.txt"
        path.write_text("café résumé", encoding="utf-8")
        svc = KnowledgeBaseContentService()
        content = svc.load_markdown(path, kb_dir)
        assert content == "café résumé"

    # ------------------------------------------------------------------
    # load_markdown — convertible types (real conversion)
    # ------------------------------------------------------------------

    def test_load_markdown_convertible_html(self, kb_dir: Path) -> None:
        """HTML files can be converted to Markdown."""
        html_path = kb_dir / "test.html"
        html_path.write_text(
            "<html><body><h1>Hello</h1><p>World</p></body></html>",
            encoding="utf-8",
        )
        svc = KnowledgeBaseContentService()
        content = svc.load_markdown(html_path, kb_dir)
        assert "Hello" in content
        assert "World" in content

    def test_load_markdown_convertible_caches_result(self, kb_dir: Path) -> None:
        """Converted markdown is cached and reused."""
        html_path = kb_dir / "cached.html"
        html_path.write_text("<html><body><p>Cache test</p></body></html>", encoding="utf-8")
        svc = KnowledgeBaseContentService()
        content1 = svc.load_markdown(html_path, kb_dir)
        assert "Cache test" in content1

        # Second load should return from cache (not re-convert)
        content2 = svc.load_markdown(html_path, kb_dir)
        assert content2 == content1

    def test_load_markdown_convertible_cache_invalidated_on_change(self, kb_dir: Path) -> None:
        """Cache is invalidated when source file content changes."""
        html_path = kb_dir / "changing.html"
        html_path.write_text("<html><body><p>Version 1</p></body></html>", encoding="utf-8")
        svc = KnowledgeBaseContentService()
        content1 = svc.load_markdown(html_path, kb_dir)
        assert "Version 1" in content1

        # Modify source
        html_path.write_text("<html><body><p>Version 2</p></body></html>", encoding="utf-8")
        content2 = svc.load_markdown(html_path, kb_dir)
        assert "Version 2" in content2
        assert content2 != content1

    # ------------------------------------------------------------------
    # load_markdown — error cases
    # ------------------------------------------------------------------

    def test_load_markdown_raises_for_path_escape(self, kb_dir: Path, tmp_path: Path) -> None:
        """Path outside KB root raises ValueError."""
        outside = tmp_path / "outside.md"
        outside.write_text("secret", encoding="utf-8")
        svc = KnowledgeBaseContentService()
        with pytest.raises(ValueError, match="outside the knowledge-base"):
            svc.load_markdown(outside, kb_dir)

    def test_load_markdown_raises_for_nonexistent(self, kb_dir: Path) -> None:
        svc = KnowledgeBaseContentService()
        missing = kb_dir / "nonexistent.md"
        with pytest.raises(FileNotFoundError, match="not found"):
            svc.load_markdown(missing, kb_dir)

    def test_load_markdown_raises_for_directory(self, kb_dir: Path) -> None:
        svc = KnowledgeBaseContentService()
        with pytest.raises(ValueError, match="Not a file"):
            svc.load_markdown(kb_dir, kb_dir)

    def test_load_markdown_raises_for_unconvertible_file(self, kb_dir: Path) -> None:
        svc = KnowledgeBaseContentService()
        exe = kb_dir / "binary.exe"
        exe.write_bytes(b"MZ\x90")
        with pytest.raises(ConversionFailedError, match="Failed to convert"):
            svc.load_markdown(exe, kb_dir)

    def test_load_markdown_raises_when_markitdown_unavailable(
        self, kb_dir: Path, monkeypatch
    ) -> None:
        """When markitdown is not importable, convertible files raise."""
        import product_description_tool.kb_conversion as kc

        # Make _check_markitdown return False
        real_check = kc.KnowledgeBaseContentService._check_markitdown
        monkeypatch.setattr(
            kc.KnowledgeBaseContentService,
            "_check_markitdown",
            lambda self: False,
        )

        pdf = kb_dir / "test.pdf"
        pdf.write_bytes(b"%PDF-1.4 fake")
        svc = KnowledgeBaseContentService()
        with pytest.raises(MarkItDownUnavailableError, match="not available"):
            svc.load_markdown(pdf, kb_dir)

    def test_load_markdown_handles_conversion_failure(
        self, kb_dir: Path, monkeypatch
    ) -> None:
        """When conversion raises, ConversionFailedError is raised."""
        import markitdown as _md

        pdf = kb_dir / "broken.pdf"
        pdf.write_bytes(b"fake pdf content")
        svc = KnowledgeBaseContentService()

        class FailingConverter:
            def convert(self, source, **kwargs):
                msg = f"Fake failure for {source}"
                raise RuntimeError(msg)

        # Patch markitdown.MarkItDown so the local import in load_markdown
        # picks up the failing converter
        monkeypatch.setattr(_md, "MarkItDown", lambda: FailingConverter())
        svc._markitdown_available = None  # Reset cached state

        with pytest.raises(ConversionFailedError, match="Failed to convert"):
            svc.load_markdown(pdf, kb_dir)

    # ------------------------------------------------------------------
    # Real-world PDF/Office conversion (happy path)
    # ------------------------------------------------------------------

    def test_load_markdown_html_conversion(self, kb_dir: Path) -> None:
        """HTML to Markdown conversion produces sensible output."""
        html_path = kb_dir / "article.html"
        html_path.write_text(
            "<html><body>"
            "<h1>Article Title</h1>"
            "<p>First paragraph.</p>"
            "<ul><li>Item A</li><li>Item B</li></ul>"
            "</body></html>",
            encoding="utf-8",
        )
        svc = KnowledgeBaseContentService()
        result = svc.load_markdown(html_path, kb_dir)
        assert "Article Title" in result
        assert "First paragraph" in result
        assert "Item A" in result
        # Should not contain raw HTML tags
        assert "<h1>" not in result


# ===================================================================
# Edge cases: cache with unreadable files, empty files
# ===================================================================


def test_cache_with_empty_source(tmp_path: Path) -> None:
    cache = ConversionCache(cache_dir=tmp_path)
    empty = tmp_path / "empty.pdf"
    empty.write_bytes(b"")
    key = cache._cache_key(empty)
    assert key.startswith(hashlib.sha256(b"").hexdigest())


def test_cache_with_unreadable_source(tmp_path: Path) -> None:
    cache = ConversionCache(cache_dir=tmp_path)
    missing = tmp_path / "missing.pdf"
    # File doesn't exist; key should use empty hash fallback
    key = cache._cache_key(missing)
    assert key.startswith(hashlib.sha256(b"").hexdigest())
