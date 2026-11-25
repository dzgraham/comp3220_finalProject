"""Degree planner package, including compatibility for the original imports."""

import importlib
import sys
from types import ModuleType

from . import constraints, data


# Redirect the old module names to the current implementations.
for _name, _module in {
    "data_loader": data,
    "degree_requirements": data,
    "credit_rules": constraints,
    "prerequisites": constraints,
    "semester_rules": constraints,
    "timetable_clash": constraints,
    "selection_feasibility": constraints,
}.items():
    sys.modules[f"{__name__}.{_name}"] = _module
    globals()[_name] = _module

# Delay the planner import so `python -m csp.planner` also works normally.
full_degree_planner = ModuleType(f"{__name__}.full_degree_planner")
full_degree_planner.__getattr__ = lambda name: getattr(
    importlib.import_module(".planner", __name__), name
)
sys.modules[full_degree_planner.__name__] = full_degree_planner
