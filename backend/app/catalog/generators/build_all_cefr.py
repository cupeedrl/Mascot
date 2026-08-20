from __future__ import annotations

import json
import pathlib
import sys

from app.catalog.schema import CatalogEntrySeed, CatalogSetSeed
from app.catalog.validator import validate_catalog_dataset

# We will construct all data modularly and write JSON files to data/
DATA_DIR = pathlib.Path(__file__).parent.parent / "data"

print(f"Target data directory: {DATA_DIR}")
