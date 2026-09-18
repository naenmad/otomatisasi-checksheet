"""
Smart Checksheet Semantic Tokenizer & Spatial Adjacency Graph Engine
=====================================================================
Provides human-like, typo-tolerant, and layout-aware parsing for automotive
quality checksheets (Excel & PDF).

Components:
1. SemanticStandardParser: Decomposes and reconstructs nominals and tolerances
   (e.g., combining upper '+ 0' and lower '- 1.4' into '5 + 0 / - 1.4').
2. FuzzyToolNormalizer: Standardizes inspection methods and tools (typo-tolerant).
3. SpatialBlockDetector: Identifies item-to-subitem relationships (e.g. APPEARANCE
   criteria and NUT POSITION coordinates) across merged or blank cells.
"""

import re
import difflib
from typing import List, Dict, Tuple, Optional, Any


class FuzzyToolNormalizer:
    """
    Standardizes tool and inspection method names against the official FactoryHub dictionary.
    Handles human typos, spacing variations, and abbreviations.
    """
    CANONICAL_TOOLS = [
        "Pin chk. / Caliper",
        "Pin chk.",
        "Insert Pin Datum",
        "Tapper Gauge",
        "Tapper Gg",
        "Feeler Gg",
        "Feeler Gauge",
        "Steelrule",
        "Ruler Gg",
        "Caliper",
        "Visual",
        "Torque Wrench",
        "Height Gauge",
        "Micrometer",
        "Dial Indicator",
    ]

    ALIASES = {
        "steel ruler": "Steelrule",
        "steelrule": "Steelrule",
        "steel rule": "Steelrule",
        "ruler": "Steelrule",
        "ruller": "Ruler Gg",
        "ruler gg": "Ruler Gg",
        "ruler gauge": "Ruler Gg",
        "feeler": "Feeler Gg",
        "feeler gg": "Feeler Gg",
        "feler gg": "Feeler Gg",
        "feler": "Feeler Gg",
        "feeler gauge": "Feeler Gauge",
        "tapper": "Tapper Gg",
        "tapper gg": "Tapper Gg",
        "tapper gauge": "Tapper Gauge",
        "taper gg": "Tapper Gg",
        "taper gauge": "Tapper Gauge",
        "pin chk": "Pin chk.",
        "pin check": "Pin chk.",
        "pin chk.": "Pin chk.",
        "pin chk / caliper": "Pin chk. / Caliper",
        "pin chk. / caliper": "Pin chk. / Caliper",
        "pin check / caliper": "Pin chk. / Caliper",
        "insert pin datum": "Insert Pin Datum",
        "insert pin": "Insert Pin Datum",
        "visual": "Visual",
        "visuil": "Visual",
        "visuall": "Visual",
        "mata": "Visual",
        "torque wrench": "Torque Wrench",
        "torque": "Torque Wrench",
        "caliper": "Caliper",
        "jangka sorong": "Caliper",
    }

    @classmethod
    def normalize(cls, method_str: str) -> str:
        """Normalize a tool/method string to FactoryHub standard."""
        if not method_str:
            return ""

        cleaned = re.sub(r"\s+", " ", str(method_str)).strip()
        if not cleaned:
            return ""

        lower_val = cleaned.lower()

        # Direct alias lookup
        if lower_val in cls.ALIASES:
            return cls.ALIASES[lower_val]

        # Substring / containment check
        for alias, canonical in cls.ALIASES.items():
            if alias in lower_val:
                return canonical

        # Fuzzy string similarity matching
        matches = difflib.get_close_matches(cleaned, cls.CANONICAL_TOOLS, n=1, cutoff=0.75)
        if matches:
            return matches[0]

        # Fallback to cleaned original text (preserve custom instruments)
        return cleaned


