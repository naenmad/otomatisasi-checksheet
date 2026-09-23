"""
Modular checksheet parser package.
Exposes BaseParser and get_parser_for_file factory.
"""
from parsers.base import BaseParser
from parsers.detector import get_parser_for_file
from parsers.iqc_incoming import IQCIncomingParser
from parsers.mmki_ir import MMKIIRParser
from parsers.mmki_ipqc import MMKIIPQCParser
from parsers.pdf_parser import PDFParser
from parsers.generic_excel import GenericExcelParser
from parsers.image_extractor import extract_excel_images

__all__ = [
    "BaseParser",
    "get_parser_for_file",
    "IQCIncomingParser",
    "MMKIIRParser",
    "MMKIIPQCParser",
    "PDFParser",
    "GenericExcelParser",
    "extract_excel_images",
]
