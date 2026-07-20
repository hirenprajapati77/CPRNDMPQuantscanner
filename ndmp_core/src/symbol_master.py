"""
NDMP OS v6.0 - Symbol Master Registry Engine
Manages canonical NSE F&O stock metadata, lot sizes, sectors, and instrument status.
"""

from pydantic import BaseModel, Field
from typing import Dict, List, Optional


class SymbolMetadata(BaseModel):
    """Symbol Metadata Schema."""
    symbol: str = Field(..., description="NSE Trading Symbol, e.g. BEL")
    company_name: str
    sector: str
    industry: str
    lot_size: int = Field(..., ge=1)
    is_fo_eligible: bool = True
    isin: str
    listing_date: str


class SymbolMasterRegistry:
    """Symbol Master Manager for ~180 NSE F&O stocks."""

    def __init__(self):
        self._symbols: Dict[str, SymbolMetadata] = {}

    def register_symbol(self, metadata: SymbolMetadata) -> None:
        """Register or update a symbol in the master registry."""
        self._symbols[metadata.symbol] = metadata

    def get_symbol(self, symbol: str) -> Optional[SymbolMetadata]:
        """Retrieve metadata for a given symbol."""
        return self._symbols.get(symbol.upper())

    def get_all_fo_symbols(self) -> List[str]:
        """Return list of active F&O eligible symbols."""
        return [sym for sym, meta in self._symbols.items() if meta.is_fo_eligible]

    def count(self) -> int:
        """Return total number of registered symbols."""
        return len(self._symbols)
