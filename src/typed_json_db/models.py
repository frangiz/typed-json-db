from dataclasses import dataclass, field
import datetime
from typing import Optional


@dataclass
class Timestamped:
    created_at: Optional[datetime.datetime] = field(default=None, kw_only=True)
    updated_at: Optional[datetime.datetime] = field(default=None, kw_only=True)
