"""Exact additive paired bootstrap, prepared once per compatible comparison.

The matrix owns integer sufficient statistics, one row per resampling unit. RNG
draws retain the legacy unit order and seed. No independent decoder resampling or
floating-point subtraction of nanosecond timestamps occurs here.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Callable, Sequence

import numpy as np

STAGES = ('zero_syndrome', 'search', 'guided_bp', 'osd', 'failed')


class PairedBootstrap:
    """Owned integer totals for nonempty, already validated (hybrid, baseline) pairs.

    `pairs` has shape (shots, 2); dictionaries are borrowed only during construction.
    `unit` is shot or batch. Arbitrarily large integer totals use Python integers
    when a conservative bound cannot prove signed-int64 reductions safe.
    Validation of scientific contexts and timing identities belongs to the caller.
    """

    def __init__(self, pairs: Sequence[tuple[dict, dict]], unit: str) -> None:
        if not pairs or unit not in ('shot', 'batch'):
            raise ValueError('nonempty pairs and shot/batch unit required')
        groups: dict[object, list[int]] = defaultdict(list)
        columns: dict[str, list[int]] = defaultdict(list)
        self.means: list[str] = []
        self.phase_keys: dict[str, list[str]] = {}
        for i, (h, b) in enumerate(pairs):
            groups[h['batch_id'] if unit == 'batch' else i].append(i)
            stage = 'zero_syndrome' if h['exit_reason'] == 'zero_syndrome' else h['exit_stage']
            reached = bool(h['osd_entered'])
            delta = int(h['block_failure']) - int(b['block_failure'])
            row = {'shots': 1, 'failure_difference': delta,
                   'early_failure_difference': int(not reached) * delta,
                   'fallback_failure_difference': int(reached) * delta}
            row.update({f'{s}_failure_difference': int(stage == s) * delta for s in STAGES})
            for clock in ('cpu', 'wall'):
                th, tb = int(h[f'{clock}_ns']), int(b[f'{clock}_ns'])
                row.update({f'{clock}_difference_ns': th - tb,
                            f'{clock}_hybrid_total': th, f'{clock}_baseline_total': tb})
                p = h[f'native_prefix_{clock}_ns']
                row[f'{clock}_unmeasured'] = int(p is None)
                measured = p is not None
                values = {
                    'prefix_on_osd': int(p) if measured and reached else 0,
                    'prefix': int(p) if measured else 0,
                    'service_other': int(h[f'service_other_{clock}_ns']) if measured else 0,
                    'avoided_baseline': tb if measured and not reached else 0,
                    'fallback_difference': int(h[f'osd_{clock}_ns']) - tb if measured and reached else 0,
                }
                for s in ('zero_syndrome', 'search', 'guided_bp', 'pre_osd_failure'):
                    selected = h['decoding_failure'] if s == 'pre_osd_failure' else stage == s
                    values[f'avoided_{s}'] = tb if measured and not reached and selected else 0
                row.update({f'{clock}_{k}_ns': v for k, v in values.items()})
                self.phase_keys[clock] = [f'{clock}_{k}_ns' for k in values]
            for key, value in row.items():
                columns[key].append(value)
        self.keys = list(columns)
        self.means = [k for k in self.keys if k.endswith('_difference') or k.endswith('_ns')]
        units = list(groups.values())
        # Each draw takes len(units) whole units. This bound also covers unequal
        # batch sizes, negative residuals, and large totals above 2**63.
        totals = [[sum(values[i] for i in indices) for values in columns.values()] for indices in units]
        bound = len(units) * max(abs(v) for row in totals for v in row)
        self.matrix = np.asarray(totals, dtype=np.int64 if bound <= np.iinfo(np.int64).max else object)
        self.units = len(units)

    def estimates(self, multiplicities: np.ndarray | None = None) -> dict[str, float | None]:
        """Return means/ratios for integer unit multiplicities (shape `(units,)`).

        None selects each unit once. Internal callers supply nonnegative draw
        counts whose sum equals `units`; a zero shot count is rejected.
        """
        values = self.matrix.sum(axis=0) if multiplicities is None else multiplicities @ self.matrix
        totals = dict(zip(self.keys, map(int, values)))
        n = totals['shots']
        if n <= 0:
            raise ValueError('bootstrap sample has no shots')
        output = {k: totals[k] / n for k in self.means}
        for clock in ('cpu', 'wall'):
            denominator = totals[f'{clock}_baseline_total']
            output[f'{clock}_ratio'] = totals[f'{clock}_hybrid_total'] / denominator if denominator > 0 else None
            if totals[f'{clock}_unmeasured']:
                for key in self.phase_keys[clock]:
                    output[key] = None
        return output

    def distributions(self, *, seed: int, count: int,
                      progress: Callable[[str], None] | None = None) -> dict[str, list[float]]:
        """Draw paired units with legacy-compatible RNG order; return finite series.

        Memory is O(units * statistics + count * statistics), never count * shots.
        Null statistics are omitted, as in the preserved implementation.
        """
        rng = np.random.default_rng(seed)
        result = {k: [] for k, v in self.estimates().items() if v is not None}
        for iteration in range(count):
            draws = rng.integers(self.units, size=self.units)
            multiplicities = np.bincount(draws, minlength=self.units)
            values = self.estimates(multiplicities)
            for key in result:
                if values[key] is not None:
                    result[key].append(values[key])
            if progress is not None and ((iteration + 1) % 250 == 0 or iteration + 1 == count):
                progress(f'Bootstrap {iteration + 1}/{count} ({self.units} paired units)')
        return result
