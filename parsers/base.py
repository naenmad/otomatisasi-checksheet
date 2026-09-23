"""
Base interface and data contracts for all checksheet parsers.
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any


class BaseParser(ABC):
    """Abstract base class for all checksheet document parsers."""

    @abstractmethod
    def can_parse(self, file_path: str, wb: Optional[Any] = None) -> bool:
        """
        Return True if this parser can handle the given document or workbook.
        """
        pass

    @abstractmethod
    def extract_metadata(self, file_path: str, wb: Optional[Any] = None) -> Dict[str, str]:
        """
        Extract metadata from checksheet document.
        Must return a dict with keys:
          - part_number: str
          - part_name: str
          - model: str
          - customer: str
          - doc_number: str
          - filename: str
        """
        pass

    @abstractmethod
    def extract_inspection_points(self, file_path: str, wb: Optional[Any] = None) -> List[Dict[str, str]]:
        """
        Extract list of inspection points from checksheet document.
        Each item in the list must be a dict with keys:
          - item_no: str
          - inspection_item: str
          - standard: str
          - method: str
          - master_data: str
        """
        pass

    def extract_images(self, file_path: str, output_dir: Optional[str] = None, part_number: str = "") -> List[str]:
        """
        Extract sketch drawings or reference images from the document.
        Default implementation returns an empty list unless overridden.
        """
        return []
