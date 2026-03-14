from product_description_tool.preview import analyze_html_content, format_html_stats


def test_analyze_html_content_counts_sections_paragraphs_words_and_characters() -> None:
    stats = analyze_html_content("<h2>Summer <b>Sale</b></h2><p>Fast<br>Dry</p><ul><li>Two words</li></ul>")

    assert stats.sections == 1
    assert stats.paragraphs == 3
    assert stats.words == 6
    assert stats.characters == 25
    assert format_html_stats(stats) == "Sections: 1, Paragraphs: 3, Words: 6, Characters: 25"


def test_analyze_html_content_treats_tags_as_word_separators() -> None:
    stats = analyze_html_content("he<b>llo</b>")

    assert stats.sections == 0
    assert stats.paragraphs == 0
    assert stats.words == 2
    assert stats.characters == 5
