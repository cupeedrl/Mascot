from __future__ import annotations

import sys
import pathlib

backend_dir = pathlib.Path(__file__).parent.parent.parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.catalog.generators.c2_philo_ethics import C2_PHILOSOPHY, C2_ETHICS
from app.catalog.generators.c2_policy_econ import C2_PUBLIC_POLICY, C2_GLOBAL_ECONOMICS
from app.catalog.generators.c2_lit_strategy import C2_LITERATURE, C2_STRATEGY
from app.catalog.generators.c2_law_acad import C2_LAW, C2_ACADEMIC
from app.catalog.generators.generate_catalog_data import save_level_file

ALL_C2 = [
    C2_PHILOSOPHY,
    C2_ETHICS,
    C2_PUBLIC_POLICY,
    C2_GLOBAL_ECONOMICS,
    C2_LITERATURE,
    C2_STRATEGY,
    C2_LAW,
    C2_ACADEMIC,
]

if __name__ == "__main__":
    count = save_level_file("c2", ALL_C2)
    print(f"Total C2 entries generated: {count}")
