"""Backtester core contracts.

Re-exports the shared, immutable vocabulary used by every other module: data
models, the validated ``Config``, the per-bar ``BarContext`` / ``IndicatorWindow``
(no-look-ahead enforcement), the user/adapter protocols, the ``BacktestResult``
contract, and the deterministic hashing helpers.
"""

from .config import Config
from .context import BarContext, IndicatorWindow, PortfolioState
from .hashing import config_hash, data_hash
from .models import Bar, LookAheadError, Order, Trade, Universe
from .protocol import PITDataLoaderProtocol, StrategyProtocol
from .result import ENGINE_VERSION, BacktestResult

__all__ = [
    "Bar",
    "Trade",
    "Order",
    "Universe",
    "LookAheadError",
    "Config",
    "IndicatorWindow",
    "PortfolioState",
    "BarContext",
    "StrategyProtocol",
    "PITDataLoaderProtocol",
    "BacktestResult",
    "config_hash",
    "data_hash",
    "ENGINE_VERSION",
]
