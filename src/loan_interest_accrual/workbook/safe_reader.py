from dataclasses import dataclass
from io import BytesIO
from pathlib import PurePath
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile

from openpyxl import load_workbook
from openpyxl.workbook.workbook import Workbook

from .limits import MAX_UPLOAD_BYTES
from .schema import WorkbookError, WorkbookErrorCode


@dataclass(frozen=True, slots=True)
class SafeReadResult:
    workbook: Workbook | None
    errors: tuple[WorkbookError, ...]


def _error(code: WorkbookErrorCode, field: str, message: str) -> WorkbookError:
    return WorkbookError(code, None, None, field, message)


def _inspect_package(package: ZipFile) -> tuple[WorkbookError, ...]:
    errors: list[WorkbookError] = []
    lower_names = {name.lower() for name in package.namelist()}
    if any("vbaproject" in name or "/activex/" in name for name in lower_names):
        errors.append(
            _error(
                WorkbookErrorCode.MACRO_NOT_ALLOWED,
                "workbook",
                "macros and active code are not allowed",
            )
        )
    if any(
        "/externallinks/" in name or name == "xl/connections.xml"
        for name in lower_names
    ):
        errors.append(
            _error(
                WorkbookErrorCode.EXTERNAL_LINK_NOT_ALLOWED,
                "workbook",
                "external links and data connections are not allowed",
            )
        )
    if any("/embeddings/" in name for name in lower_names):
        errors.append(
            _error(
                WorkbookErrorCode.EMBEDDED_OBJECT_NOT_ALLOWED,
                "workbook",
                "embedded objects are not allowed",
            )
        )
    for name in package.namelist():
        if not name.lower().endswith(".rels"):
            continue
        try:
            root = ElementTree.fromstring(package.read(name))
        except ElementTree.ParseError:
            continue
        if any(
            relationship.attrib.get("TargetMode") == "External"
            for relationship in root
        ):
            if not any(
                error.error_code is WorkbookErrorCode.EXTERNAL_LINK_NOT_ALLOWED
                for error in errors
            ):
                errors.append(
                    _error(
                        WorkbookErrorCode.EXTERNAL_LINK_NOT_ALLOWED,
                        "workbook",
                        "external relationships are not allowed",
                    )
                )
            break

    try:
        root = ElementTree.fromstring(package.read("xl/workbook.xml"))
        namespace = {
            "m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
        }
        names = [
            sheet.attrib.get("name", "")
            for sheet in root.findall("m:sheets/m:sheet", namespace)
        ]
        duplicate_names = sorted({name for name in names if names.count(name) > 1})
        for name in duplicate_names:
            errors.append(
                WorkbookError(
                    WorkbookErrorCode.SHEET_DUPLICATE,
                    name,
                    None,
                    name,
                    f"worksheet name is duplicated: {name}",
                )
            )
    except (KeyError, ElementTree.ParseError):
        pass
    return tuple(errors)


def read_workbook(filename: str, source_bytes: bytes) -> SafeReadResult:
    if PurePath(filename).suffix.lower() != ".xlsx":
        return SafeReadResult(
            None,
            (
                _error(
                    WorkbookErrorCode.FILE_EXTENSION_INVALID,
                    "filename",
                    "only .xlsx uploads are accepted",
                ),
            ),
        )
    if len(source_bytes) > MAX_UPLOAD_BYTES:
        return SafeReadResult(
            None,
            (
                _error(
                    WorkbookErrorCode.FILE_TOO_LARGE,
                    "file",
                    f"workbook exceeds {MAX_UPLOAD_BYTES} bytes",
                ),
            ),
        )
    try:
        with ZipFile(BytesIO(source_bytes)) as package:
            package_errors = _inspect_package(package)
    except (BadZipFile, OSError, ValueError):
        return SafeReadResult(
            None,
            (
                _error(
                    WorkbookErrorCode.WORKBOOK_OPEN_FAILED,
                    "workbook",
                    "uploaded bytes are not a readable .xlsx package",
                ),
            ),
        )
    if any(
        error.error_code is WorkbookErrorCode.SHEET_DUPLICATE
        for error in package_errors
    ):
        return SafeReadResult(None, package_errors)
    try:
        workbook = load_workbook(
            BytesIO(source_bytes),
            data_only=False,
            read_only=False,
            keep_links=False,
        )
    except Exception:
        return SafeReadResult(
            None,
            package_errors
            + (
                _error(
                    WorkbookErrorCode.WORKBOOK_OPEN_FAILED,
                    "workbook",
                    "openpyxl could not open the workbook",
                ),
            ),
        )
    return SafeReadResult(workbook, package_errors)
