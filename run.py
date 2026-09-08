#!/usr/bin/env python3
"""
CLI Runner for Summit Adyawinsa Checksheet Automation
Usage:
    python run.py [--excel PATH] [--headed] [--submit] [--doc-number DOC_NO]
"""

import argparse
import asyncio
import os
import sys
from dotenv import load_dotenv

from automator import run_automation

load_dotenv()

DEFAULT_EXCEL = os.getenv("DEFAULT_EXCEL_FILE", "6. IR - 51138E000P_BRKT ASSY-RR TOWING HOOK #Rev New EO.xlsx")

def main():
    parser = argparse.ArgumentParser(description="Summit Adyawinsa Checksheet Master Automation")
    parser.add_argument(
        "--excel",
        type=str,
        default=DEFAULT_EXCEL,
        help=f"Path to Excel file (default: {DEFAULT_EXCEL})"
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run browser in background without opening window (default is visible/headed)"
    )
    parser.add_argument(
        "--submit",
        action="store_true",
        help="Automatically click 'Save Template' (default is pause for manual review & saving)"
    )
    parser.add_argument(
        "--doc-number",
        type=str,
        default=None,
        help="Custom Doc Number (e.g. 'Form 6'). If not provided, extracted from file name."
    )
    parser.add_argument(
        "--images-dir",
        type=str,
        default=None,
        help="Custom directory containing manual reference images (e.g. 'images/75511B040P/')"
    )

    args = parser.parse_args()

    if not os.path.exists(args.excel):
        print(f"[!] Error: File not found: {args.excel}")
        sys.exit(1)

    print("==================================================")
    print("   FactoryHub Checksheet Master Automation")
    print("==================================================")
    print(f" Excel File : {args.excel}")
    print(f" Browser    : {'Headless' if args.headless else 'Visible (Headed - Siap Review)'}")
    print(f" Action     : {'AUTO-SUBMIT' if args.submit else 'REVIEW & SAVE MANUAL'}")
    if args.doc_number:
        print(f" Doc Number : {args.doc_number}")
    if args.images_dir:
        print(f" Images Dir : {args.images_dir}")
    print("==================================================\n")

    headless = args.headless
    asyncio.run(
        run_automation(
            excel_path=args.excel,
            headless=headless,
            submit=args.submit,
            doc_number=args.doc_number,
            manual_images_dir=args.images_dir
        )
    )

if __name__ == "__main__":
    main()
