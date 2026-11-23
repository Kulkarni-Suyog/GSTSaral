"""Data models for GSTSaral records."""

from dataclasses import asdict, dataclass
from typing import Any, Dict


@dataclass
class Record:
    item_or_topic: str
    old_rule: str
    new_rule: str
    effective_from: str
    document: str
    source_url: str

    def __post_init__(self) -> None:
        self.item_or_topic = str(self.item_or_topic or "").strip()
        self.old_rule = str(self.old_rule or "").strip()
        self.new_rule = str(self.new_rule or "").strip()
        self.effective_from = str(self.effective_from or "").strip()
        self.document = str(self.document or "").strip()
        self.source_url = str(self.source_url or "").strip()

        if not self.item_or_topic:
            raise ValueError("item_or_topic cannot be empty")
        if not self.new_rule:
            raise ValueError("new_rule cannot be empty")
        if not self.source_url.startswith(("http://", "https://")):
            raise ValueError(f"Invalid source_url: {self.source_url}")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
