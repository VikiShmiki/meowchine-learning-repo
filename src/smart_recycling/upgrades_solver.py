"""Deterministic weighted maximum coverage with a municipal equity safeguard."""

import itertools
import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Candidate:
    """A source site and its demand catchment, encoded as a bit set."""

    id: str
    mask: int


@dataclass(frozen=True)
class Solution:
    """Selection with independent optimality and floor-feasibility evidence."""

    selected: tuple[str, ...]
    covered: int
    solver: str
    floor_status: str
    totals: tuple[float, ...]


class Problem:
    """One material's baseline, population and hypothetical additive upgrades."""

    def __init__(
        self,
        weights: list[float],
        groups: list[int],
        denominators: list[float],
        baseline: int,
        candidates: list[Candidate],
        floor: float = 50,
    ) -> None:
        if (
            len(weights) != len(groups)
            or not denominators
            or not 0 <= floor <= 100
            or any(not math.isfinite(w) or w < 0 for w in weights + denominators)
            or any(g < 0 or g >= len(denominators) for g in groups)
        ):
            raise ValueError("Invalid population or equity inputs")
        valid = (1 << len(weights)) - 1
        if any(mask < 0 or mask & ~valid for mask in [baseline, *(c.mask for c in candidates)]):
            raise ValueError("Catchment references unknown demand")
        if len({c.id for c in candidates}) != len(candidates):
            raise ValueError("Duplicate candidate IDs")
        for g, denominator in enumerate(denominators):
            if not math.isclose(
                denominator,
                math.fsum(w for w, i in zip(weights, groups, strict=True) if i == g),
                abs_tol=1e-6,
            ):
                raise ValueError("Municipal denominator does not reconcile")
        self.weights, self.groups, self.denominators = weights, groups, denominators
        self.baseline, self.floor = baseline, floor
        self.candidates = sorted(candidates, key=lambda c: c.id)

    def totals(self, mask: int) -> tuple[float, ...]:
        """Count each covered resident once, within their municipality."""
        values = [[] for _ in self.denominators]
        # Scan bytes to avoid repeatedly copying a city-sized integer for each bit.
        # Demand visits stay in ascending index order, preserving fsum inputs exactly.
        for offset, byte in enumerate(mask.to_bytes((mask.bit_length() + 7) // 8, "little")):
            while byte:
                bit = byte & -byte
                index = offset * 8 + bit.bit_length() - 1
                values[self.groups[index]].append(self.weights[index])
                byte ^= bit
        return tuple(math.fsum(v) for v in values)

    def score(self, totals: tuple[float, ...]) -> tuple:
        """Feasible plans maximize city coverage; others use lexicographic max-min."""
        percents = sorted(100 * n / d for n, d in zip(totals, self.denominators, strict=True) if d)
        feasible = all(p >= self.floor for p in percents)
        return (1, math.fsum(totals)) if feasible else (0, *percents, math.fsum(totals))

    def solve(self, n: int, exact_limit: int = 10000) -> Solution:
        """Enumerate small searches; otherwise use greedy addition and two swap passes.

        The union of all candidates is a valid infeasibility certificate. A heuristic
        failure without that certificate is explicitly not a proof of infeasibility.
        """
        if isinstance(n, bool) or not isinstance(n, int) or n < 0:
            raise ValueError("Upgrade budget must be a nonnegative integer")
        candidates = self.candidates
        n = min(n, len(candidates))
        base_totals = self.totals(self.baseline)

        def evaluate(indices: tuple[int, ...]) -> tuple[int, tuple[float, ...]]:
            mask = self.baseline
            for i in indices:
                mask |= candidates[i].mask
            gains = self.totals(mask & ~self.baseline)
            return mask, tuple(a + b for a, b in zip(base_totals, gains, strict=True))

        def better(totals: tuple, indices: tuple, best_totals: tuple, best: tuple) -> bool:
            score, previous = self.score(totals), self.score(best_totals)
            return score > previous or (
                score == previous and (len(indices), indices) < (len(best), best)
            )

        selected: tuple[int, ...] = ()
        mask, totals = self.baseline, base_totals
        count = 0
        for k in range(n + 1):
            count += math.comb(len(candidates), k)
            if count > exact_limit:
                break
        exact = count <= exact_limit
        if exact:
            for k in range(1, n + 1):
                for indices in itertools.combinations(range(len(candidates)), k):
                    trial_mask, trial_totals = evaluate(indices)
                    if better(trial_totals, indices, totals, selected):
                        selected, mask, totals = indices, trial_mask, trial_totals
        else:

            def extend(indices: tuple[int, ...]) -> tuple:
                current_mask, current_totals = evaluate(indices)
                best, best_mask, best_totals = indices, current_mask, current_totals
                for i, candidate in enumerate(candidates):
                    if i in indices:
                        continue
                    gains = self.totals(candidate.mask & ~current_mask)
                    trial_totals = tuple(a + b for a, b in zip(current_totals, gains, strict=True))
                    trial = tuple(sorted((*indices, i)))
                    if better(trial_totals, trial, best_totals, best):
                        best, best_mask, best_totals = (
                            trial,
                            current_mask | candidate.mask,
                            trial_totals,
                        )
                return best, best_mask, best_totals

            for _ in range(n):
                trial, trial_mask, trial_totals = extend(selected)
                if trial == selected:
                    break
                selected, mask, totals = trial, trial_mask, trial_totals
            for _ in range(2):
                best, best_mask, best_totals = selected, mask, totals
                for removed in selected:
                    trial, trial_mask, trial_totals = extend(
                        tuple(i for i in selected if i != removed)
                    )
                    if better(trial_totals, trial, best_totals, best):
                        best, best_mask, best_totals = trial, trial_mask, trial_totals
                if best == selected:
                    break
                selected, mask, totals = best, best_mask, best_totals
        upper = self.baseline
        for candidate in candidates:
            upper |= candidate.mask
        status = (
            "met"
            if self.score(totals)[0]
            else (
                "proven_infeasible"
                if exact or not self.score(self.totals(upper))[0]
                else "not_found"
            )
        )
        return Solution(
            tuple(candidates[i].id for i in selected),
            mask,
            "optimal" if exact else "heuristic",
            status,
            totals,
        )
