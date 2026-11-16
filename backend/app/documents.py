from __future__ import annotations

import csv
import io
import json
import re
import zipfile
from pathlib import Path, PurePosixPath
from xml.etree import ElementTree as ET

MAX_DOCUMENT_BYTES = 25 * 1024 * 1024
MAX_ARCHIVE_ENTRIES = 4000
MAX_UNCOMPRESSED_BYTES = 50 * 1024 * 1024
DEFAULT_EXTRACT_CHARS = 24_000
ALLOWED_DOCUMENT_EXTENSIONS = {
    ".pdf", ".docx", ".xlsx", ".txt", ".md", ".csv", ".tsv", ".json",
    ".jsonl", ".xml", ".html", ".htm", ".css", ".js", ".jsx", ".ts", ".tsx",
    ".py", ".ps1", ".sh", ".sql", ".yml", ".yaml", ".toml", ".ini", ".log",
}


class DocumentError(ValueError):
    pass


class DocumentParserUnavailable(DocumentError):
    pass


def _limit_text(text: str, max_chars: int) -> tuple[str, bool]:
    normalized = text.replace("\x00", "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if len(normalized) <= max_chars:
        return normalized, False
    return normalized[:max_chars].rstrip() + "\n\n[EXTRACTION TRUNCATED: document exceeds the local context limit.]", True


def _zip_checked(path: Path) -> zipfile.ZipFile:
    try:
        archive = zipfile.ZipFile(path)
        infos = archive.infolist()
        if len(infos) > MAX_ARCHIVE_ENTRIES:
            archive.close()
            raise DocumentError("The document archive contains too many internal entries.")
        uncompressed = sum(info.file_size for info in infos)
        if uncompressed > MAX_UNCOMPRESSED_BYTES:
            archive.close()
            raise DocumentError("The document expands beyond the 50 MB safety limit.")
        if any(info.flag_bits & 0x1 for info in infos):
            archive.close()
            raise DocumentError("Encrypted office documents are not supported.")
        return archive
    except zipfile.BadZipFile as exc:
        raise DocumentError("The office document is not a valid ZIP-based document.") from exc


def _docx_text(path: Path) -> tuple[str, list[str]]:
    with _zip_checked(path) as archive:
        try:
            xml_bytes = archive.read("word/document.xml")
        except KeyError as exc:
            raise DocumentError("The DOCX file does not contain its main document body.") from exc
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        raise DocumentError("The DOCX document XML is malformed.") from exc
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    paragraphs: list[str] = []
    for index, paragraph in enumerate(root.findall(".//w:body/w:p", ns), start=1):
        pieces: list[str] = []
        for node in paragraph.iter():
            if node.tag == f"{{{ns['w']}}}t" and node.text:
                pieces.append(node.text)
            elif node.tag == f"{{{ns['w']}}}tab":
                pieces.append("\t")
            elif node.tag == f"{{{ns['w']}}}br":
                pieces.append(" ")
        content = "".join(pieces).strip()
        if content:
            paragraphs.append(f"[paragraph {index:04d}] {content}")
    if not paragraphs:
        raise DocumentError("No readable paragraph text was found in the DOCX file.")
    return "\n".join(paragraphs), ["DOCX paragraph references are included inline as [paragraph NNNN]."]


def _xlsx_text(path: Path) -> tuple[str, list[str]]:
    main_ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    rel_ns = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    package_rel_ns = "http://schemas.openxmlformats.org/package/2006/relationships"
    with _zip_checked(path) as archive:
        names = set(archive.namelist())
        if "xl/workbook.xml" not in names or "xl/_rels/workbook.xml.rels" not in names:
            raise DocumentError("The XLSX workbook structure is incomplete.")
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        relation_map: dict[str, str] = {}
        for relation in rels.findall(f"{{{package_rel_ns}}}Relationship"):
            target = relation.attrib.get("Target", "")
            if target.startswith("/"):
                target = target.lstrip("/")
            else:
                target = str(PurePosixPath("xl") / target)
            normalized = str(PurePosixPath(target))
            if normalized.startswith("xl/") and ".." not in PurePosixPath(normalized).parts:
                relation_map[relation.attrib.get("Id", "")] = normalized
        shared_strings: list[str] = []
        if "xl/sharedStrings.xml" in names:
            shared_root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            for item in shared_root.findall(f"{{{main_ns}}}si"):
                shared_strings.append("".join(node.text or "" for node in item.iter(f"{{{main_ns}}}t")))
        output: list[str] = []
        sheets = workbook.find(f"{{{main_ns}}}sheets")
        if sheets is None:
            raise DocumentError("No worksheets were found in the XLSX workbook.")
        for sheet in sheets.findall(f"{{{main_ns}}}sheet"):
            name = sheet.attrib.get("name", "Sheet")
            target = relation_map.get(sheet.attrib.get(f"{{{rel_ns}}}id", ""))
            if not target or target not in names:
                continue
            sheet_root = ET.fromstring(archive.read(target))
            output.append(f"[worksheet: {name}]")
            sheet_data = sheet_root.find(f"{{{main_ns}}}sheetData")
            if sheet_data is None:
                continue
            cell_count = 0
            for row in sheet_data.findall(f"{{{main_ns}}}row"):
                for cell in row.findall(f"{{{main_ns}}}c"):
                    reference = cell.attrib.get("r", "?")
                    cell_type = cell.attrib.get("t", "")
                    value_node = cell.find(f"{{{main_ns}}}v")
                    value = value_node.text if value_node is not None else ""
                    if cell_type == "s" and value:
                        try:
                            value = shared_strings[int(value)]
                        except (ValueError, IndexError):
                            value = ""
                    elif cell_type == "inlineStr":
                        value = "".join(node.text or "" for node in cell.iter(f"{{{main_ns}}}t"))
                    if value not in (None, ""):
                        output.append(f"[{name}!{reference}] {value}")
                    cell_count += 1
                    if cell_count > 30_000:
                        output.append("[WORKSHEET TRUNCATED: more than 30,000 cells.] ")
                        break
                if cell_count > 30_000:
                    break
        if len(output) <= 1:
            raise DocumentError("No readable cell values were found in the XLSX workbook.")
    return "\n".join(output), ["XLSX cell references are included inline as [SheetName!A1]."]


def _pdf_text(path: Path) -> tuple[str, list[str]]:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise DocumentParserUnavailable(
            "PDF extraction requires the optional local pypdf package. Install it in the JARVIS backend environment with: "
            "python -m pip install pypdf"
        ) from exc
    try:
        reader = PdfReader(str(path), strict=False)
        if reader.is_encrypted:
            raise DocumentError("Password-protected PDFs are not supported.")
        pages: list[str] = []
        for index, page in enumerate(reader.pages, start=1):
            text = (page.extract_text() or "").strip()
            if text:
                pages.append(f"[page {index}]\n{text}")
        if not pages:
            raise DocumentError("No selectable text was found. Scanned PDFs need a separately approved local OCR engine.")
        return "\n\n".join(pages), ["PDF page references are included inline as [page N]."]
    except DocumentError:
        raise
    except Exception as exc:
        raise DocumentError(f"Could not extract PDF text: {type(exc).__name__}: {exc}") from exc


def _text_file(path: Path) -> tuple[str, list[str]]:
    try:
        raw = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        try:
            raw = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            raise DocumentError(f"Could not read the text file: {exc}") from exc
    except OSError as exc:
        raise DocumentError(f"Could not read the text file: {exc}") from exc

    if path.suffix.lower() in {".csv", ".tsv"}:
        delimiter = "\t" if path.suffix.lower() == ".tsv" else ","
        try:
            rows = list(csv.reader(io.StringIO(raw), delimiter=delimiter))
            raw = "\n".join(f"[row {index}] " + " | ".join(cell.strip() for cell in row) for index, row in enumerate(rows, start=1))
        except csv.Error as exc:
            raise DocumentError(f"The delimited-text file is malformed: {exc}") from exc
    lines = raw.splitlines()
    chunked: list[str] = []
    for start in range(0, len(lines), 40):
        end = min(len(lines), start + 40)
        chunked.append(f"[{path.name}:L{start + 1}-L{end}]\n" + "\n".join(lines[start:end]))
    return "\n\n".join(chunked), ["Text and source-code line references are included inline as [filename:Lx-Ly]."]


def extract_document(path: Path, max_chars: int = DEFAULT_EXTRACT_CHARS) -> dict:
    """Extract text from a user-imported file without executing macros, scripts, or embedded content."""
    path = Path(path)
    if not path.is_file() or path.is_symlink():
        raise DocumentError("The selected import is not a regular file.")
    if path.stat().st_size > MAX_DOCUMENT_BYTES:
        raise DocumentError("The document exceeds the 25 MB import limit.")
    extension = path.suffix.lower()
    if extension not in ALLOWED_DOCUMENT_EXTENSIONS:
        raise DocumentError(f"Unsupported document extension: {extension or '(none)'}")
    if extension == ".docx":
        content, citations = _docx_text(path)
        parser = "docx-xml"
    elif extension == ".xlsx":
        content, citations = _xlsx_text(path)
        parser = "xlsx-xml"
    elif extension == ".pdf":
        content, citations = _pdf_text(path)
        parser = "pypdf"
    else:
        content, citations = _text_file(path)
        parser = "text-lines"
    content, truncated = _limit_text(content, max(1000, min(int(max_chars), 80_000)))
    return {
        "content": content,
        "citations": citations,
        "parser": parser,
        "characters": len(content),
        "truncated": truncated,
    }
