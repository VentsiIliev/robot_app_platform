import csv
import logging
import os
from typing import List, Optional

from src.applications.user_management.domain.i_user_repository import IUserRepository
from src.applications.user_management.domain.user_schema import UserRecord, UserSchema

_logger = logging.getLogger(__name__)


class CsvUserRepository(IUserRepository):

    def __init__(self, file_path: str, schema: UserSchema):
        self._path   = file_path
        self._schema = schema
        self._fieldnames = [f.key for f in schema.fields]
        os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
        if not os.path.exists(file_path):
            self._write_all([])

    def get_schema(self) -> UserSchema:
        return self._schema

    def get_all(self) -> List[UserRecord]:
        try:
            with open(self._path, newline="", encoding="utf-8") as f:
                return [UserRecord.from_dict(row) for row in csv.DictReader(f)]
        except Exception as exc:
            _logger.error("get_all failed: %s", exc)
            return []

    def get_by_id(self, user_id) -> Optional[UserRecord]:
        key = self._schema.id_key
        return next((r for r in self.get_all() if str(r.get(key)) == str(user_id)), None)

    def add(self, record: UserRecord) -> bool:
        if self.exists(record.get_id(self._schema.id_key)):
            return False
        records = self.get_all()
        records.append(record)
        self._write_all(records)
        return True

    def update(self, record: UserRecord) -> bool:
        records = self.get_all()
        key = self._schema.id_key
        for i, r in enumerate(records):
            if str(r.get(key)) == str(record.get(key)):
                records[i] = record
                self._write_all(records)
                return True
        return False

    def delete(self, user_id) -> bool:
        key     = self._schema.id_key
        records = self.get_all()
        filtered = [r for r in records if str(r.get(key)) != str(user_id)]
        if len(filtered) == len(records):
            return False
        self._write_all(filtered)
        return True

    def exists(self, user_id) -> bool:
        key = self._schema.id_key
        return any(str(r.get(key)) == str(user_id) for r in self.get_all())

    def _write_all(self, records: List[UserRecord]) -> None:
        with open(self._path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=self._fieldnames, extrasaction="ignore")
            writer.writeheader()
            for r in records:
                writer.writerow(r.to_dict())
