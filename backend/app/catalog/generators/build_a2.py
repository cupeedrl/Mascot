from __future__ import annotations

import sys
import pathlib

backend_dir = pathlib.Path(__file__).parent.parent.parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.catalog.generators.a2_data import A2_DATA_FULL
from app.catalog.generators.a2_health_hobbies import A2_HEALTH, A2_HOBBIES
from app.catalog.generators.a2_comm_services_people import A2_COMMUNICATION
from app.catalog.generators.a2_services_people import A2_DAILY_SERVICES, A2_PEOPLE
from app.catalog.generators.generate_catalog_data import save_level_file

ALL_A2_COMPLETE = A2_DATA_FULL + [A2_HEALTH, A2_HOBBIES, A2_COMMUNICATION, A2_DAILY_SERVICES, A2_PEOPLE]

if __name__ == "__main__":
    count = save_level_file("a2", ALL_A2_COMPLETE)
    print(f"Total A2 entries generated: {count}")
