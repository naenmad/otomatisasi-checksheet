"""
Smart Checksheet Semantic Tokenizer & Spatial Adjacency Graph Engine
=====================================================================
Provides human-like, typo-tolerant, and layout-aware parsing for automotive
quality checksheets (Excel & PDF).

Components:
1. SemanticStandardParser: Decomposes and reconstructs nominals and tolerances
   (e.g., combining upper '+ 0' and lower '- 1.4' into '5 + 0 / - 1.4').
2. FuzzyToolNormalizer: Standardizes inspection methods and tools (typo-tolerant).
3. TextNormalizer: Standardizes inspection item labels and appearance descriptions.
4. SpatialBlockDetector: Identifies item-to-subitem relationships (e.g. APPEARANCE
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
        "Hammering",
        "Bolt",
        "Roll Meter",
        "Millsheet",
        "Data Label",
        "Thickness Meter",
        "Thread Gauge",
    ]

    ALIASES = {
        "hammering": "Hammering",
        "hammer": "Hammering",
        "palu": "Hammering",
        "hammer test": "Hammering",
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
        "visual insp.": "Visual",
        "visual insp": "Visual",
        "mata": "Visual",
        "torque wrench": "Torque Wrench",
        "torque": "Torque Wrench",
        "caliper": "Caliper",
        "jangka sorong": "Caliper",
        "bolt": "Bolt",
        "bolt m6": "Bolt M6",
        "bolt m8": "Bolt M8",
        "bolt m10": "Bolt M10",
        "baut": "Bolt",
        "roll meter": "Roll Meter",
        "rollmeter": "Roll Meter",
        "meteran": "Roll Meter",
        "millsheet": "Millsheet",
        "mill sheet": "Millsheet",
        "data label": "Data Label",
        "thickness meter": "Thickness Meter",
        "thickness tester": "Thickness Meter",
        "coating thick/ tester": "Thickness Meter",
        "coating thickness": "Thickness Meter",
        "coating thickness tester": "Thickness Meter",
        "thread gauge": "Thread Gauge",
        "thread gaude": "Thread Gauge",
        "thread gage": "Thread Gauge",
        "thread gouge": "Thread Gauge",
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


class TextNormalizer:
    """
    Standardizes inspection item labels and appearance descriptions.
    Handles inconsistent casing, typos, abbreviations, trailing punctuation,
    and verbose appearance criteria text.
    """

    # Canonical defect items set (share the same item_no in checksheet tables)
    DEFECT_ITEMS = {
        "No Rust", "No Scratch", "No Dent", "No Crack", "No Wave",
        "No Wrinkle", "No Neck", "No Over Cutting", "No Spatter",
        "No Bubble", "No Meler", "No Kotor", "No Bintik Putih",
        "No Menggumpal", "No Orange Peel", "No Cacat", "Profile OK", "Packing"
    }

    # ── Inspection Item Label Mapping ──
    # key = lowercased input, value = canonical output
    ITEM_ALIASES = {
        # Appearance variants
        "app": "Appearance",
        "appearance": "Appearance",
        "surface": "Surface",
        # Thickness
        "thickness": "Thickness",
        "thicknss": "Thickness",
        "thickness permukaan": "Thickness",
        "thickness after press": "Thickness After Press",
        "thickness painting": "Thickness Painting",
        "coating thickness": "Coating Thickness",
        # Dimension / Qty / Hole
        "qty hole": "Qty Hole",
        "jumlah hole": "Qty Hole",
        "hole": "Hole",
        "hole slot": "Hole Slot",
        "diameter hole": "Diameter Hole",
        "hole diameter": "Diameter Hole",
        "diamter hole": "Diameter Hole",
        "dimention hole": "Diameter Hole",
        "dimensi hole": "Diameter Hole",
        "dimensi": "Dimension",
        "dimention": "Dimension",
        "distance": "Distance",
        "length": "Length",
        "lenght": "Length",
        "panjang": "Length",
        "width": "Width",
        "lebar": "Width",
        "panjang total": "Total Length",
        "radius": "Radius",
        # Burr / Burry
        "burry": "Burry",
        "burr": "Burry",
        "burrs": "Burry",
        "height of burr": "Burry",
        "no burr": "Burry",
        "no burry": "Burry",
        "burry max 0.3": "Burry",
        "burry max. : 0.3mm": "Burry",
        "burrs max 0,3 mm": "Burry",
        "burry max 0.2": "Burry",
        "burry <= 0.2": "Burry",
        "burry ≤ 0.2": "Burry",
        # Appearance defect checks
        "no rust": "No Rust",
        "no rusty": "No Rust",
        "tidak rusty": "No Rust",
        "tidak karat": "No Rust",
        "karat": "No Rust",
        "rust": "No Rust",
        "rusty": "No Rust",
        "no scratch": "No Scratch",
        "tidak scratch": "No Scratch",
        "scratch": "No Scratch",
        "tidak lecet": "No Scratch",
        "lecet": "No Scratch",
        "no wave": "No Wave",
        "tidak wave": "No Wave",
        "wave": "No Wave",
        "no spatter": "No Spatter",
        "no spater": "No Spatter",
        "spatter": "No Spatter",
        "spater": "No Spatter",
        "sparter": "No Spatter",
        "tidak spater": "No Spatter",
        "tidak spatter": "No Spatter",
        "no crack": "No Crack",
        "tidak crack": "No Crack",
        "crack": "No Crack",
        "neck / crack": "No Crack",
        "no crack / neck": "No Crack",
        "no crack/neck": "No Crack",
        "no dent": "No Dent",
        "no dented": "No Dent",
        "danted": "No Dent",
        "dent": "No Dent",
        "dented": "No Dent",
        "tidak dent": "No Dent",
        "tidak dented": "No Dent",
        "no over cutting": "No Over Cutting",
        "tidak over cutting": "No Over Cutting",
        "over cutting": "No Over Cutting",
        "overcutting": "No Over Cutting",
        "no wrinkle": "No Wrinkle",
        "tidak wrinkle": "No Wrinkle",
        "wrinkle": "No Wrinkle",
        "no neck": "No Neck",
        "tidak neck": "No Neck",
        "neck": "No Neck",
        # Painting / Coating appearance defects
        "no bubble": "No Bubble",
        "tidak bubble": "No Bubble",
        "tidak bubule": "No Bubble",
        "bubble": "No Bubble",
        "buble": "No Bubble",
        "no meler": "No Meler",
        "tidak meler": "No Meler",
        "meler": "No Meler",
        "no kotor": "No Kotor",
        "tidak kotor": "No Kotor",
        "kotor": "No Kotor",
        "no bintik putih": "No Bintik Putih",
        "tidak bintik putih": "No Bintik Putih",
        "tidak bintik": "No Bintik Putih",
        "bintik putih": "No Bintik Putih",
        "bintik": "No Bintik Putih",
        "no menggumpal": "No Menggumpal",
        "tidak menggumpal": "No Menggumpal",
        "menggumpal": "No Menggumpal",
        "gumpal": "No Menggumpal",
        "no orange peel": "No Orange Peel",
        "tidak orange peel": "No Orange Peel",
        "orange peel": "No Orange Peel",
        "no cacat": "No Cacat",
        "tidak cacat": "No Cacat",
        "cacat": "No Cacat",
        "profil ok": "Profile OK",
        "profile ok": "Profile OK",
        "profile oke": "Profile OK",
        # Function / Packing
        "function": "Function",
        "fungsi": "Function",
        "packing": "Packing",
        "packing ok": "Packing",
        "packing \"ok\"": "Packing",
        "packing o": "Packing",
        # Material
        "material": "Spec. Material",
        "spec. material": "Spec. Material",
        "warna": "Color",
        "zn plating": "Zn Plating",
        "plastic coating": "Plastic Coating",
        # Weld / Structural
        "non desctructive test": "Non Destructive Test",
        "non destructive test": "Non Destructive Test",
        "identification mark": "Identification Mark",
        "welding strength": "Welding Strength",
        "welding strenght": "Welding Strength",
        "welding strength (chisel test)": "Welding Strength (Chisel Test)",
        # Nut
        "nut center": "Nut Center",
        "nut tidak rusak": "Nut OK",
        "nut tidak seret": "Nut Smooth",
        # Trim
        "trim line": "Trim Line",
        # Flange
        "flange height": "Flange Height",
    }

    # Numbered item pattern: "1. TOTAL COMPONEN", "10. NECK / CRACK"
    NUMBERED_ITEM_RE = re.compile(r"^\d+\.\s*(.+)$")

    # Common appearance defect keywords for standard normalization
    DEFECT_KEYWORDS = [
        "crack", "dent", "dented", "scratch", "rusty", "rust",
        "over cutting", "overcutting", "neck", "burr", "burrs",
        "wave", "wrinkle", "twist", "deformation", "spatter",
        "karat", "bubble", "buble", "mengelupas", "belang",
        "meler", "kotor", "bintik", "gumpal", "orange peel", "cacat", "lecet",
    ]

    @classmethod
    def normalize_item(cls, item: str) -> str:
        """Normalize an inspection_item label to canonical form."""
        if not item:
            return ""

        # Clean whitespace and trailing punctuation
        cleaned = re.sub(r"\s+", " ", str(item)).strip()
        cleaned = cleaned.rstrip(",;.")

        if not cleaned:
            return ""

        lower = cleaned.lower().strip()

        # Direct alias
        if lower in cls.ITEM_ALIASES:
            return cls.ITEM_ALIASES[lower]

        # Handle numbered items: "1. TOTAL COMPONEN" -> strip number
        num_match = cls.NUMBERED_ITEM_RE.match(cleaned)
        if num_match:
            inner = num_match.group(1).strip()
            inner_lower = inner.lower()
            if inner_lower in cls.ITEM_ALIASES:
                return cls.ITEM_ALIASES[inner_lower]
            return cls._title_case(inner)

        # Handle Flange variants: "Flangeb", "Flange a", "Flange c"
        flange_match = re.match(r"^flange\s*([a-z])$", lower)
        if flange_match:
            return f"Flange {flange_match.group(1).upper()}"

        # Handle NUT POSITION with brackets
        if "nut position" in lower:
            return cleaned.upper()

        # Handle HOLE DATUM
        if "hole datum" in lower:
            return cleaned.upper()

        # Handle DATUM SURFACE
        if "datum surface" in lower:
            return cleaned.upper()

        # Single character garbage ('d', 'L')
        if len(cleaned) <= 1:
            return cleaned.upper()

        # Fallback: smart title case
        return cls._title_case(cleaned)

    @classmethod
    def is_qualitative_item(cls, item_label: str) -> bool:
        """Check if an item label represents a qualitative / pass-fail check."""
        if not item_label:
            return False
        lower = item_label.lower().strip()
        if lower.startswith("no ") or lower.startswith("tidak "):
            return True
        if lower in (
            "profile ok", "sesuai sample", "hole complete",
            "welding not perforate", "welding tidak keropos",
            "non destructive test", "ndt",
            "nut ok", "nut smooth", "nut center", "nut position", "bolt smooth",
            "go / no go", "go/no go", "packing", "marking -67l- jelas"
        ):
            return True
        for kw in cls.DEFECT_KEYWORDS:
            if kw in lower and lower not in ("thickness", "coating thickness", "dimension"):
                return True
        return False

    @classmethod
    def normalize_standard(cls, standard: str, item_label: str = "") -> str:
        """
        Normalize standard text. For appearance-type items, clean up verbose
        defect descriptions into a concise comma-separated format.
        For qualitative / defect items with empty or '-' standard, return 'OK / NG'.
        """
        if not standard or standard.strip() in ("-", ""):
            if item_label:
                item_lower = item_label.lower().strip()
                if item_lower == "profile ok":
                    return "Sesuai Sample"
                if cls.is_qualitative_item(item_label):
                    return "OK / NG"
            return ""

        cleaned = re.sub(r"\s+", " ", str(standard)).strip()

        # Only apply appearance normalization when appropriate:
        # 1. Item is explicitly appearance-type
        # 2. Standard starts with defect-check phrasing (No X, Tidak X, etc.)
        item_lower = item_label.lower() if item_label else ""
        is_appearance = item_lower in ("appearance", "app", "surface")
        lower_std = cleaned.lower()

        # Check if the standard text starts with defect-check patterns
        starts_with_defect_check = bool(re.match(
            r"^(?:no\s+|tidak\s+|part\s+tidak|painting\s+|plating\s+|coating\s+)",
            lower_std
        ))

        if is_appearance or starts_with_defect_check:
            normalized = cls._normalize_appearance_standard(cleaned)
            if normalized:
                return normalized

        # Force defect items standard
        if item_label and item_label in cls.DEFECT_ITEMS:
            if item_label == "Profile OK":
                return "Sesuai Sample"
            return "OK / NG"

        # Force Burry standard to ≤ 0.3 mm
        if item_label and item_label.lower().strip() == "burry":
            if not standard or standard.strip() in ("-", "", "OK / NG"):
                return "≤ 0.3 mm"

        # Fix comma-decimal inconsistency: "0,55" -> "0.55", "1,6" -> "1.6"
        cleaned = re.sub(r"(\d),(\d)", r"\1.\2", cleaned)

        # Standardize max 0.3 / 0.2 mm variations -> "≤ 0.3 mm"
        cleaned_lower = cleaned.lower().strip()
        if re.search(r"^(?:burry\s+|burrs\s+|burr\s+)?(?:max\.?\s*:?\s*0[.,][12345](?:\s*mm)?|0[.,][12345]\s*max|<=?\s*0[.,][12345](?:\s*mm)?|≤\s*0[.,][12345](?:\s*mm)?)$", cleaned_lower):
            return "≤ 0.3 mm"

        # Fix missing space before ±
        cleaned = re.sub(r"(\d)±", r"\1 ±", cleaned)

        return cleaned

    @classmethod
    def _normalize_appearance_standard(cls, text: str) -> str:
        """
        Parse verbose appearance criteria and produce a clean, standardized form.
        
        Input examples:
            "No crack, dented, scratch,over cutting, profil part OK ( sesuai sample)"
            "No Rust, No Scratch, No Wrinkle, No Dented, No Crack, No Neck."
            "Painting tidak buble,mengelupas,scratch,dented,belang"
            "tidak dented, scratch, tidak karat"
        
        Output: "No Crack, No Dent, No Scratch, No Over Cutting, Profile OK"
        """
        lower = text.lower().strip().rstrip(".")

        # Defect-type normalization map: raw -> canonical
        defect_map = {
            "crack": "Crack",
            "dented": "Dent",
            "dent": "Dent",
            "scratch": "Scratch",
            "lecet": "Scratch",
            "over cutting": "Over Cutting",
            "overcutting": "Over Cutting",
            "rusty": "Rust",
            "rust": "Rust",
            "karat": "Rust",
            "neck": "Neck",
            "burr": "Burry",
            "burrs": "Burry",
            "burry": "Burry",
            "wave": "Wave",
            "wrinkle": "Wrinkle",
            "twist": "Twist",
            "deformation": "Deformation",
            "spatter": "Spatter",
            "spater": "Spatter",
            "bubble": "Bubble",
            "buble": "Bubble",
            "meler": "Meler",
            "kotor": "Kotor",
            "bintik putih": "Bintik Putih",
            "bintik": "Bintik Putih",
            "menggumpal": "Menggumpal",
            "gumpal": "Menggumpal",
            "orange peel": "Orange Peel",
            "orange": "Orange Peel",
            "kulit jeruk": "Orange Peel",
            "cacat": "Cacat",
            "mengelupas": "Peeling",
            "belang": "Uneven",
            "keropos": "Porosity",
        }

        found_defects = []
        extra_notes = []

        # Check for coating/painting/plating prefix
        coating_prefix = ""
        coating_match = re.match(r"^(painting|plating|coating)\s+(tidak\s+)?", lower)
        if coating_match:
            coating_prefix = coating_match.group(1).title()
            lower = lower[coating_match.end():]

        # Split by comma, semicolon, or "dan"/"and"
        parts = re.split(r"[,;]+|\s+dan\s+|\s+and\s+", lower)

        no_prefix_active = False
        for part in parts:
            part = part.strip()
            if not part:
                continue

            # Check for Qty Hole
            qh_match = re.search(r"qty\s*hole\s*[:=]?\s*(\d+)", part)
            if qh_match:
                extra_notes.append(f"Qty Hole: {qh_match.group(1)}")
                continue

            # Check "no ..." or "tidak ..."  
            no_match = re.match(r"^(?:no|tidak)\s+(.+)$", part)
            if no_match:
                no_prefix_active = True
                part = no_match.group(1).strip()

            # Try to match known defects
            matched = False
            for raw_defect, canonical in defect_map.items():
                if raw_defect in part:
                    if canonical not in found_defects:
                        found_defects.append(canonical)
                    matched = True
                    break

            if not matched:
                # Handle special phrases
                if "packing" in part:
                    extra_notes.append("Packing")
                elif "profil" in part and "ok" in part:
                    extra_notes.append("Profile OK")
                elif "sesuai sample" in part:
                    if "Profile OK" not in extra_notes:
                        extra_notes.append("Sesuai Sample")
                elif re.search(r"\bok\b", part) and re.search(r"\bng\b", part):
                    extra_notes.append("OK / NG")
                elif "harmful" in part:
                    if "Burry" not in found_defects:
                        found_defects.append("Burry")
                    extra_notes.append("Max Harmful")
                elif "hole complete" in part or "hole" in part and "complete" in part:
                    extra_notes.append("Hole Complete")
                elif "welding" in part and "not" in part and "perforate" in part:
                    extra_notes.append("Welding Not Perforate")
                elif "marking" in part:
                    # Keep marking notes as-is with proper casing
                    extra_notes.append(part.strip().title())
                elif len(part) > 2 and not part.isspace():
                    # Unknown clause, keep it
                    no_prefix_active = False
                    continue

        if not found_defects and not extra_notes:
            return ""  # Can't normalize, return empty so caller keeps original

        # Build output
        result_parts = []

        for defect in found_defects:
            result_parts.append(f"No {defect}")

        result_parts.extend(extra_notes)

        output = ", ".join(result_parts)
        if coating_prefix:
            output = f"{coating_prefix}: {output}"

        return output

    @classmethod
    def _title_case(cls, text: str) -> str:
        """Smart title case that preserves known abbreviations and mixed-case part numbers."""
        # If already all-caps and short, keep it (likely an abbreviation)
        if text.isupper() and len(text) <= 6:
            return text

        # Preserve content in brackets
        def _title_word(w: str) -> str:
            if w.startswith("[") or w.startswith("("):
                return w
            if w.upper() in ("OK", "NG", "MAX", "MIN", "PC", "MM"):
                return w.upper()
            if w.upper() == "NO":
                return "No"
            if "/" in w:
                return "/".join(_title_word(p) for p in w.split("/"))
            return w.capitalize()

        words = text.split()
        return " ".join(_title_word(w) for w in words)

    @classmethod
    def normalize_point(cls, point: Dict[str, str]) -> Dict[str, str]:
        """
        Apply all normalizations to an inspection point dict.
        Call this before saving to database for consistent data.
        """
        result = dict(point)

        raw_item = result.get("inspection_item", "")
        raw_std = result.get("standard", "")
        raw_method = result.get("method", "")

        item_lower = raw_item.lower().strip()
        std_lower = raw_std.lower().strip()

        # If item is Dimension/Dimensi but standard specifies burry or <= 0.3 mm -> change item to Burry
        if item_lower in ("dimension", "dimensi") and (
            any(b in std_lower for b in ["burr", "burry"])
            or "≤ 0.3" in std_lower
            or "<= 0.3" in std_lower
            or "<_ 0.3" in std_lower
            or "0.3 mm" in std_lower
            or "0.2 mm" in std_lower
        ):
            raw_item = "Burry"
            raw_std = "≤ 0.3 mm"

        norm_item = cls.normalize_item(raw_item)
        result["inspection_item"] = norm_item

        # Normalize standard
        norm_std = cls.normalize_standard(raw_std, norm_item)
        if norm_item == "Burry":
            norm_std = "≤ 0.3 mm"
        result["standard"] = norm_std

        # Normalize method
        norm_method = FuzzyToolNormalizer.normalize(raw_method)
        if norm_item in cls.DEFECT_ITEMS:
            norm_method = "Visual"
        elif norm_item == "Burry" and (not norm_method or norm_method in ("Visual", "Visual Insp.")):
            norm_method = "Caliper"
        result["method"] = norm_method

        return result

    @classmethod
    def expand_points(cls, points: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """
        Expand a list of inspection points:
        1. Split combined appearance rows into individual defect check rows
        2. Swap category items (Function, Appearance) where standard is the real item name
        3. Standard for defect checks = "OK / NG"
        4. Re-numbers item_no sequentially, grouping appearance defect items under the same item_no
        """
        expanded = []
        for pt in points:
            normalized = cls.normalize_point(pt)
            item_lower = normalized.get("inspection_item", "").lower()
            std = normalized.get("standard", "").strip()
            method = normalized.get("method", "Visual")

            # --- Category: Appearance / App / Surface / Visual ---
            # Standard contains defect list -> split into individual rows
            if item_lower in ("appearance", "app", "surface", "visual"):
                if item_lower == "surface" and (re.search(r'[\d±]', std) or method in ("Tapper Gg", "Tapper Gauge", "Feeler Gg", "Feeler Gauge")):
                    expanded.append(normalized)
                    continue

                split_rows = cls._split_appearance_to_rows(std)
                if split_rows:
                    for split_item, split_std in split_rows:
                        expanded.append({
                            "item_no": normalized.get("item_no", ""),
                            "inspection_item": split_item,
                            "standard": split_std,
                            "method": "Visual",
                            "master_data": normalized.get("master_data", ""),
                        })
                    continue

            # --- Category: Function / Fungsi ---
            # Standard contains the real inspection item name
            # e.g. Function | "Non destructive test" | Hammering
            #   -> Non Destructive Test | OK / NG | Hammering
            if item_lower in ("function", "fungsi"):
                if std and std != "-" and not re.match(r'^[\d\.±\+\-\s\/]+$', std):
                    # Standard is text, not a measurement -> swap to item name
                    # Handle comma-separated function checks
                    sub_items = cls._split_function_to_rows(std, method)
                    if sub_items:
                        for sub_item, sub_std, sub_method in sub_items:
                            expanded.append({
                                "item_no": normalized.get("item_no", ""),
                                "inspection_item": sub_item,
                                "standard": sub_std,
                                "method": sub_method,
                                "master_data": normalized.get("master_data", ""),
                            })
                        continue

            expanded.append(normalized)

        # Re-number item_no: consecutive appearance/defect items share the exact same item_no
        current_num = 1
        appearance_group_no = None
        in_appearance_group = False

        for pt in expanded:
            item_name = pt.get("inspection_item", "")
            is_defect = item_name in cls.DEFECT_ITEMS or any(
                item_name.startswith(p) for p in ["No ", "Tidak "]
            ) or item_name in ("Profile OK", "Packing", "Sesuai Sample")

            if is_defect:
                if not in_appearance_group:
                    in_appearance_group = True
                    appearance_group_no = str(current_num)
                    current_num += 1
                pt["item_no"] = appearance_group_no
            else:
                in_appearance_group = False
                pt["item_no"] = str(current_num)
                current_num += 1

        return expanded

    @classmethod
    def _split_appearance_to_rows(cls, standard: str) -> Optional[List[Tuple[str, str]]]:
        """
        Split a combined appearance standard into individual (item_name, standard) tuples.
        Standard for defect checks = "OK / NG".
        """
        if not standard or standard.strip() in ("-", ""):
            return None

        cleaned = re.sub(r"\s+", " ", str(standard)).strip()

        # First normalize the standard text to get clean defect names
        normalized = cls._normalize_appearance_standard(cleaned)
        if not normalized:
            return None

        # Handle coating prefix
        coating_prefix = ""
        coating_match = re.match(r"^(Painting|Plating|Coating):\s*(.+)$", normalized)
        if coating_match:
            coating_prefix = coating_match.group(1)
            normalized = coating_match.group(2).strip()

        parts = [p.strip() for p in normalized.split(",") if p.strip()]

        if len(parts) <= 1:
            item_name = parts[0] if parts else normalized
            if "qty hole" in item_name.lower():
                qh_m = re.search(r"qty\s*hole\s*[:=]?\s*(\d+)", item_name, re.IGNORECASE)
                return [("Qty Hole", qh_m.group(1) if qh_m else item_name)]
            if coating_prefix:
                item_name = f"{coating_prefix}: {item_name}"
            return [(item_name, "OK / NG")]

        rows = []
        for part in parts:
            part = part.strip()
            if not part:
                continue

            item_name = part
            std_val = "OK / NG"

            if coating_prefix:
                item_name = f"No {part.replace('No ', '')}" if part.startswith("No ") else part
                item_name = f"{coating_prefix}: {item_name}"

            if "qty hole" in part.lower():
                qh_m = re.search(r"qty\s*hole\s*[:=]?\s*(\d+)", part, re.IGNORECASE)
                item_name = "Qty Hole"
                std_val = qh_m.group(1) if qh_m else part
            elif "packing" in part.lower():
                item_name = "Packing"
                std_val = "OK / NG"
            elif "profile ok" in part.lower():
                item_name = "Profile OK"
                std_val = "Sesuai Sample"
            elif "sesuai sample" in part.lower():
                item_name = "Sesuai Sample"
                std_val = "OK / NG"
            elif "hole complete" in part.lower():
                item_name = "Hole Complete"
                std_val = "OK / NG"
            elif "welding" in part.lower():
                item_name = part
                std_val = "OK / NG"
            elif "max harmful" in part.lower():
                item_name = "Burry"
                std_val = "Max Harmful"

            rows.append((item_name, std_val))

        return rows if rows else None

    @classmethod
    def _split_function_to_rows(cls, standard: str, method: str) -> Optional[List[Tuple[str, str, str]]]:
        """
        Split function/category standard into individual (item_name, standard, method) tuples.
        Handles comma-separated items and known function check names.

        Input:  "Nut tidak seret, tidak rusak, Nut Center,"
        Output: [("Nut Smooth", "OK / NG", "Bolt"),
                 ("Nut OK", "OK / NG", "Bolt"),
                 ("Nut Center", "OK / NG", "Bolt")]
        """
        if not standard or standard.strip() in ("-", ""):
            return None

        cleaned = re.sub(r"\s+", " ", str(standard)).strip().rstrip(",;.")

        # Known function item mappings
        func_aliases = {
            "non destuctive tes": "Non Destructive Test",
            "non destructive test": "Non Destructive Test",
            "non destructive tes": "Non Destructive Test",
            "ndt": "Non Destructive Test",
            "nut tidak seret": "Nut Smooth",
            "tidak seret": "Nut Smooth",
            "nut tidak rusak": "Nut OK",
            "tidak rusak": "Nut OK",
            "ulir tidak rusak": "Nut OK",
            "bolt masuk masksimal": "Bolt Smooth",
            "bolt masuk maksimal": "Bolt Smooth",
            "nut center": "Nut Center",
            "nut position": "Nut Position",
            "posisi nut center": "Nut Center",
            "go / no go": "Go / No Go",
            "go/no go": "Go / No Go",
            "tidak keropos": "Welding Tidak Keropos",
            "welding tidak keropos": "Welding Tidak Keropos",
        }

        # Split by comma
        parts = [p.strip() for p in cleaned.split(",") if p.strip()]

        rows = []
        for part in parts:
            part_lower = part.lower().strip()
            if not part_lower:
                continue

            # Look up in function aliases
            item_name = None
            for alias, canonical in func_aliases.items():
                if alias in part_lower:
                    item_name = canonical
                    break

            if not item_name:
                # Use as-is with title case
                item_name = cls._title_case(part)

            # Assign proper method if missing or generic
            sub_method = method
            if not sub_method or sub_method.lower() in ("visual", "-", ""):
                if item_name == "Non Destructive Test":
                    sub_method = "Hammering"
                elif any(k in item_name.lower() for k in ("nut", "bolt", "ulir")):
                    sub_method = "Bolt"

            rows.append((item_name, "OK / NG", sub_method))

        return rows if rows else None



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
            r"^([Øø⌀]?\s*\d+(?:\.\d+)?)\s*[\+]+\s*(\d+(?:\.\d+)?)\s*\/\s*[\-]+\s*(\d+(?:\.\d+)?)$"
        ),

        # Upper tolerance token e.g. "+ 0", "+ 0.5", "+ 1.4", "+ 2.0", "+0.2"
        "upper_tol": re.compile(r"^\+\s*(\d+(?:\.\d+)?)$"),

        # Lower tolerance token e.g. "- 1.4", "- 1.5", "- 2.0", "- 0.0", "- 0", "-0.2"
        "lower_tol": re.compile(r"^\-\s*(\d+(?:\.\d+)?)$"),

        # Number with upper tolerance e.g. "5 + 0", "0 + 0.5", "5 + 1.4"
        "nominal_with_upper": re.compile(r"^([Øø⌀]?\s*\d+(?:\.\d+)?)\s*\+\s*(\d+(?:\.\d+)?)$"),

        # Qualitative criteria e.g. "NO CRACK / NECK", "NO DEFORM", "NO BURR = 0.3 mm", "OK / NG"
        "qualitative": re.compile(
            r"^(NO\s+[A-Z\s\/\=\.\d]+|OK\s*\/\s*NG|DEV\.WITHIN\s*\d+(?:\.\d+)?|[A-Za-z\s]+(?:NOT|NO)\s+[A-Za-z\s]+)$",
            re.IGNORECASE
        ),

        # Pure nominal number e.g. "5", "0", "18", "138 POINT", "1 POINT"
        "pure_nominal": re.compile(r"^([Øø⌀]?\s*\d+(?:\.\d+)?(?:\s*POINT[S]?)?)$", re.IGNORECASE),
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
        base = re.sub(r"[ø⌀]", "Ø", base)
        base = re.sub(r"\s+", " ", base)

        extras = [str(t).strip() for t in (row_extra_tokens or []) if t and str(t).strip()]
        nexts = [str(t).strip() for t in (next_row_tokens or []) if t and str(t).strip()]

        # Check for multiline in base cell e.g. "5\n+0\n-1.4"
        multiline_match = re.match(
            r"^([Øø⌀]?\s*\d+(?:\.\d+)?)\s*\+\s*(\d+(?:\.\d+)?)\s*[\-\/]\s*(\d+(?:\.\d+)?)$",
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
