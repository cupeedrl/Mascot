from __future__ import annotations

import sys
import pathlib

backend_dir = pathlib.Path(__file__).parent.parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.catalog.loader import load_catalog_from_dir, DATA_DIR
from app.catalog.validator import validate_catalog_dataset

def main():
    print(f"Loading catalog datasets from {DATA_DIR}...")
    dataset = load_catalog_from_dir(DATA_DIR)
    print(f"Loaded {len(dataset)} vocabulary sets.")
    
    total_entries = 0
    by_level = {}
    for vs in dataset:
        lvl = vs.level_code
        by_level[lvl] = by_level.get(lvl, 0) + len(vs.entries)
        total_entries += len(vs.entries)
    
    print("\nVocabulary counts by CEFR level:")
    for lvl in ["A1", "A2", "B1", "B2", "C1", "C2"]:
        print(f"  {lvl}: {by_level.get(lvl, 0)} entries")
    print(f"Total entries: {total_entries}")
    
    print("\nRunning comprehensive duplicate and field validation across entire dataset...")
    val_res = validate_catalog_dataset(dataset, raise_on_error=True)
    print(f"Validation successful! Zero errors found. Sets checked: {val_res.total_sets}, Entries checked: {val_res.total_entries}")

if __name__ == "__main__":
    main()
