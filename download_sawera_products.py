"""
Entrypoint alias for download_excel-sheets_products.py
"""
import importlib.util
from pathlib import Path
import sys

target_script = Path(__file__).parent / "download_excel-sheets_products.py"

if target_script.exists():
    spec = importlib.util.spec_from_file_location("download_excel_sheets_products", target_script)
    module = importlib.util.module_from_spec(spec)
    sys.modules["download_excel_sheets_products"] = module
    spec.loader.exec_module(module)
    if hasattr(module, "main"):
        module.main()
