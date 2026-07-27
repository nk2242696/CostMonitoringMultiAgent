"""
Recommendation analyzers package.

Resource-type-specific analyzers that generate targeted cost
optimization recommendations.
"""

from src.recommendations.analyzers.compute_optimizer import ComputeOptimizer
from src.recommendations.analyzers.storage_optimizer import StorageOptimizer
from src.recommendations.analyzers.savings_calculator import SavingsCalculator

__all__ = ["ComputeOptimizer", "StorageOptimizer", "SavingsCalculator"]
