"""Minimal .xlsx reader.

Counterpart to the writer in exports.py. Enough of SpreadsheetML to read a
sheet into rows of strings, which is all the Outscraper import needs. Cells are
placed by their column reference, so blank cells keep the columns aligned —
skipping them silently shifts every value left, which is the classic way to read
a spreadsheet wrong.
"""
import re
import zipfile
from xml.etree import ElementTree

MAIN = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"


def column_index(reference):
    letters = re.match(r"([A-Za-z]+)", reference or "")
    if not letters:
        return 0
    index = 0
    for character in letters.group(1).upper():
        index = index * 26 + (ord(character) - 64)
    return index - 1


def _shared_strings(archive):
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
    out = []
    for item in root.iter(MAIN + "si"):
        out.append("".join(node.text or "" for node in item.iter(MAIN + "t")))
    return out


def sheet_names(archive):
    book = ElementTree.fromstring(archive.read("xl/workbook.xml"))
    rels = ElementTree.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    targets = {rel.get("Id"): rel.get("Target") for rel in rels}
    out = []
    for index, sheet in enumerate(book.iter(MAIN + "sheet"), start=1):
        target = targets.get(sheet.get(REL + "id")) or ("worksheets/sheet%d.xml" % index)
        if not target.startswith("xl/"):
            target = "xl/" + target.lstrip("/")
        out.append((sheet.get("name") or ("Sheet%d" % index), target))
    return out


def read_sheet(data, sheet=0):
    """Return a sheet as a list of rows, each a list of strings."""
    with zipfile.ZipFile(data if hasattr(data, "read") else _as_file(data)) as archive:
        shared = _shared_strings(archive)
        sheets = sheet_names(archive)
        if not sheets:
            return []
        if isinstance(sheet, str):
            match = [path for name, path in sheets if name == sheet]
            path = match[0] if match else sheets[0][1]
        else:
            path = sheets[min(sheet, len(sheets) - 1)][1]
        if path not in archive.namelist():
            return []
        root = ElementTree.fromstring(archive.read(path))

        rows = []
        for row in root.iter(MAIN + "row"):
            cells = {}
            for cell in row:
                position = column_index(cell.get("r"))
                kind = cell.get("t")
                text = "".join(node.text or "" for node in cell.iter(MAIN + "t"))
                if not text:
                    value = cell.findtext(MAIN + "v") or ""
                    if kind == "s":
                        try:
                            text = shared[int(value)]
                        except (ValueError, IndexError):
                            text = value
                    else:
                        text = value
                cells[position] = text
            if cells:
                width = max(cells) + 1
                rows.append([cells.get(i, "") for i in range(width)])
        return rows


def _as_file(data):
    import io
    if isinstance(data, bytes):
        return io.BytesIO(data)
    return data


def read_records(data, sheet=0):
    """Read a sheet as dicts keyed by the header row."""
    rows = read_sheet(data, sheet)
    if not rows:
        return []
    header = [str(cell).strip() for cell in rows[0]]
    out = []
    for row in rows[1:]:
        if not any(str(cell).strip() for cell in row):
            continue
        record = {}
        for index, name in enumerate(header):
            if not name:
                continue
            record[name] = row[index] if index < len(row) else ""
        out.append(record)
    return out
