from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

@dataclass
class AvailabilityResult:
    in_stock: Optional[bool] = None
    price: Optional[float] = None
    currency: Optional[str] = None
    raw_price_text: Optional[str] = None
    raw_stock_text: Optional[str] = None
    scraped_at: Optional[datetime] = field(default_factory=lambda: datetime.now(timezone.utc))
    status: Optional[str] = "PENDING" # IN_STOCK, OUT_OF_STOCK, ERROR
    reason: Optional[str] = None # For errors: "selector_not_found", "http_error_503", etc.