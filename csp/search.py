# One search budget and comparable statistics for both CSP stages.

from time import perf_counter


class SearchBudget:
    def __init__(self, max_nodes=20000):
        if not isinstance(max_nodes, int) or isinstance(max_nodes, bool) or max_nodes < 1:
            raise ValueError("max_nodes must be a positive integer")
        self.max_nodes = max_nodes
        self.started = perf_counter()
        self.limit_reached = False

        # Both search stages spend the same budget, but keep separate counts.
        self.nodes = {"selection": 0, "scheduling": 0}
        self.backtracks = {"selection": 0, "scheduling": 0}
        self.pruned_branches = 0
        self.selection_attempts = 0
        self.scheduling_attempts = 0

    def step(self, phase):
        # Count one choice, or return False when the node budget is used up
        # Stop before counting a choice that would go past the limit.
        if sum(self.nodes.values()) >= self.max_nodes:
            self.limit_reached = True
            return False
        
        self.nodes[phase] += 1
        
        return True

    def snapshot(self):
        # Report the totals and the contribution from each search stage.
        return {
            "nodes_explored": sum(self.nodes.values()),
            "backtracks": sum(self.backtracks.values()),
            "selection_nodes": self.nodes["selection"],
            "scheduling_nodes": self.nodes["scheduling"],
            "selection_backtracks": self.backtracks["selection"],
            "scheduling_backtracks": self.backtracks["scheduling"],
            "pruned_branches": self.pruned_branches,
            "selection_attempts": self.selection_attempts,
            "scheduling_attempts": self.scheduling_attempts,
            "limit_reached": self.limit_reached,
            "execution_time": perf_counter() - self.started
        }
