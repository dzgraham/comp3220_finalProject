# Public interface and command-line launcher for the CSP planner.
from csp.planner import generate_full_degree_plan, main

__all__ = ["generate_full_degree_plan"]

if __name__ == "__main__":
    raise SystemExit(main())
