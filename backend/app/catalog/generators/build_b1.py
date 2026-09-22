from __future__ import annotations

import sys
import pathlib

backend_dir = pathlib.Path(__file__).parent.parent.parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.catalog.generators.b1_part1 import B1_EDUCATION
from app.catalog.generators.b1_comm_env import B1_COMMUNICATION, B1_ENVIRONMENT
from app.catalog.generators.b1_tech_rel import B1_TECHNOLOGY, B1_RELATIONSHIPS
from app.catalog.generators.b1_work import B1_WORK
from app.catalog.generators.b1_travel import B1_TRAVEL
from app.catalog.generators.b1_health import B1_HEALTH
from app.catalog.generators.generate_catalog_data import save_level_file

ALL_B1 = [
    B1_EDUCATION,
    B1_COMMUNICATION,
    B1_ENVIRONMENT,
    B1_TECHNOLOGY,
    B1_RELATIONSHIPS,
    B1_WORK,
    B1_TRAVEL,
    B1_HEALTH,
]

if __name__ == "__main__":
    count = save_level_file("b1", ALL_B1)
    print(f"Total B1 entries generated: {count}")
