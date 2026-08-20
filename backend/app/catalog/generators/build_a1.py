from __future__ import annotations

import sys
import pathlib

backend_dir = pathlib.Path(__file__).parent.parent.parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.catalog.generators.level_a1 import ALL_A1
from app.catalog.generators.generate_catalog_data import save_level_file

if __name__ == "__main__":
    count = save_level_file("a1", ALL_A1)
    print(f"Total A1 entries generated: {count}")
