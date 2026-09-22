from __future__ import annotations

import sys
import pathlib

backend_dir = pathlib.Path(__file__).parent.parent.parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.catalog.generators.b2_business_media import B2_BUSINESS, B2_MEDIA
from app.catalog.generators.b2_culture_science import B2_CULTURE, B2_SCIENCE
from app.catalog.generators.b2_society_dev import B2_SOCIETY, B2_DEVELOPMENT
from app.catalog.generators.b2_env_tech import B2_ENVIRONMENT, B2_TECHNOLOGY
from app.catalog.generators.b2_expansion import B2_BUSINESS_EXP, B2_MEDIA_EXP
from app.catalog.generators.b2_expansion_part2 import B2_CULTURE_EXP, B2_SCIENCE_EXP, B2_SOCIETY_DEV_EXP
from app.catalog.generators.b2_extra_env_tech import B2_ENV_EXP, B2_TECH_EXP
from app.catalog.generators.generate_catalog_data import save_level_file

def merge_set(base_set: dict, extra_entries: list) -> dict:
    new_set = dict(base_set)
    new_set["entries"] = list(base_set["entries"]) + extra_entries
    return new_set

ALL_B2 = [
    merge_set(B2_BUSINESS, B2_BUSINESS_EXP),
    merge_set(B2_MEDIA, B2_MEDIA_EXP),
    merge_set(B2_CULTURE, B2_CULTURE_EXP),
    merge_set(B2_SCIENCE, B2_SCIENCE_EXP),
    merge_set(B2_SOCIETY, B2_SOCIETY_DEV_EXP[:5]),
    merge_set(B2_DEVELOPMENT, B2_SOCIETY_DEV_EXP[5:]),
    merge_set(B2_ENVIRONMENT, B2_ENV_EXP),
    merge_set(B2_TECHNOLOGY, B2_TECH_EXP),
]

if __name__ == "__main__":
    count = save_level_file("b2", ALL_B2)
    print(f"Total B2 entries generated: {count}")
