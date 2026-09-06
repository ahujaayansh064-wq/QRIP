"""A small vector PDF writer.

Enough of PDF 1.4 to typeset an executive report with real charts: flowed text,
rules, filled shapes, polygons and arc segments, across automatically broken
pages. No dependencies, because the rest of this project has none.
"""
import math
from datetime import datetime, timezone

A4 = (595.28, 841.89)

FONTS = [
    ("F1", "Helvetica"),
    ("F2", "Helvetica-Bold"),
    ("F3", "Helvetica-Oblique"),
    ("F4", "Times-Roman"),
    ("F5", "Times-Bold"),
]
BOLD_FONTS = {"F2", "F5"}

# Approximate advance widths as a fraction of font size. Helvetica metrics
# rounded into three buckets — accurate enough for wrapping and centring.
_NARROW = set("iljtfr.,;:'|!()[]{} ")
_WIDE = set("mwMW@%")


def text_width(text, size, font="F1"):
    total = 0.0
    for character in str(text):
        if character in _NARROW:
            total += 0.30
        elif character in _WIDE:
            total += 0.86
        elif character.isupper() or character.isdigit():
            total += 0.62
        else:
            total += 0.52
    if font in BOLD_FONTS:
        total *= 1.06
    return total * size


def wrap(text, size, width, font="F1"):
    words = str(text).split()
    lines, current = [], ""
    for word in words:
        candidate = (current + " " + word).strip()
        if text_width(candidate, size, font) <= width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [""]


