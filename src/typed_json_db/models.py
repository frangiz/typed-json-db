from dataclasses import dataclass, field
import datetime
from typing import Optional


@dataclass
class Timestamped:
    """
    Base class for dataclasses that require automatic timestamp management.

    This class provides `created_at` and `updated_at` fields, which are intended to be
    automatically populated and updated by database operations. Subclasses can inherit
    from this class to ensure that creation and modification timestamps are tracked
    without manual intervention.

    Attributes:
        created_at (Optional[datetime.datetime]): The timestamp when the record was created.
        updated_at (Optional[datetime.datetime]): The timestamp when the record was last updated.
    """

    created_at: Optional[datetime.datetime] = field(default=None, kw_only=True)
    updated_at: Optional[datetime.datetime] = field(default=None, kw_only=True)