class SemanticStandardParser:
    """
    Intelligent tokenizer and composer for inspection standards and tolerances.
    Capable of reconstructing split-row upper/lower tolerances, multiline cells,
    symmetrical tolerances, and qualitative visual inspection criteria.
    """

    # Regex patterns for semantic token classification
    PATTERNS = {
        # Bilateral / Symmetrical tolerance e.g. "0 ± 1.0", "5 ± 0.5", "±1.0"
        "bilateral": re.compile(r"^(?:(\d+(?:\.\d+)?)\s*)?[±\+\/\-]+\s*(\d+(?:\.\d+)?)$"),

        # Complete upper & lower tolerance in one string e.g. "0 + 2.0 / - 0", "5 +0.2/-0.3"
        "complete_two_sided": re.compile(
            r"^([Øø]?\s*\d+(?:\.\d+)?)\s*[\+]+\s*(\d+(?:\.\d+)?)\s*\/\s*[\-]+\s*(\d+(?:\.\d+)?)$"
        ),

        # Upper tolerance token e.g. "+ 0", "+ 0.5", "+ 1.4", "+ 2.0", "+0.2"
        "upper_tol": re.compile(r"^\+\s*(\d+(?:\.\d+)?)$"),

        # Lower tolerance token e.g. "- 1.4", "- 1.5", "- 2.0", "- 0.0", "- 0", "-0.2"
        "lower_tol": re.compile(r"^\-\s*(\d+(?:\.\d+)?)$"),

        # Number with upper tolerance e.g. "5 + 0", "0 + 0.5", "5 + 1.4"
        "nominal_with_upper": re.compile(r"^([Øø]?\s*\d+(?:\.\d+)?)\s*\+\s*(\d+(?:\.\d+)?)$"),

        # Qualitative criteria e.g. "NO CRACK / NECK", "NO DEFORM", "NO BURR = 0.3 mm", "OK / NG"
        "qualitative": re.compile(
            r"^(NO\s+[A-Z\s\/\=\.\d]+|OK\s*\/\s*NG|DEV\.WITHIN\s*\d+(?:\.\d+)?|[A-Za-z\s]+(?:NOT|NO)\s+[A-Za-z\s]+)$",
            re.IGNORECASE
        ),

        # Pure nominal number e.g. "5", "0", "18", "138 POINT", "1 POINT"
        "pure_nominal": re.compile(r"^([Øø]?\s*\d+(?:\.\d+)?(?:\s*POINT[S]?)?)$", re.IGNORECASE),
    }

    @classmethod
    def is_lower_tolerance(cls, text: str) -> bool:
        """Check if a string represents a lower tolerance continuation token."""
        if not text:
            return False
        cleaned = re.sub(r"\s+", " ", str(text)).strip()
        if cls.PATTERNS["lower_tol"].match(cleaned):
            return True
        if re.search(r"^[\-\/]\s*(\d+(?:\.\d+)?)$", cleaned):
            return True
        if re.search(r"[\-\+\±]\s*\d", cleaned):
            return True
        if re.match(r"^[\+\-]?\s*0(?:\.0+)?$", cleaned):
            return True
        return False

    @classmethod
    def compose_standard(
        cls,
        base_std: str,
        row_extra_tokens: Optional[List[str]] = None,
        next_row_tokens: Optional[List[str]] = None
    ) -> Tuple[str, bool]:
        """
        Combines base standard cell with horizontal extra tokens and vertical continuation tokens.
        
        Returns:
            (canonical_standard_string, consumed_next_row_flag)
        """
        consumed_next = False
        base = str(base_std or "").replace("\r\n", "\n").replace("\n", " ").strip()
        base = re.sub(r"\s+", " ", base)

        extras = [str(t).strip() for t in (row_extra_tokens or []) if t and str(t).strip()]
        nexts = [str(t).strip() for t in (next_row_tokens or []) if t and str(t).strip()]

        # Check for multiline in base cell e.g. "5\n+0\n-1.4"
        multiline_match = re.match(
            r"^([Øø]?\s*\d+(?:\.\d+)?)\s*\+\s*(\d+(?:\.\d+)?)\s*[\-\/]\s*(\d+(?:\.\d+)?)$",
            base
        )
        if multiline_match:
            nom, u, l = multiline_match.groups()
            return f"{nom} + {u} / - {l}", False

        # Case 1: Base is qualitative criteria (e.g. "NO CRACK / NECK", "NO DEFORM", "OK / NG", "136 Points", "Not Allowed")
        if any(q in base.upper() for q in [
            "NO ", "OK / NG", "OK/NG", "NOT ", "NOT ALLOWED", "DEV.WITHIN",
            "GO / NO GO", "POINTS", "POINT", "SMOOTH PIN", "PC"
        ]):
            # Check if next row has OK/NG qualifier
            if nexts and any("OK" in n.upper() for n in nexts):
                consumed_next = True
                return f"{base} OK / NG", consumed_next
            if extras:
                return f"{base} {' '.join(extras)}", False
            return cls.clean_format(base), False

        # Case 2: Base is already complete bilateral or two-sided tolerance
        # e.g. "0 ± 1.0", "0 + 2.0 / - 0", "5 ± 1.0"
        if "±" in base or ("+" in base and "-" in base and "/" in base):
            return cls.clean_format(base), False

        # Case 3: Multi-dimension standard (e.g. 18 +0.2 X 36 +0.4)
        if any("X" in t.upper() for t in extras):
            comb = f"{base} " + " ".join(extras)
            if nexts:
                comb += " / " + " ".join(nexts)
                consumed_next = True
            return cls.clean_format(comb), consumed_next

        # Case 4: Combine base nominal with horizontal extra tokens and vertical continuation tokens
        all_tokens = extras + nexts
        pm_tok = next((t for t in all_tokens if "±" in t), None)
        if pm_tok:
            val = re.sub(r"^±\s*", "", pm_tok).strip()
            consumed = pm_tok in nexts
            return cls.clean_format(f"{base} ± {val}"), consumed

        plus_tok = next((t for t in all_tokens if "+" in t and "±" not in t), None)
        minus_tok = next((t for t in all_tokens if "-" in t and "±" not in t and not t.startswith("+")), None)
        zero_tok = next((t for t in all_tokens if re.match(r"^[\+\-]?\s*0(?:\.0+)?$", t)), None)

        if plus_tok or minus_tok or zero_tok:
            consumed = any(t in nexts for t in [plus_tok, minus_tok, zero_tok] if t is not None)
            if plus_tok and (zero_tok or minus_tok):
                u = re.sub(r"^\+\s*", "", plus_tok).strip()
                if minus_tok and minus_tok != zero_tok:
                    l = re.sub(r"^\-\s*", "", minus_tok).strip()
                    return cls.clean_format(f"{base} + {u} / - {l}"), consumed
                elif zero_tok:
                    l = zero_tok.lstrip("-+").strip() or "0"
                    return cls.clean_format(f"{base} + {u} / - {l}"), consumed
                else:
                    return cls.clean_format(f"{base} + {u} / - 0"), consumed
            elif minus_tok and zero_tok:
                l = re.sub(r"^\-\s*", "", minus_tok).strip()
                return cls.clean_format(f"{base} + 0 / - {l}"), consumed
            elif plus_tok:
                u = re.sub(r"^\+\s*", "", plus_tok).strip()
                return cls.clean_format(f"{base} + {u} / - 0"), consumed
            elif minus_tok:
                l = re.sub(r"^\-\s*", "", minus_tok).strip()
                return cls.clean_format(f"{base} + 0 / - {l}"), consumed

        # Fallback to horizontal extra tokens if any
        if extras:
            return cls.clean_format(f"{base} {' '.join(extras)}"), False

        return cls.clean_format(base), False

    @classmethod
    def clean_format(cls, std_str: str) -> str:
        """Ensures standard string adheres to clean, consistent industrial format."""
        if not std_str:
            return ""

        s = str(std_str).strip()
        # Collapse multiple whitespaces
        s = re.sub(r"\s+", " ", s)
        # Normalize slash spacing e.g. " / "
        s = re.sub(r"\s*\/\s*", " / ", s)
        # Remove redundant repeated slashes
        s = re.sub(r"(\s*\/\s*)+", " / ", s)
        # Normalize plus/minus symbol e.g. " ± "
        s = re.sub(r"\s*±\s*", " ± ", s)
        # Normalize plus tolerance e.g. " + "
        s = re.sub(r"(?<=\d)\s*\+\s*", " + ", s)
        # Format two-sided tolerances with proper spaces e.g. "5 +0.2/-0.3" -> "5 + 0.2 / - 0.3"
        s = re.sub(r"(?<=\d)\s*\+\s*([0-9\.]+)\s*\/\s*([\-\+])\s*([0-9\.]+)", r" + \1 / \2 \3", s)
        # Normalize minus tolerance after slash e.g. "/ -" -> "/ - "
        s = re.sub(r"\/\s*\-\s*", "/ - ", s)
        # Normalize plus tolerance after slash e.g. "/ +" -> "/ + "
        s = re.sub(r"\/\s*\+\s*", "/ + ", s)
        # If slash is followed by 0 without sign e.g. "/ 0", format as "/ - 0"
        s = re.sub(r"\/\s*0(?:\.0+)?(?!\.\d*[1-9])(?!\d)", "/ - 0", s)
        # Clean double spaces
        s = re.sub(r"\s+", " ", s).strip()
        return s


