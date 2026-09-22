from datetime import datetime

from pydantic import BaseModel


class Source(BaseModel):
    """Provenance for any priced or sourced item. The composer may only
    attach a Source that came from a real provider call — never fabricated.
    """

    provider: str
    fetched_at: datetime
    url: str | None = None
    deep_link: str | None = None
