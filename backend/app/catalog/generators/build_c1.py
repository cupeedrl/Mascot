from __future__ import annotations

import sys
import pathlib

backend_dir = pathlib.Path(__file__).parent.parent.parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.catalog.generators.c1_leadership_global import C1_LEADERSHIP, C1_GLOBAL_ISSUES
from app.catalog.generators.c1_psych_innov import C1_PSYCHOLOGY, C1_INNOVATION
from app.catalog.generators.c1_acad_prof import C1_ACADEMIC_LIFE, C1_PROFESSIONAL_COMMUNICATION
from app.catalog.generators.c1_soc_tech import C1_SOCIETY, C1_ADVANCED_TECH
from app.catalog.generators.generate_catalog_data import save_level_file

ALL_C1 = [
    C1_LEADERSHIP,
    C1_GLOBAL_ISSUES,
    C1_PSYCHOLOGY,
    C1_INNOVATION,
    C1_ACADEMIC_LIFE,
    C1_PROFESSIONAL_COMMUNICATION,
    C1_SOCIETY,
    C1_ADVANCED_TECH,
]

if __name__ == "__main__":
    count = save_level_file("c1", ALL_C1)
    print(f"Total C1 entries generated: {count}")
