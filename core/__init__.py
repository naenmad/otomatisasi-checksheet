"""
Core engine modules for Summit FactoryHub Checksheet Automation.
Contains:
- automator: Playwright automation engine for FactoryHub
- extractor: Excel/PDF parsing and image extraction
- logger: Shared logging setup
- version: App version metadata and system banners
"""
import os
import sys

# Ensure core directory is in sys.path so modules inside core can import each other seamlessly
_CORE_DIR = os.path.dirname(os.path.abspath(__file__))
if _CORE_DIR not in sys.path:
    sys.path.insert(0, _CORE_DIR)

# Expose modules
from . import automator
from . import extractor
from . import logger
from . import version

__all__ = ["automator", "extractor", "logger", "version"]
