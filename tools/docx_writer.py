"""
Minimal, dependency-free .docx writer (stdlib only: zipfile + string templates).

Used because this machine has no internet-installed pandoc / python-docx and
sudo requires an interactive password, so we can't just `apt install` our way
to a docx toolchain. This writes valid Office Open XML directly.
"""
import zipfile
from datetime import datetime, timezone

CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>"""

RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>"""

DOC_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>"""

APP_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties">
<Application>PopInstall docx_writer</Application>
</Properties>"""

STYLES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:docDefaults>
<w:rPrDefault><w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri"/><w:sz w:val="22"/></w:rPr></w:rPrDefault>
</w:docDefaults>
<w:style w:type="paragraph" w:default="1" w:styleId="Normal">
<w:name w:val="Normal"/>
<w:pPr><w:spacing w:after="140" w:line="276" w:lineRule="auto"/></w:pPr>
</w:style>
<w:style w:type="paragraph" w:styleId="Title">
<w:name w:val="Title"/><w:basedOn w:val="Normal"/>
<w:pPr><w:spacing w:after="120"/></w:pPr>
<w:rPr><w:rFonts w:ascii="Calibri Light" w:hAnsi="Calibri Light"/><w:sz w:val="56"/><w:b/><w:color w:val="1F3864"/></w:rPr>
</w:style>
<w:style w:type="paragraph" w:styleId="Subtitle">
<w:name w:val="Subtitle"/><w:basedOn w:val="Normal"/>
<w:pPr><w:spacing w:after="360"/></w:pPr>
<w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri"/><w:sz w:val="26"/><w:color w:val="595959"/><w:i/></w:rPr>
</w:style>
<w:style w:type="paragraph" w:styleId="Heading1">
<w:name w:val="heading 1"/><w:basedOn w:val="Normal"/>
<w:pPr><w:spacing w:before="360" w:after="160"/><w:outlineLvl w:val="0"/></w:pPr>
<w:rPr><w:b/><w:sz w:val="32"/><w:color w:val="1F3864"/></w:rPr>
</w:style>
<w:style w:type="paragraph" w:styleId="Heading2">
<w:name w:val="heading 2"/><w:basedOn w:val="Normal"/>
<w:pPr><w:spacing w:before="280" w:after="120"/><w:outlineLvl w:val="1"/></w:pPr>
<w:rPr><w:b/><w:sz w:val="26"/><w:color w:val="2E5395"/></w:rPr>
</w:style>
<w:style w:type="paragraph" w:styleId="Heading3">
<w:name w:val="heading 3"/><w:basedOn w:val="Normal"/>
<w:pPr><w:spacing w:before="200" w:after="100"/><w:outlineLvl w:val="2"/></w:pPr>
<w:rPr><w:b/><w:i/><w:sz w:val="24"/><w:color w:val="444444"/></w:rPr>
</w:style>
<w:style w:type="paragraph" w:styleId="Code">
<w:name w:val="Code"/><w:basedOn w:val="Normal"/>
<w:pPr><w:shd w:val="clear" w:color="auto" w:fill="F2F2F2"/><w:spacing w:before="0" w:after="0"/></w:pPr>
<w:rPr><w:rFonts w:ascii="Consolas" w:hAnsi="Consolas"/><w:sz w:val="19"/></w:rPr>
</w:style>
</w:styles>"""

DOC_TEMPLATE = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:body>
{body}
<w:sectPr>
<w:pgSz w:w="12240" w:h="15840"/>
<w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" w:header="720" w:footer="720" w:gutter="0"/>
</w:sectPr>
</w:body>
</w:document>"""


def _esc(text):
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _run(text, bold=False, italic=False):
    props = ""
    if bold or italic:
        props = "<w:rPr>" + ("<w:b/>" if bold else "") + ("<w:i/>" if italic else "") + "</w:rPr>"
    return f'<w:r>{props}<w:t xml:space="preserve">{_esc(text)}</w:t></w:r>'


class DocxBuilder:
    def __init__(self, doc_title="Document"):
        self.doc_title = doc_title
        self._parts = []

    def title(self, text):
        self._parts.append(f'<w:p><w:pPr><w:pStyle w:val="Title"/></w:pPr>{_run(text)}</w:p>')
        return self

    def subtitle(self, text):
        self._parts.append(f'<w:p><w:pPr><w:pStyle w:val="Subtitle"/></w:pPr>{_run(text)}</w:p>')
        return self

    def heading(self, text, level=1):
        style = f"Heading{max(1, min(level, 3))}"
        self._parts.append(f'<w:p><w:pPr><w:pStyle w:val="{style}"/></w:pPr>{_run(text)}</w:p>')
        return self

    def paragraph(self, text, bold=False, italic=False):
        lines = str(text).split("\n")
        runs = f'<w:br/>'.join(_run(line, bold, italic) for line in lines)
        self._parts.append(f"<w:p>{runs}</w:p>")
        return self

    def bullet(self, text):
        self._parts.append(
            '<w:p><w:pPr><w:ind w:left="432" w:hanging="360"/>'
            '<w:spacing w:after="60"/></w:pPr>'
            f'{_run(chr(8226) + chr(9)  + str(text))}</w:p>'
        )
        return self

    def numbered(self, index, text):
        self._parts.append(
            '<w:p><w:pPr><w:ind w:left="432" w:hanging="360"/>'
            '<w:spacing w:after="60"/></w:pPr>'
            f'{_run(f"{index}.\t{text}")}</w:p>'
        )
        return self

    def code(self, text_or_lines):
        lines = text_or_lines if isinstance(text_or_lines, (list, tuple)) else str(text_or_lines).split("\n")
        for line in lines:
            content = line if line.strip() else " "
            self._parts.append(
                f'<w:p><w:pPr><w:pStyle w:val="Code"/></w:pPr>{_run(content)}</w:p>'
            )
        return self

    def spacer(self):
        self._parts.append("<w:p/>")
        return self

    def page_break(self):
        self._parts.append('<w:p><w:r><w:br w:type="page"/></w:r></w:p>')
        return self

    def hr(self):
        self._parts.append(
            '<w:p><w:pPr><w:pBdr><w:bottom w:val="single" w:sz="6" w:space="1" w:color="BFBFBF"/></w:pBdr></w:pPr></w:p>'
        )
        return self

    def save(self, path):
        body = "\n".join(self._parts)
        document_xml = DOC_TEMPLATE.format(body=body)
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        core_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
<dc:title>{_esc(self.doc_title)}</dc:title>
<dc:creator>Claude Code</dc:creator>
<cp:lastModifiedBy>Claude Code</cp:lastModifiedBy>
<dcterms:created xsi:type="dcterms:W3CDTF">{now}</dcterms:created>
<dcterms:modified xsi:type="dcterms:W3CDTF">{now}</dcterms:modified>
</cp:coreProperties>"""

        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("[Content_Types].xml", CONTENT_TYPES)
            z.writestr("_rels/.rels", RELS)
            z.writestr("docProps/core.xml", core_xml)
            z.writestr("docProps/app.xml", APP_XML)
            z.writestr("word/document.xml", document_xml)
            z.writestr("word/styles.xml", STYLES)
            z.writestr("word/_rels/document.xml.rels", DOC_RELS)
        return path
