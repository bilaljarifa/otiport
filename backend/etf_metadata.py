# -*- coding: utf-8 -*-
"""ETF universe metadata shared between `api.py` and `backend/assistant_tools.py`.

Extracted from `api.py` (where it originally lived inline) so the AI
Assistant's tools can look up the same names/regions without importing from
`api.py` itself — `api.py` registers the assistant router, so the reverse
import would be circular.
"""

from __future__ import annotations

ETF_METADATA: dict[str, dict[str, str]] = {
    "PSI": {"name": "Semiconductors", "region": "North America"},
    "IYW": {"name": "US Technology", "region": "North America"},
    "RING": {"name": "Gold Miners", "region": "Developed Markets"},
    "PICK": {"name": "Metals & Mining", "region": "Developed Markets"},
    "NLR": {"name": "Nuclear Energy", "region": "Developed Markets"},
    "UTES": {"name": "Utilities", "region": "North America"},
    "LIT": {"name": "Lithium & Battery", "region": "Developed Markets"},
    "NANR": {"name": "Natural Resources", "region": "North America"},
    "GUNR": {"name": "Global Resources", "region": "Developed Markets"},
    "XCEM": {"name": "Emerging Markets", "region": "Emerging Markets"},
    "PTLC": {"name": "Large Cap", "region": "North America"},
    "FXU": {"name": "Utilities Alpha", "region": "North America"},
}
