"""Load and access JSON records."""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class RecordStore:
    def __init__(self, data_file: Path):
        self.data_file = data_file
        self.records = []

    def load(self):
        with self.data_file.open("r", encoding="utf-8") as file:
            self.records = json.load(file)

        logger.info("records loaded", extra={"records": len(self.records)})

    def list_records(self):
        return self.records

    def get_record(self, record_id: str):
        return next(
            (record for record in self.records if record["id"] == record_id), None
        )
