"""Tiny unoptimized end-to-end oracle: plain lists, sets and edge exclusions."""
import math
from min_sum_oracle import Oracle


def decode(rows, probabilities, syndrome, settings):
    n = len(probabilities)
    weights = [math.log1p(-p)-math.log(p) for p in probabilities]
    if any(s and not row for row, s in zip(rows, syndrome)):
        return None, 'inconsistent_syndrome', []
    if not any(syndrome):
        return [0]*n, 'zero_syndrome', []
    frontier, guidance, hints = [], [], []
    generated = 1
    bp = None
    fields = [min(settings.clip, x) for x in weights]

    def node(pattern):
        residual = [s ^ (sum(pattern.get(i, 0) for i in row) % 2) for row, s in zip(rows, syndrome)]
        leaves = []
        for a, active in enumerate(residual):
            if not active:
                leaves.append(0.)
                continue
            costs = [weights[i]/sum(residual[b] for b, row in enumerate(rows) if i in row)
                     for i in rows[a] if i not in pattern]
            if not costs:
                return None
            leaves.append(min(costs))
        size = 1
        while size < len(leaves): size *= 2
        leaves += [0.]*(size-len(leaves))
        while len(leaves) > 1: leaves = [leaves[i]+leaves[i+1] for i in range(0,len(leaves),2)]
        key = tuple(sorted(pattern.items()))
        g = sum(weights[i] for i, bit in key if bit)
        return ((g+leaves[0],sum(residual),key), dict(pattern), residual)

    root = node({})
    if settings.max_depth and root is not None: frontier.append(root)
    for expansions, iterations in zip(settings.expansions, settings.iterations):
        capped = False
        for _ in range(expansions):
            if not frontier: break
            frontier.sort(key=lambda x: x[0]); _, parent, residual = frontier.pop(0)
            detector = next(i for i, bit in enumerate(residual) if bit)
            free = sorted((i for i in rows[detector] if i not in parent), key=lambda i: (weights[i],i))
            for k, selected in enumerate(free):
                if generated == settings.max_generated_nodes:
                    capped = True; break
                generated += 1
                pattern = {**parent, **{i:0 for i in free[:k]}, selected:1}
                correction = [pattern.get(i,0) for i in range(n)]
                if all(sum(correction[i] for i in row)%2 == s for row,s in zip(rows,syndrome)):
                    return correction,'search_goal_generated',hints
                candidate = node(pattern)
                if candidate is not None:
                    guidance.append(candidate)
                    if sum(pattern.values()) < settings.max_depth: frontier.append(candidate)
            if capped: break
        if capped: break
        if settings.bp_enabled and guidance:
            guidance.sort(key=lambda x:x[0]); _,pattern,_ = guidance.pop(0)
            hints.append(tuple(sorted(pattern.items())))
            if bp is None or not settings.warm:
                bp = Oracle(rows,n,syndrome,settings.clip,settings.alpha)
            channel = [(1-2*pattern[i])*(weights[i]+settings.margin) if i in pattern else weights[i] for i in range(n)]
            if bp.replace(channel): return bp.decision,'bp_transition_valid',hints
            for _ in range(iterations):
                if bp.step(): return bp.decision,'bp_iteration_valid',hints
            fields = bp.llrs
        if not frontier and (not settings.bp_enabled or not guidance): break
    from ldpc.hybrid_bp import Osd0Bridge
    result = Osd0Bridge(rows,n,probabilities).decode(syndrome,fields)
    return (result.correction if result.valid else None),'osd_valid' if result.valid else 'osd_invalid',hints
