"""Literal edge-exclusion oracle: independent of the production two-minimum kernel."""
import math


class Oracle:
    def __init__(self, rows, n, syndrome, clip, alpha):
        self.rows, self.n, self.s, self.clip, self.alpha = rows, n, syndrome, clip, alpha
        self.edges = [(a, i) for a, row in enumerate(rows) for i in row]
        self.z = {edge: 0. for edge in self.edges}
        self.q = {}
        self.iterations = 0

    def clipped(self, value):
        return max(-self.clip, min(self.clip, value)) + 0.

    def replace(self, fields):
        self.fields = list(fields)
        self.sums = [fields[i] + sum(self.z[a, i] for a, row in enumerate(self.rows) if i in row)
                     for i in range(self.n)]
        self.llrs = [self.clipped(x) for x in self.sums]
        self.q = {(a, i): self.clipped(self.sums[i] - self.z[a, i]) for a, i in self.edges}
        self.decision = [int(x <= 0) for x in self.llrs]
        return self.valid()

    def valid(self):
        return all(sum(self.decision[i] for i in row) % 2 == self.s[a] for a, row in enumerate(self.rows))

    def step(self):
        if self.valid():
            return True
        old = self.q.copy()
        for a, i in self.edges:
            others = [old[a, j] for j in self.rows[a] if j != i]
            if not others:
                self.z[a, i] = (-1)**self.s[a] * self.clip
            else:
                sign = (-1)**(self.s[a] + sum(x < 0 for x in others))
                self.z[a, i] = self.clipped(self.alpha * sign * min(map(abs, others)))
        self.iterations += 1
        return self.replace(self.fields)
