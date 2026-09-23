"""
Template detector and parser registry.
Inspects checksheet documents and returns the most specialized parser instance.
"""
import os
import openpyxl
from typing import Optional

from parsers.base import BaseParser
from parsers.pdf_parser import PDFParser
from parsers.iqc_incoming import IQCIncomingParser
from parsers.mmki_ir import MMKIIRParser
from parsers.mmki_ipqc import MMKIIPQCParser
from parsers.generic_excel import GenericExcelParser

_PARSERS = [
    PDFParser(),
    IQCIncomingParser(),
    MMKIIRParser(),
    MMKIIPQCParser(),
    GenericExcelParser(),
]


def get_parser_for_file(file_path: str) -> BaseParser:
    """
    Detect document format and return the appropriate BaseParser implementation.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Checksheet file not found: {file_path}")

    # For Excel, load workbook once to inspect structure efficiently
    wb = None
    if file_path.lower().endswith((".xlsx", ".xls")):
        try:
            wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
        except Exception:
            wb = None

    try:
        for parser in _PARSERS:
            if parser.can_parse(file_path, wb=wb):
                return parser
    finally:
        if wb:
            try:
                wb.close()
            except Exception:
                pass

    # Fallback to generic Excel parser
    return GenericExcelParser()