class SpatialBlockDetector:
    """
    Spatial analyzer that identifies hierarchical table structures in checksheets.
    Groups parent-child items (such as APPEARANCE and NUT POSITION) even when
    cells are visually unmerged or left blank by human operators.
    """

    FOOTER_KEYWORDS = [
        "JUDGEMENT",
        "REMARK",
        "REMARKS",
        "NOTE :",
        "NOTE:",
        "INSPECTOR :",
        "APPROVED BY",
        "CHECKED BY",
        "PREPARED BY",
    ]

    HEADER_KEYWORDS = [
        "INSPECTION ITEM",
        "ITEM NAME",
        "STANDARD",
        "METHOD",
        "SKETCH",
    ]

    @classmethod
    def is_footer_row(cls, row_cell_values: List[Any]) -> bool:
        """
        Determines if row signals the end of the inspection items table.
        Only triggers when footer keywords ('JUDGEMENT', 'REMARKS', etc.)
        appear in the core table columns (item number or item name).
        """
        for v in row_cell_values:
            upper = str(v or "").strip().upper()
            if upper in ["JUDGEMENT", "JUDGMENT", "REMARK", "REMARKS", "NOTE :", "NOTE:"]:
                return True
            if upper.startswith("JUDGEMENT") or upper.startswith("REMARK"):
                return True
        return False

    @classmethod
    def is_header_noise(cls, item_name: str) -> bool:
        """Determines if item name is a repeated table column header."""
        upper = item_name.strip().upper()
        return upper in ["INSPECTION ITEM", "ITEM", "NO", "STANDARD", "STD", "SKETCH", "ITEM NAME", "NO. / ITEM"]
