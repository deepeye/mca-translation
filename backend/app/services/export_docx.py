"""Generate .docx translation documents with risk annotations as Word comments."""

from io import BytesIO

from docx import Document
from docx.oxml.ns import nsdecls
from docx.oxml import parse_xml
from docx.shared import Pt
from lxml import etree

from app.constants.languages import get_language


def _add_comment(doc, paragraph, text: str, author: str = "CulturalBridge"):
    """Add a Word comment to a paragraph.

    python-docx does not natively support comments, so we manipulate the
    XML directly. Each comment gets an incremental ID.
    """
    comments_part, comments_element = _get_or_create_comments_part(doc)

    comment_id = _next_comment_id()
    comment_xml = (
        f'<w:comment {nsdecls("w")} w:id="{comment_id}" w:author="{author}" w:date="{_now_iso()}">'
        f'<w:p><w:r><w:t xml:space="preserve">{_escape_xml(text)}</w:t></w:r></w:p></w:comment>'
    )
    comments_element.append(parse_xml(comment_xml))

    # Sync the lxml changes back to the Part's blob so doc.save() picks them up.
    comments_part._blob = etree.tostring(comments_element, xml_declaration=True, encoding="UTF-8", standalone=True)

    # Add comment reference markers around the first run
    run = paragraph.runs[0] if paragraph.runs else paragraph.add_run(" ")
    comment_ref_start = parse_xml(
        f'<w:commentRangeStart {nsdecls("w")} w:id="{comment_id}"/>'
    )
    comment_ref_end = parse_xml(
        f'<w:commentRangeEnd {nsdecls("w")} w:id="{comment_id}"/>'
    )
    comment_ref = parse_xml(
        f'<w:r {nsdecls("w")}><w:commentReference w:id="{comment_id}"/></w:r>'
    )

    run._r.addprevious(comment_ref_start)

    parent = run._r.getparent()
    parent.append(comment_ref_end)
    parent.append(comment_ref)


def _get_or_create_comments_part(doc):
    """Get or create the Word comments XML part.

    Returns ``(part, element)`` where *element* is the ``<w:comments>``
    lxml Element that callers can append children to.
    """
    part = doc.part

    for rel in part.rels.values():
        if "comments" in str(rel.reltype):
            tp = rel.target_part
            if tp._blob:
                return tp, etree.fromstring(tp._blob)
            return tp, etree.fromstring(f'<w:comments {nsdecls("w")}></w:comments>')

    # No comments relationship exists yet – create one.
    from docx.opc.part import Part
    from docx.opc.packuri import PackURI

    comments_xml = f'<w:comments {nsdecls("w")}></w:comments>'
    blob = comments_xml.encode("utf-8")
    comments_part = Part(
        PackURI("/word/comments.xml"),
        "application/vnd.openxmlformats-officedocument.wordprocessingml.comments+xml",
        blob,
        part.package,
    )
    part.relate_to(
        comments_part,
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships/comments",
    )
    return comments_part, etree.fromstring(blob)


_comment_counter = 0


def _next_comment_id() -> int:
    global _comment_counter
    _comment_counter += 1
    return _comment_counter


def _now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _escape_xml(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _set_rtl(paragraph) -> None:
    """为段落设置 RTL 双向方向（<w:bidi/>）。"""
    pPr = paragraph._p.get_or_add_pPr()
    pPr.append(parse_xml(f'<w:bidi {nsdecls("w")}/>'))


def generate_translation_docx(
    source_text: str,
    translated_text: str,
    risk_annotations: list[dict],
    language: str,
) -> bytes:
    """Generate a standard-format .docx with source text, translation, and risk annotations as Word comments.

    Returns the .docx content as bytes.
    """
    if not translated_text:
        raise ValueError("translated_text is required")

    doc = Document()

    # Set default font
    style = doc.styles["Normal"]
    font = style.font
    font.name = "Times New Roman"
    font.size = Pt(12)

    # --- Source text section ---
    doc.add_heading("【原文】", level=2)
    para = doc.add_paragraph(source_text)
    para.style = doc.styles["Normal"]

    # --- Separator ---
    doc.add_paragraph("─" * 40)

    # --- Translation section ---
    doc.add_heading("【译文】", level=2)
    para_tr = doc.add_paragraph(translated_text)
    para_tr.style = doc.styles["Normal"]

    # RTL 语言（阿拉伯语/乌尔都语）译文段落设双向方向
    lang_info = get_language(language)
    if lang_info is not None and lang_info.direction == "rtl":
        _set_rtl(para_tr)

    # --- Risk annotations as Word comments ---
    for ann in risk_annotations:
        phrase = ann.get("phrase", "")
        if not phrase or phrase not in translated_text:
            continue
        risk_level = ann.get("risk_level", "unknown")
        explanation = ann.get("explanation", "")
        risk_type = ann.get("risk_type", "")
        comment_text = f"[风险: {risk_level}]"
        if risk_type:
            comment_text += f" ({risk_type})"
        if explanation:
            comment_text += f"\n{explanation}"
        _add_comment(doc, para_tr, comment_text)

    buf = BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf.read()
