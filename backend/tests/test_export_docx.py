"""Tests for .docx export service."""

import io

import pytest
from docx import Document as DocxDocument


@pytest.fixture
def sample_source() -> str:
    return "坚持以人民为中心的发展思想。"


@pytest.fixture
def sample_translation() -> str:
    return "Adhere to the people-centered development philosophy."


@pytest.fixture
def sample_annotations() -> list[dict]:
    return [
        {
            "phrase": "people-centered",
            "risk_level": "medium",
            "risk_type": "political_sensitivity",
            "explanation": "部分西方媒体将其与民粹主义关联",
        }
    ]


class TestGenerateTranslationDocx:
    def test_returns_non_empty_bytes(self, sample_source, sample_translation, sample_annotations):
        """Verify the function returns a non-empty bytes object."""
        from app.services.export_docx import generate_translation_docx

        result = generate_translation_docx(
            source_text=sample_source,
            translated_text=sample_translation,
            risk_annotations=sample_annotations,
            language="en-GB",
        )
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_docx_contains_source_and_translation(self, sample_source, sample_translation, sample_annotations):
        """Verify the generated .docx contains both source and translation paragraphs."""
        from app.services.export_docx import generate_translation_docx

        result = generate_translation_docx(
            source_text=sample_source,
            translated_text=sample_translation,
            risk_annotations=sample_annotations,
            language="en-GB",
        )
        doc = DocxDocument(io.BytesIO(result))
        text = "\n".join(p.text for p in doc.paragraphs)
        assert "坚持以人民为中心的发展思想" in text
        assert "people-centered development" in text

    def test_docx_has_headings(self, sample_source, sample_translation, sample_annotations):
        """Verify the document has at least one heading (原文/译文)."""
        from app.services.export_docx import generate_translation_docx

        result = generate_translation_docx(
            source_text=sample_source,
            translated_text=sample_translation,
            risk_annotations=sample_annotations,
            language="en-GB",
        )
        doc = DocxDocument(io.BytesIO(result))
        headings = [p for p in doc.paragraphs if p.style.name.startswith("Heading")]
        assert len(headings) >= 2

    def test_annotations_become_comments(self, sample_source, sample_translation, sample_annotations):
        """Verify risk annotations are added as Word comments on matching text."""
        from app.services.export_docx import generate_translation_docx

        result = generate_translation_docx(
            source_text=sample_source,
            translated_text=sample_translation,
            risk_annotations=sample_annotations,
            language="en-GB",
        )
        doc = DocxDocument(io.BytesIO(result))

        comment_count = 0
        for rel in doc.part.rels.values():
            if "comment" in str(rel.reltype).lower():
                comment_count += 1
        # At least one comment relationship exists
        assert comment_count >= 1

    def test_empty_annotations_list(self, sample_source, sample_translation):
        """Verify the function handles an empty annotations list."""
        from app.services.export_docx import generate_translation_docx

        result = generate_translation_docx(
            source_text=sample_source,
            translated_text=sample_translation,
            risk_annotations=[],
            language="en-GB",
        )
        doc = DocxDocument(io.BytesIO(result))
        text = "\n".join(p.text for p in doc.paragraphs)
        assert "原文" in text
        assert "译文" in text

    def test_empty_translation_raises(self, sample_source, sample_annotations):
        """Verify empty translation raises ValueError."""
        from app.services.export_docx import generate_translation_docx

        with pytest.raises(ValueError, match="translated_text is required"):
            generate_translation_docx(
                source_text=sample_source,
                translated_text="",
                risk_annotations=sample_annotations,
                language="en-GB",
            )