def hex_rgb(value):
    """'#2B4570' -> (0.169, 0.271, 0.439)"""
    if isinstance(value, (tuple, list)):
        return tuple(value)
    text = str(value).lstrip("#")
    if len(text) == 3:
        text = "".join(character * 2 for character in text)
    return tuple(int(text[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def escape(text):
    out = []
    replacements = {
        "‘": "", "’": "", "“": "", "”": "",
        "•": "", "–": "", "—": "", "…": "",
        "·": "·", "×": "×", "→": "->", "≥": ">=",
        "≤": "<=", "£": "£", "€": "",
    }
    for character in str(text):
        if character in "()\\":
            out.append("\\" + character)
        elif ord(character) < 32:
            out.append(" ")
        elif ord(character) < 128:
            out.append(character)
        elif character in replacements:
            out.append(replacements[character])
        elif ord(character) < 256:
            out.append(character)
        else:
            out.append("?")
    return "".join(out)


class Document:
    def __init__(self, size=A4, margin=46.0):
        self.width, self.height = size
        self.margin = margin
        self.pages = []
        self.ops = []
        self.y = self.height - margin
        self._footer = None
        self.new_page()

    # --- pages ------------------------------------------------------------

    def new_page(self):
        if self.ops:
            self.pages.append(self.ops)
        self.ops = []
        self.y = self.height - self.margin
        if self._footer:
            self._footer(self)

    def set_footer(self, callback):
        self._footer = callback

    @property
    def content_width(self):
        return self.width - 2 * self.margin

    def ensure(self, space):
        if self.y - space < self.margin + 26:
            self.new_page()
            return True
        return False

    def space(self, amount):
        self.y -= amount

    # --- primitives -------------------------------------------------------

    def _colour(self, colour, stroke=False):
        r, g, b = hex_rgb(colour)
        op = "RG" if stroke else "rg"
        self.ops.append("%.4f %.4f %.4f %s" % (r, g, b, op))

    def text(self, x, y, value, size=9.5, font="F1", colour="#1C1D21", align="left",
             width=None):
        if value is None or value == "":
            return
        if align in ("center", "right") and width:
            measured = text_width(value, size, font)
            if align == "center":
                x = x + (width - measured) / 2
            else:
                x = x + width - measured
        self._colour(colour)
        self.ops.append("BT /%s %.2f Tf 1 0 0 1 %.2f %.2f Tm (%s) Tj ET"
                        % (font, size, x, y, escape(value)))

    def rect(self, x, y, w, h, fill=None, stroke=None, line_width=0.7, radius=0):
        if fill:
            self._colour(fill)
        if stroke:
            self._colour(stroke, stroke=True)
            self.ops.append("%.2f w" % line_width)
        if radius > 0:
            self._rounded_path(x, y, w, h, radius)
        else:
            self.ops.append("%.2f %.2f %.2f %.2f re" % (x, y, w, h))
        self.ops.append("B" if (fill and stroke) else ("f" if fill else "S"))

    def _rounded_path(self, x, y, w, h, r):
        k = 0.5523 * r
        self.ops.append("%.2f %.2f m" % (x + r, y))
        self.ops.append("%.2f %.2f l" % (x + w - r, y))
        self.ops.append("%.2f %.2f %.2f %.2f %.2f %.2f c"
                        % (x + w - r + k, y, x + w, y + r - k, x + w, y + r))
        self.ops.append("%.2f %.2f l" % (x + w, y + h - r))
        self.ops.append("%.2f %.2f %.2f %.2f %.2f %.2f c"
                        % (x + w, y + h - r + k, x + w - r + k, y + h, x + w - r, y + h))
        self.ops.append("%.2f %.2f l" % (x + r, y + h))
        self.ops.append("%.2f %.2f %.2f %.2f %.2f %.2f c"
                        % (x + r - k, y + h, x, y + h - r + k, x, y + h - r))
        self.ops.append("%.2f %.2f l" % (x, y + r))
        self.ops.append("%.2f %.2f %.2f %.2f %.2f %.2f c"
                        % (x, y + r - k, x + r - k, y, x + r, y))
        self.ops.append("h")

    def line(self, x1, y1, x2, y2, colour="#E4E1D8", width=0.7, dash=None):
        self._colour(colour, stroke=True)
        self.ops.append("%.2f w" % width)
        if dash:
            self.ops.append("[%s] 0 d" % dash)
        self.ops.append("%.2f %.2f m %.2f %.2f l S" % (x1, y1, x2, y2))
        if dash:
            self.ops.append("[] 0 d")

    def polygon(self, points, fill=None, stroke=None, width=0.8, close=True):
        if len(points) < 2:
            return
        if fill:
            self._colour(fill)
        if stroke:
            self._colour(stroke, stroke=True)
            self.ops.append("%.2f w" % width)
        self.ops.append("%.2f %.2f m" % points[0])
        for point in points[1:]:
            self.ops.append("%.2f %.2f l" % point)
        if close:
            self.ops.append("h")
        self.ops.append("B" if (fill and stroke) else ("f" if fill else "S"))

    def circle(self, cx, cy, r, fill=None, stroke=None, width=0.8):
        k = 0.5523 * r
        if fill:
            self._colour(fill)
        if stroke:
            self._colour(stroke, stroke=True)
            self.ops.append("%.2f w" % width)
        self.ops.append("%.2f %.2f m" % (cx - r, cy))
        self.ops.append("%.2f %.2f %.2f %.2f %.2f %.2f c"
                        % (cx - r, cy + k, cx - k, cy + r, cx, cy + r))
        self.ops.append("%.2f %.2f %.2f %.2f %.2f %.2f c"
                        % (cx + k, cy + r, cx + r, cy + k, cx + r, cy))
        self.ops.append("%.2f %.2f %.2f %.2f %.2f %.2f c"
                        % (cx + r, cy - k, cx + k, cy - r, cx, cy - r))
        self.ops.append("%.2f %.2f %.2f %.2f %.2f %.2f c"
                        % (cx - k, cy - r, cx - r, cy - k, cx - r, cy))
        self.ops.append("B" if (fill and stroke) else ("f" if fill else "S"))

    def ring_segment(self, cx, cy, outer, inner, start_deg, end_deg, colour):
        """A donut slice, approximated with short segments."""
        steps = max(4, int(abs(end_deg - start_deg) / 3) + 2)
        points = []
        for index in range(steps + 1):
            angle = math.radians(start_deg + (end_deg - start_deg) * index / steps)
            points.append((cx + math.cos(angle) * outer, cy + math.sin(angle) * outer))
        for index in range(steps, -1, -1):
            angle = math.radians(start_deg + (end_deg - start_deg) * index / steps)
            points.append((cx + math.cos(angle) * inner, cy + math.sin(angle) * inner))
        self.polygon(points, fill=colour)

    # --- flowed content ---------------------------------------------------

    def heading(self, text, size=15, colour="#1C1D21", font="F5", gap_before=16,
                gap_after=8, rule=False):
        self.ensure(size + gap_before + gap_after + 18)
        self.y -= gap_before
        self.text(self.margin, self.y - size, text, size=size, font=font, colour=colour)
        self.y -= size + gap_after
        if rule:
            self.line(self.margin, self.y + 3, self.width - self.margin, self.y + 3)
            self.y -= 6

    def eyebrow(self, text, colour="#6B6D76"):
        self.ensure(18)
        self.text(self.margin, self.y - 8, str(text).upper(), size=7.4, font="F2",
                  colour=colour)
        self.y -= 15

    def paragraph(self, text, size=9.4, leading=13.2, colour="#1C1D21", font="F1",
                  gap=7, indent=0, width=None):
        available = (width or self.content_width) - indent
        for line in wrap(text, size, available, font):
            self.ensure(leading + 4)
            self.text(self.margin + indent, self.y - size, line, size=size, font=font,
                      colour=colour)
            self.y -= leading
        self.y -= gap

    def bullets(self, items, size=9.4, leading=13.0, colour="#1C1D21"):
        for item in items:
            self.ensure(leading + 6)
            self.text(self.margin + 2, self.y - size, "•", size=size, colour="#2B4570")
            for index, line in enumerate(wrap(item, size, self.content_width - 16)):
                if index:
                    self.ensure(leading + 2)
                self.text(self.margin + 14, self.y - size, line, size=size, colour=colour)
                self.y -= leading
            self.y -= 2
        self.y -= 5

    def quote(self, text, attribution=None, colour="#4A4B53"):
        lines = wrap(text, 9.2, self.content_width - 26, "F3")
        self.ensure(len(lines) * 12.6 + 20)
        top = self.y
        for line in lines:
            self.text(self.margin + 16, self.y - 9.2, line, size=9.2, font="F3", colour=colour)
            self.y -= 12.6
        if attribution:
            self.text(self.margin + 16, self.y - 8, attribution, size=7.8, colour="#6B6D76")
            self.y -= 12
        self.line(self.margin + 4, top - 1, self.margin + 4, self.y + 4,
                  colour="#E4E1D8", width=1.6)
        self.y -= 6

    def table(self, columns, rows, widths, header_fill="#F4F2EC", row_height=None,
              size=8.4, align=None):
        """columns: list of headers. rows: list of lists of strings."""
        align = align or ["left"] * len(columns)
        total = sum(widths)
        scale = self.content_width / total if total else 1
        widths = [width * scale for width in widths]

        def draw_header():
            self.ensure(26)
            self.rect(self.margin, self.y - 16, self.content_width, 16, fill=header_fill)
            x = self.margin
            for index, column in enumerate(columns):
                self.text(x + 4, self.y - 11.5, str(column).upper(), size=6.8, font="F2",
                          colour="#6B6D76", align=align[index], width=widths[index] - 8)
                x += widths[index]
            self.y -= 16

        draw_header()
        for row in rows:
            cell_lines = []
            for index, cell in enumerate(row):
                cell_lines.append(wrap(cell if cell is not None else "", size,
                                       widths[index] - 8))
            height = row_height or (max(len(lines) for lines in cell_lines) * (size + 3.2) + 6)
            if self.y - height < self.margin + 26:
                self.new_page()
                draw_header()
            x = self.margin
            for index, lines in enumerate(cell_lines):
                offset = self.y - size - 3
                for line in lines:
                    self.text(x + 4, offset, line, size=size,
                              align=align[index], width=widths[index] - 8)
                    offset -= size + 3.2
                x += widths[index]
            self.y -= height
            self.line(self.margin, self.y, self.width - self.margin, self.y)
        self.y -= 8

    # --- output -----------------------------------------------------------

    def render(self, title="QRIP report"):
        if self.ops:
            self.pages.append(self.ops)
            self.ops = []
        objects = []

        def add(body):
            objects.append(body)
            return len(objects)

        font_ids = {}
        for name, base in FONTS:
            font_ids[name] = add(("<< /Type /Font /Subtype /Type1 /BaseFont /" + base
                                  + " /Encoding /WinAnsiEncoding >>").encode())
        pages_id = add(b"")
        resources = "<< /Font << " + " ".join(
            "/" + name + " " + str(font_ids[name]) + " 0 R" for name, _ in FONTS) + " >> >>"

        page_ids = []
        for ops in self.pages:
            stream = "\n".join(ops).encode("latin-1", "replace")
            content_id = add(b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n"
                             + stream + b"\nendstream")
            page_ids.append(add(
                ("<< /Type /Page /Parent " + str(pages_id) + " 0 R /MediaBox [0 0 "
                 + ("%.2f %.2f" % (self.width, self.height)) + "] /Resources " + resources
                 + " /Contents " + str(content_id) + " 0 R >>").encode()))

        objects[pages_id - 1] = (
            "<< /Type /Pages /Count " + str(len(page_ids)) + " /Kids ["
            + " ".join(str(pid) + " 0 R" for pid in page_ids) + "] >>").encode()
        catalog_id = add(("<< /Type /Catalog /Pages " + str(pages_id) + " 0 R >>").encode())
        stamp = datetime.now(timezone.utc).strftime("D:%Y%m%d%H%M%SZ")
        info_id = add(("<< /Producer (QRIP) /Title (" + escape(title)
                       + ") /CreationDate (" + stamp + ") >>").encode())

        out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        offsets = [0]
        for index, body in enumerate(objects, start=1):
            offsets.append(len(out))
            out += str(index).encode() + b" 0 obj\n" + body + b"\nendobj\n"
        xref = len(out)
        out += b"xref\n0 " + str(len(objects) + 1).encode() + b"\n0000000000 65535 f \n"
        for offset in offsets[1:]:
            out += ("%010d 00000 n \n" % offset).encode()
        out += (b"trailer\n<< /Size " + str(len(objects) + 1).encode() + b" /Root "
                + str(catalog_id).encode() + b" 0 R /Info " + str(info_id).encode()
                + b" 0 R >>\nstartxref\n" + str(xref).encode() + b"\n%%EOF\n")
        return bytes(out)


# --- charts ---------------------------------------------------------------

def donut(doc, cx, cy, radius, segments, thickness=26, centre_label=None,
          centre_sub=None):
    """segments: [(label, value, colour)]"""
    total = sum(max(value, 0) for _, value, _ in segments) or 1
    angle = 90.0
    for label, value, colour in segments:
        if value <= 0:
            continue
        sweep = 360.0 * value / total
        doc.ring_segment(cx, cy, radius, radius - thickness, angle - sweep, angle, colour)
        angle -= sweep
    if centre_label:
        doc.text(cx - text_width(centre_label, 19, "F5") / 2, cy - 4, centre_label,
                 size=19, font="F5")
    if centre_sub:
        doc.text(cx - text_width(centre_sub, 7, "F1") / 2, cy - 16, centre_sub,
                 size=7, colour="#6B6D76")


def donut_legend(doc, x, y, segments, line_height=15):
    total = sum(max(value, 0) for _, value, _ in segments) or 1
    for label, value, colour in segments:
        doc.rect(x, y - 7, 8, 8, fill=colour, radius=1.5)
        share = int(round(100.0 * value / total))
        doc.text(x + 14, y - 6.5, label, size=8.6)
        doc.text(x + 14, y - 6.5, str(value) + "  (" + str(share) + "%)", size=8.6,
                 colour="#6B6D76", align="right", width=170)
        y -= line_height
    return y


def grouped_bars(doc, x, y, width, height, groups, series, gap=10):
    """groups: [label]. series: [(name, colour, [values...])]"""
    maximum = max([value for _, _, values in series for value in values] + [1])
    steps = 4
    for step in range(steps + 1):
        level = y + height * step / steps
        doc.line(x, level, x + width, level, colour="#EDEBE4", width=0.6)
        doc.text(x - 22, level - 3, str(int(round(maximum * step / steps))), size=7,
                 colour="#6B6D76", align="right", width=18)
    group_width = width / max(len(groups), 1)
    bar_width = (group_width - gap) / max(len(series), 1)
    for index, label in enumerate(groups):
        base = x + index * group_width
        for series_index, (_, colour, values) in enumerate(series):
            value = values[index] if index < len(values) else 0
            bar_height = (value / maximum) * height if maximum else 0
            bx = base + gap / 2 + series_index * bar_width
            if bar_height > 0:
                doc.rect(bx, y, bar_width - 2, bar_height, fill=colour, radius=1.5)
                doc.text(bx, y + bar_height + 3, str(value), size=6.8, colour="#6B6D76",
                         align="center", width=bar_width - 2)
        doc.text(base, y - 11, label, size=7.4, colour="#6B6D76", align="center",
                 width=group_width)
    doc.line(x, y, x + width, y, colour="#C9C5B8", width=0.8)
    legend_x = x
    for name, colour, _ in series:
        doc.rect(legend_x, y - 26, 8, 8, fill=colour, radius=1.5)
        doc.text(legend_x + 12, y - 25.5, name, size=7.8)
        legend_x += text_width(name, 7.8) + 30


def line_chart(doc, x, y, width, height, points, labels, low=-1.0, high=1.0,
               colour="#2B4570", zero_line=True):
    """A single series across evenly spaced periods, oldest on the left."""
    if len(points) < 2:
        doc.text(x, y + height / 2, "Not enough dated reviews to plot a trend.",
                 size=8.5, colour="#6B6D76")
        return
    span = (high - low) or 1.0

    def plot_y(value):
        return y + (max(low, min(high, value)) - low) / span * height

    for step in range(5):
        level = y + height * step / 4
        doc.line(x, level, x + width, level, colour="#EDEBE4", width=0.5)
        doc.text(x - 26, level - 3, "%+.1f" % (low + span * step / 4), size=6.8,
                 colour="#6B6D76", align="right", width=22)
    if zero_line and low < 0 < high:
        doc.line(x, plot_y(0), x + width, plot_y(0), colour="#C9C5B8", width=0.9)

    step_x = width / max(len(points) - 1, 1)
    coordinates = [(x + index * step_x, plot_y(value))
                   for index, value in enumerate(points)]
    for index in range(len(coordinates) - 1):
        start = coordinates[index]
        end = coordinates[index + 1]
        doc.line(start[0], start[1], end[0], end[1], colour=colour, width=1.8)
    for index, point in enumerate(coordinates):
        doc.circle(point[0], point[1], 2.6, fill=colour)
        if index < len(labels):
            doc.text(point[0] - step_x / 2, y - 11, labels[index], size=6.8,
                     colour="#6B6D76", align="center", width=step_x)


def radar(doc, cx, cy, radius, axes, series, rings=5, maximum=10.0):
    """axes: [label]. series: [(name, colour, [scores...])]"""
    count = max(len(axes), 3)
    angles = [math.pi / 2 - (2 * math.pi * index / count) for index in range(count)]

    for ring in range(1, rings + 1):
        r = radius * ring / rings
        points = [(cx + math.cos(angle) * r, cy + math.sin(angle) * r) for angle in angles]
        doc.polygon(points, stroke="#E4E1D8", width=0.6)
    for angle in angles:
        doc.line(cx, cy, cx + math.cos(angle) * radius, cy + math.sin(angle) * radius,
                 colour="#E4E1D8", width=0.6)

    for name, colour, values in series:
        points = []
        for index, angle in enumerate(angles):
            value = values[index] if index < len(values) else 0
            r = radius * max(0.0, min(1.0, value / maximum))
            points.append((cx + math.cos(angle) * r, cy + math.sin(angle) * r))
        doc.polygon(points, stroke=colour, width=1.6)
        for point in points:
            doc.circle(point[0], point[1], 2.2, fill=colour)

    for index, angle in enumerate(angles):
        if index >= len(axes):
            break
        lx = cx + math.cos(angle) * (radius + 12)
        ly = cy + math.sin(angle) * (radius + 12)
        label = axes[index]
        lines = wrap(label, 7.4, 92)
        for offset, line in enumerate(lines):
            width = text_width(line, 7.4)
            anchor = lx - width / 2
            if math.cos(angle) > 0.3:
                anchor = lx
            elif math.cos(angle) < -0.3:
                anchor = lx - width
            doc.text(anchor, ly - offset * 9 - 2, line, size=7.4, colour="#1C1D21")

    legend_x = cx - radius
    legend_y = cy - radius - 26
    for name, colour, _ in series:
        doc.rect(legend_x, legend_y, 8, 8, fill=colour, radius=1.5)
        doc.text(legend_x + 12, legend_y + 0.5, name, size=8)
        legend_x += text_width(name, 8) + 32


def bar_row(doc, x, y, width, value, maximum, colour, height=7):
    doc.rect(x, y, width, height, fill="#EDEBE4", radius=2)
    filled = width * max(0.0, min(1.0, value / (maximum or 1)))
    if filled > 0:
        doc.rect(x, y, filled, height, fill=colour, radius=2)


def kpi_tile(doc, x, y, width, height, value, label, note=None, accent="#2B4570"):
    doc.rect(x, y, width, height, fill="#FFFFFF", stroke="#E4E1D8", radius=4)
    doc.line(x, y + height - 3, x + width, y + height - 3, colour=accent, width=3)
    doc.text(x + 12, y + height - 34, str(value), size=21, font="F5", colour=accent)
    doc.text(x + 12, y + height - 48, str(label).upper(), size=6.8, font="F2",
             colour="#6B6D76")
    if note:
        for index, line in enumerate(wrap(note, 6.8, width - 20)[:2]):
            doc.text(x + 12, y + 12 - index * 8.5, line, size=6.8, colour="#6B6D76")
