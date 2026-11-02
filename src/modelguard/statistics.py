"""Operational drop thresholds and statistical evidence are separate quantities."""
from math import comb, ceil, sqrt
from .config import GuardError

def exact_mcnemar(regressions: int, improvements: int) -> float:
    if min(regressions, improvements) < 0: raise GuardError('Negative discordant count')
    n = regressions + improvements
    if n == 0: return 1.0
    tail = sum(comb(n, k) for k in range(min(regressions, improvements) + 1)) / (2 ** n)
    return min(1.0, 2 * tail)

def wilson(success: int, n: int) -> list[float] | None:
    if n == 0: return None
    if not 0 <= success <= n: raise GuardError('Invalid binomial counts')
    z = 1.95996398454; p = success / n; den = 1 + z*z/n
    mid = (p + z*z/(2*n))/den
    half = z*sqrt(p*(1-p)/n + z*z/(4*n*n))/den
    return [max(0.0, mid-half), min(1.0, mid+half)]

def percentile(values: list[float], p: float):
    if not values: return None
    return sorted(values)[max(0, ceil(len(values)*p)-1)]
