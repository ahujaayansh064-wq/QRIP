"""Export writers — .xlsx, .docx and .pdf produced with nothing but the stdlib.

OOXML files are zip containers of XML, so both spreadsheet and document exports
are written directly. The PDF writer emits a minimal but valid PDF 1.4 file.
"""
import io
import json
import zipfile
from datetime import datetime, timezone

# --- shared --------------------------------------------------------------


def esc(text) -> str:
    if text is None:
        return ""
    s = str(text)
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;"))


def _clean(text) -> str:
    """Strip characters OOXML rejects."""
    if text is None:
        return ""
    return "".join(ch for ch in str(text)
                   if ch in "\t\n\r" or 0x20 <= ord(ch) <= 0xD7FF or 0xE000 <= ord(ch) <= 0xFFFD)


# --- XLSX ----------------------------------------------------------------

def _col_name(idx: int) -> str:
    name = ""
    idx += 1
    while idx:
        idx, rem = divmod(idx - 1, 26)
        name = chr(65 + rem) + name
    return name


def _sheet_xml(rows) -> str:
    out = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
           '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">',
           '<sheetFormatPr defaultRowHeight="15"/><sheetData>']
    for r, row in enumerate(rows, start=1):
        out.append('<row r="' + str(r) + '">')
        for c, value in enumerate(row):
            ref = _col_name(c) + str(r)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                out.append('<c r="' + ref + '"><v>' + str(value) + '</v></c>')
            else:
                text = _clean(value)
                if not text:
                    continue
                out.append('<c r="' + ref + '" t="inlineStr"><is><t xml:space="preserve">'
                           + esc(text) + '</t></is></c>')
        out.append('</row>')
    out.append('</sheetData></worksheet>')
    return "".join(out)


def write_xlsx(sheets) -> bytes:
    """sheets: list of (name, rows) where rows is a list of lists."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        types = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
                 '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">',
                 '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>',
                 '<Default Extension="xml" ContentType="application/xml"/>',
                 '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>']
        for i in range(len(sheets)):
            types.append('<Override PartName="/xl/worksheets/sheet' + str(i + 1)
                         + '.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>')
        types.append('</Types>')
        z.writestr("[Content_Types].xml", "".join(types))
        z.writestr("_rels/.rels",
                   '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
                   '</Relationships>')
        wb = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
              '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"',
              ' xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>']
        rels = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">']
        for i, (name, rows) in enumerate(sheets, start=1):
            safe = esc(_clean(name))[:31] or ("Sheet" + str(i))
            wb.append('<sheet name="' + safe + '" sheetId="' + str(i) + '" r:id="rId'
                      + str(i) + '"/>')
            rels.append('<Relationship Id="rId' + str(i)
                        + '" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"'
                        ' Target="worksheets/sheet' + str(i) + '.xml"/>')
            z.writestr("xl/worksheets/sheet" + str(i) + ".xml", _sheet_xml(rows))
        wb.append('</sheets></workbook>')
        rels.append('</Relationships>')
        z.writestr("xl/workbook.xml", "".join(wb))
        z.writestr("xl/_rels/workbook.xml.rels", "".join(rels))
    return buf.getvalue()


# --- DOCX ----------------------------------------------------------------

STYLES_XML = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
    '<w:docDefaults><w:rPrDefault><w:rPr>'
    '<w:rFonts w:ascii="Georgia" w:hAnsi="Georgia"/><w:sz w:val="22"/>'
    '</w:rPr></w:rPrDefault></w:docDefaults>'
    '<w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:pPr>'
    '<w:spacing w:after="240"/></w:pPr><w:rPr><w:b/><w:sz w:val="52"/></w:rPr></w:style>'
    '<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:pPr>'
    '<w:spacing w:before="360" w:after="120"/></w:pPr>'
    '<w:rPr><w:b/><w:sz w:val="32"/><w:color w:val="2B4570"/></w:rPr></w:style>'
    '<w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/><w:pPr>'
    '<w:spacing w:before="240" w:after="80"/></w:pPr>'
    '<w:rPr><w:b/><w:sz w:val="26"/></w:rPr></w:style>'
    '<w:style w:type="paragraph" w:styleId="Quote"><w:name w:val="Quote"/><w:pPr>'
    '<w:ind w:left="480"/><w:spacing w:before="80" w:after="80"/></w:pPr>'
    '<w:rPr><w:i/><w:color w:val="4A4A55"/></w:rPr></w:style>'
    '<w:style w:type="paragraph" w:styleId="Meta"><w:name w:val="Meta"/>'
    '<w:rPr><w:color w:val="6B6D76"/><w:sz w:val="18"/></w:rPr></w:style>'
    '</w:styles>'
)


def p(text, style=None, bold=False):
    body = '<w:p>'
    if style:
        body += '<w:pPr><w:pStyle w:val="' + style + '"/></w:pPr>'
    runs = '<w:rPr><w:b/></w:rPr>' if bold else ''
    body += ('<w:r>' + runs + '<w:t xml:space="preserve">' + esc(_clean(text))
             + '</w:t></w:r></w:p>')
    return body


def write_docx(paragraphs) -> bytes:
    """paragraphs: list of (style_or_None, text) tuples."""
    doc = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
           '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">',
           '<w:body>']
    for style, text in paragraphs:
        doc.append(p(text, style))
    doc.append('<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
               '<w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440"/>'
               '</w:sectPr></w:body></w:document>')
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml",
                   '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                   '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                   '<Default Extension="xml" ContentType="application/xml"/>'
                   '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
                   '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
                   '</Types>')
        z.writestr("_rels/.rels",
                   '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
                   '</Relationships>')
        z.writestr("word/_rels/document.xml.rels",
                   '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
                   '</Relationships>')
        z.writestr("word/styles.xml", STYLES_XML)
        z.writestr("word/document.xml", "".join(doc))
    return buf.getvalue()


# --- PDF -----------------------------------------------------------------

PAGE_W, PAGE_H = 595.28, 841.89
MARGIN = 56.0


# The fonts are declared /WinAnsiEncoding, so these map to real glyphs rather
# than to ASCII lookalikes.
_WINANSI = {
    "‘": 0x91, "’": 0x92, "“": 0x93, "”": 0x94,
    "•": 0x95, "–": 0x96, "—": 0x97, "…": 0x85,
    "·": 0xB7, "×": 0xD7, "£": 0xA3, "€": 0x80,
    "é": 0xE9, "è": 0xE8, "ü": 0xFC, "ö": 0xF6,
    "ä": 0xE4, "á": 0xE1, "í": 0xED, "ó": 0xF3,
}
_ASCII_FALLBACK = {"→": "->", "←": "<-", "≥": ">=", "≤": "<="}


def _pdf_escape(text: str) -> str:
    out = []
    for ch in text:
        if ch in "()\\":
            out.append("\\" + ch)
        elif ord(ch) < 32:
            out.append(" ")
        elif ord(ch) < 128:
            out.append(ch)
        elif ch in _WINANSI:
            out.append(chr(_WINANSI[ch]))
        elif ch in _ASCII_FALLBACK:
            out.append(_ASCII_FALLBACK[ch])
        else:
            out.append("?")
    return "".join(out)


def _wrap(text, font_size, width, bold=False):
    # Helvetica average advance ~0.5 em; bold slightly wider.
    per_char = font_size * (0.55 if bold else 0.5)
    max_chars = max(int(width / per_char), 20)
    words = text.split()
    lines, current = [], ""
    for word in words:
        candidate = (current + " " + word).strip()
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                lines.append(current)
            while len(word) > max_chars:
                lines.append(word[:max_chars])
                word = word[max_chars:]
            current = word
    if current:
        lines.append(current)
    return lines or [""]


def write_pdf(blocks) -> bytes:
    """blocks: list of (kind, text) where kind is title|h1|h2|body|quote|meta."""
    spec = {
        "title": (20, "F2", 26, 10),
        "h1": (14, "F2", 19, 16),
        "h2": (11.5, "F2", 16, 10),
        "body": (10, "F1", 14, 5),
        "quote": (9.5, "F3", 13.5, 6),
        "meta": (8.5, "F1", 12, 4),
    }
    pages, lines = [], []
    y = PAGE_H - MARGIN
    for kind, text in blocks:
        size, font, leading, gap = spec.get(kind, spec["body"])
        indent = 18.0 if kind == "quote" else 0.0
        for line in _wrap(str(text), size, PAGE_W - 2 * MARGIN - indent, font == "F2"):
            if y - leading < MARGIN:
                pages.append(lines)
                lines, y = [], PAGE_H - MARGIN
            y -= leading
            lines.append((MARGIN + indent, y, size, font, line))
        y -= gap
    pages.append(lines)

    objects = []       # 1-indexed content, filled below

    def add(body: bytes) -> int:
        objects.append(body)
        return len(objects)

    font_regular = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
    font_bold = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>")
    font_italic = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Oblique /Encoding /WinAnsiEncoding >>")

    pages_obj_id = add(b"")   # placeholder, patched after pages exist
    page_ids = []
    for page_lines in pages:
        stream_parts = ["BT"]
        current_font = None
        for x, y_pos, size, font, text in page_lines:
            key = (font, size)
            if key != current_font:
                stream_parts.append("/" + font + " " + str(size) + " Tf")
                current_font = key
            stream_parts.append("1 0 0 1 " + str(round(x, 2)) + " " + str(round(y_pos, 2)) + " Tm")
            stream_parts.append("(" + _pdf_escape(text) + ") Tj")
        stream_parts.append("ET")
        stream = "\n".join(stream_parts).encode("latin-1", "replace")
        content_id = add(b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n"
                         + stream + b"\nendstream")
        page_id = add(
            ("<< /Type /Page /Parent " + str(pages_obj_id) + " 0 R /MediaBox [0 0 "
             + str(PAGE_W) + " " + str(PAGE_H) + "] /Resources << /Font << /F1 "
             + str(font_regular) + " 0 R /F2 " + str(font_bold) + " 0 R /F3 "
             + str(font_italic) + " 0 R >> >> /Contents " + str(content_id)
             + " 0 R >>").encode()
        )
        page_ids.append(page_id)

    kids = " ".join(str(pid) + " 0 R" for pid in page_ids)
    objects[pages_obj_id - 1] = ("<< /Type /Pages /Count " + str(len(page_ids))
                                 + " /Kids [" + kids + "] >>").encode()
    catalog_id = add(("<< /Type /Catalog /Pages " + str(pages_obj_id) + " 0 R >>").encode())
    stamp = datetime.now(timezone.utc).strftime("D:%Y%m%d%H%M%SZ")
    info_id = add(("<< /Producer (QRIP) /Title (QRIP analysis report) /CreationDate ("
                   + stamp + ") >>").encode())

    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for i, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += str(i).encode() + b" 0 obj\n" + body + b"\nendobj\n"
    xref_pos = len(out)
    out += b"xref\n0 " + str(len(objects) + 1).encode() + b"\n"
    out += b"0000000000 65535 f \n"
    for off in offsets[1:]:
        out += ("%010d 00000 n \n" % off).encode()
    out += (b"trailer\n<< /Size " + str(len(objects) + 1).encode() + b" /Root "
            + str(catalog_id).encode() + b" 0 R /Info " + str(info_id).encode()
            + b" 0 R >>\nstartxref\n" + str(xref_pos).encode() + b"\n%%EOF\n")
    return bytes(out)


# --- project export builders ---------------------------------------------

def project_workbook(project, themes, codes, contradictions, comparisons, audit, methods,
                     workbench=None):
    sheets = []
    sheets.append(("Project", [
        ["QRIP project export"],
        ["Name", project["name"]],
        ["Research question", project["research_question"] or ""],
        ["Methodology", project["methodology"] or ""],
        ["Description", project["description"] or ""],
        [],
        ["Controls"],
        ["Similarity threshold", project["similarity_threshold"]],
        ["Confidence threshold", project["confidence_threshold"]],
        ["Min supporting quotations", project["min_supporting_quotations"]],
        ["Participant frequency threshold", project["participant_frequency_threshold"]],
        ["Coding granularity", project["coding_granularity"]],
        ["Contradiction sensitivity", project["contradiction_sensitivity"]],
        [],
        ["Exported at", datetime.now(timezone.utc).isoformat(timespec="seconds")],
    ]))

    theme_rows = [["Theme", "Status", "Confidence", "Coverage", "Participants",
                   "Quotes", "Description", "Alternative interpretation"]]
    for t in themes:
        theme_rows.append([t["name"], t["status"], t["confidence"], t["coverage"],
                           t["participant_count"], t["quote_count"], t["description"] or "",
                           t["alternative_interpretation"] or ""])
    sheets.append(("Themes", theme_rows))

    code_rows = [["Code", "Theme", "Participant", "Emotion", "Intent", "Valence",
                  "Confidence", "Negative case", "Quote", "Literal meaning",
                  "Alternative interpretations"]]
    theme_names = {t["id"]: t["name"] for t in themes}
    for c in codes:
        code_rows.append([
            c["label"], theme_names.get(c["theme_id"], ""), c["participant_label"],
            c["emotion"], c["intent"], c["valence"], c["confidence"],
            "yes" if c["is_negative_case"] else "", c["quote_text"], c["literal_meaning"] or "",
            " | ".join(json.loads(c["alternative_interpretations"] or "[]")),
        ])
    sheets.append(("Codebook", code_rows))

    contra_rows = [["Theme", "Severity", "Description"]]
    for c in contradictions:
        contra_rows.append([theme_names.get(c["theme_id"], ""), c["severity"], c["description"]])
    sheets.append(("Contradictions", contra_rows))

    cmp_rows = [["Theme", "Primary model", "Secondary model", "Agreement", "Notes"]]
    for c in comparisons:
        cmp_rows.append([theme_names.get(c["theme_id"], ""), c["primary_model"],
                         c["secondary_model"], "yes" if c["agreement"] else "no",
                         c["disagreement_notes"] or ""])
    sheets.append(("Model comparison", cmp_rows))

    framework_payload = methods.get("framework")
    if framework_payload:
        matrix = framework_payload["matrix"]
        rows = [["Participant"] + matrix["columns"]]
        for row in matrix["rows"]:
            rows.append([row["participant"]] + [cell["summary"] for cell in row["cells"]])
        sheets.append(("Framework matrix", rows))

    content_payload = methods.get("content")
    if content_payload:
        matrix = content_payload["matrix"]
        rows = [["Participant"] + matrix["columns"] + ["Total"]]
        for row in matrix["rows"]:
            rows.append([row["participant"]] + row["counts"] + [row["total"]])
        sheets.append(("Content counts", rows))

    bench = workbench or {}

    codebook_rows = [["Code", "Colour", "Groundedness", "Density", "Cases", "Groups",
                      "Created by", "Definition"]]
    for entry in bench.get("codebook", []):
        codebook_rows.append([
            entry["name"], entry["color"], entry["groundedness"], entry["density"],
            entry["participants"], ", ".join(entry.get("groups") or []),
            entry["created_by"], entry.get("definition") or "",
        ])
    if len(codebook_rows) > 1:
        sheets.append(("Codebook", codebook_rows))

    quotation_rows = [["Participant", "Document", "Start", "End", "Created by",
                       "Codes", "Comment", "Quotation"]]
    documents = {doc["id"]: doc for doc in bench.get("documents", [])}
    for quotation in bench.get("quotations", []):
        document = documents.get(quotation["document_id"], {})
        quotation_rows.append([
            document.get("participant_label", ""), document.get("filename", ""),
            quotation["start_offset"], quotation["end_offset"], quotation["created_by"],
            " | ".join(code["label"] for code in quotation["codes"]),
            quotation.get("comment") or "", quotation["text"],
        ])
    if len(quotation_rows) > 1:
        sheets.append(("Quotations", quotation_rows))

    memo_rows = [["Title", "Kind", "Updated", "Attached to", "Memo"]]
    for memo in bench.get("memos", []):
        memo_rows.append([memo["title"], memo["kind"], memo["updated_at"],
                          ", ".join(link["type"] + ":" + link["id"]
                                    for link in memo.get("links") or []),
                          memo["body"]])
    if len(memo_rows) > 1:
        sheets.append(("Memos", memo_rows))

    link_rows = [["From", "Relation", "To", "Comment"]]
    for link in bench.get("links", []):
        link_rows.append([link.get("source_label", ""), link["relation"],
                          link.get("target_label", ""), link.get("comment") or ""])
    if len(link_rows) > 1:
        sheets.append(("Relations", link_rows))

    audit_rows = [["When", "Action", "Entity", "Entity id", "Details"]]
    for a in audit:
        audit_rows.append([a["created_at"], a["action"], a["entity_type"],
                           a["entity_id"] or "", a["details"]])
    sheets.append(("Audit log", audit_rows))
    return write_xlsx(sheets)


def report_blocks(project, themes, codes, contradictions, comparisons, methods,
                  dashboard, workbench=None):
    """Shared narrative structure for the .docx and .pdf reports."""
    blocks = [
        ("title", project["name"]),
        ("meta", "QRIP — Qualitative Research Intelligence Platform · generated "
                 + datetime.now(timezone.utc).strftime("%d %b %Y %H:%M UTC")),
    ]
    if project["research_question"]:
        blocks.append(("body", "Research question: " + project["research_question"]))
    if project["description"]:
        blocks.append(("body", project["description"]))

    blocks.append(("h1", "Corpus and method"))
    blocks.append(("body",
                   str(dashboard["interview_count"]) + " transcripts were segmented into "
                   + str(dashboard["meaning_unit_count"]) + " meaning units and coded into "
                   + str(dashboard["code_count"]) + " codes, clustered into "
                   + str(dashboard["theme_count"]) + " themes. Mean coding confidence was "
                   + str(round(dashboard["average_confidence"], 3)) + ". "
                   + str(dashboard["contradiction_count"]) + " contradictions were flagged."))
    blocks.append(("body", "Controls: similarity threshold "
                   + str(project["similarity_threshold"]) + ", confidence threshold "
                   + str(project["confidence_threshold"]) + ", minimum "
                   + str(project["min_supporting_quotations"]) + " supporting quotations, "
                   + str(project["participant_frequency_threshold"])
                   + " participant minimum, " + str(project["coding_granularity"])
                   + "-level coding."))

    bench = workbench or {}
    hand = [q for q in bench.get("quotations", []) if q["created_by"] == "user"]
    if bench.get("quotations"):
        blocks.append(("body",
                       str(len(bench["quotations"])) + " quotations are held in the project, "
                       + str(len(hand)) + " of them created by hand. The codebook holds "
                       + str(len(bench.get("codebook", []))) + " codes, "
                       + str(sum(1 for c in bench.get("codebook", [])
                                 if c["created_by"] == "user"))
                       + " of which the researcher added."))

    if bench.get("memos"):
        blocks.append(("h1", "Memos"))
        for memo in bench["memos"]:
            blocks.append(("h2", memo["title"] + "  (" + memo["kind"] + ")"))
            blocks.append(("body", memo["body"] or ""))

    blocks.append(("h1", "Themes"))
    theme_codes = {}
    for c in codes:
        theme_codes.setdefault(c["theme_id"], []).append(c)
    for t in themes:
        blocks.append(("h2", t["name"] + "  (" + t["status"] + ")"))
        blocks.append(("meta", "Confidence " + str(t["confidence"]) + " · coverage "
                       + str(round(t["coverage"] * 100, 1)) + "% · "
                       + str(t["participant_count"]) + " participants · "
                       + str(t["quote_count"]) + " quotations"))
        if t["description"]:
            blocks.append(("body", t["description"]))
        for c in sorted(theme_codes.get(t["id"], []),
                        key=lambda c: -c["confidence"])[:3]:
            blocks.append(("quote", "“" + c["quote_text"] + "” — "
                           + c["participant_label"]))
        if t["alternative_interpretation"]:
            blocks.append(("body", "Alternative reading: " + t["alternative_interpretation"]))

    if contradictions:
        blocks.append(("h1", "Contradictions and tensions"))
        names = {t["id"]: t["name"] for t in themes}
        for c in contradictions[:12]:
            blocks.append(("h2", names.get(c["theme_id"], "Across themes")
                           + " · severity " + str(c["severity"])))
            blocks.append(("body", c["description"]))

    for key, title in (("thematic", "Thematic analysis"),
                       ("grounded_theory", "Grounded theory"),
                       ("ipa", "Interpretative phenomenological analysis"),
                       ("framework", "Framework analysis"),
                       ("narrative", "Narrative analysis"),
                       ("content", "Content analysis")):
        payload = methods.get(key)
        if not payload:
            continue
        blocks.append(("h1", title))
        blocks.append(("meta", payload.get("framework", "")))
        blocks.extend(_method_blocks(key, payload))

    if comparisons:
        blocks.append(("h1", "Second-pass agreement"))
        names = {t["id"]: t["name"] for t in themes}
        for c in comparisons:
            state = "agreement" if c["agreement"] else "divergence"
            blocks.append(("body", names.get(c["theme_id"], "?") + " — " + state
                           + (": " + c["disagreement_notes"] if c["disagreement_notes"] else "")))

    blocks.append(("h1", "Reflexive note"))
    blocks.append(("body",
                   "Every theme in this report is one defensible reading of the corpus, not "
                   "the only one. Alternative interpretations, counter-cases and unstable "
                   "theme boundaries are recorded above so that a reader can disagree with "
                   "the analysis on the evidence rather than on trust."))
    return blocks


def _method_blocks(key, payload):
    out = []
    if key == "thematic":
        for phase in payload["phases"]:
            out.append(("body", "Phase " + str(phase["phase"]) + " — " + phase["name"]
                        + ": " + phase["output"]))
    elif key == "grounded_theory":
        sel = payload["selective_coding"]
        out.append(("h2", "Core category: " + str(sel.get("core_category"))))
        out.append(("body", sel["storyline"]))
        out.append(("body", payload["saturation"]["verdict"]))
        for cat in payload["axial_categories"][:4]:
            out.append(("h2", "Axial category: " + cat["name"]))
            for slot_key, slot in cat["paradigm"].items():
                if slot["evidence"]:
                    out.append(("body", slot["label"] + ": "
                                + slot["evidence"][0]["quote"] + " — "
                                + slot["evidence"][0]["participant"]))
        for memo in payload["memos"]:
            out.append(("h2", memo["title"]))
            out.append(("body", memo["text"]))
    elif key == "ipa":
        for get in payload["group_experiential_themes"][:5]:
            out.append(("h2", "GET: " + get["name"]))
            out.append(("meta", "Convergence " + str(get["convergence"]) + " · present in "
                        + ", ".join(get["present_in"])))
            for ex in get["exemplars"][:2]:
                out.append(("quote", "“" + ex["quote"] + "” — " + ex["participant"]))
            for note in get["divergence"]:
                out.append(("body", note))
        for case in payload["cases"]:
            out.append(("h2", "Case: " + case["participant"]))
            out.append(("body", case["idiographic_summary"]))
    elif key == "framework":
        for stage in payload["stages"]:
            out.append(("body", "Stage " + str(stage["stage"]) + " — " + stage["name"]
                        + ": " + stage["output"]))
        for m in payload["mapping"][:8]:
            out.append(("body", m["category"] + ": " + m["pattern"]))
    elif key == "narrative":
        out.append(("body", payload["cross_narrative"]["note"]))
        for n in payload["narratives"]:
            out.append(("h2", n["participant"] + " — " + n["plot_type"]["type"] + " arc"))
            out.append(("body", n["summary"]))
    elif key == "content":
        m = payload["manifest"]
        out.append(("body", str(m["total_words"]) + " words, " + str(m["unique_terms"])
                    + " unique content terms, type-token ratio "
                    + str(m["type_token_ratio"]) + "."))
        for lat in payload["latent"][:8]:
            out.append(("body", lat["category"] + ": " + lat["interpretation"]))
        out.append(("body", payload["reliability"]["note"]))
    return out
