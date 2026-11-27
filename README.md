# COMP3220: AI-Based Degree Planner

A CSP algorithm that uses backtracking and MRV (Minimum Remaining Value) to select courses and assign them to
semesters. It targets **93 credits**: 24 Level 1 credits, 60 Level 2/3 credits, and 9 foundation credits.
If a full degree cannot be completed, it keeps a verified partial plan when
available and reports the missing requirements.

Requires **Python 3.10+**. No third-party packages are needed.

## Run

Run commands from the project root:

```powershell
# Computer Science without math courses (partial with the supplied catalogue)
python csp_solver.py

# AI & Data Science with an optional math track
python csp_solver.py --major computer_science --track ai_data --math-track calculus

# Specialization tracks are available with any major
python csp_solver.py --major computer_science --track web_systems --math-track statistics

# All command-line options
python csp_solver.py --help
```

| Major | `--major` value |
| --- | --- |
| Computer Science (default) | `computer_science` |
| Information Technology | `information_technology` |
| Cybersecurity | `cybersecurity` |
| Software Engineering | `software_engineering` |

Majors determine compulsory courses and degree elective requirements. Specialization
tracks are shared by all majors and prioritize electives without changing compulsory
requirements. The planner loads majors, tracks, and math tracks from `tracks2.json`.

`--math-track` is optional and independent of `--track`. Choices are `linear_algebra`,
`statistics`, `calculus`, `abstract_algebra`, and `discrete_math`. Selecting one enables
MATH and STAT courses, including prerequisites, and prioritizes that track's electives.
Preferences remain subject to prerequisites, credit requirements, and timetable limits.
Without a math track, MATH and STAT courses are excluded from full and partial plans.
Required Computing courses such as COMP1210 and COMP2201 remain compulsory.

The supplied catalogue contains only 15 non-foundation, non-math Level 1 credits,
so a plan without math is at least 9 Level 1 credits short of the 24-credit target.
The planner reports a partial degree instead of adding math automatically. The default
Computer Science plan schedules 84 credits and exits with code 1. Additional eligible
Level 1 courses in the catalogue would be needed to complete it without math.

Software Engineering needs departmental approval for `COMP3911`; use
`--approved-courses COMP3911` when approved. `--include-summer` adds Semester 3
to each planning year. The CLI shows unused terms as "No courses assigned";
summer availability does not require the planner to put courses there.

## Integration

```python
from csp_solver import generate_full_degree_plan

result = generate_full_degree_plan(
    major="computer_science", track="ai_data", math_track="calculus",
    years=3, max_nodes=20000
)

for semester, courses in result["plan"].items():
    print(semester, courses)

print(result["status"], result["credit_shortfall"])
```

Optional arguments include `math_track`, `include_summer`, `approved_courses`, and
`allow_unknown`. Planning starts from the beginning of the degree.

## Results

- `complete` and `success`: true only when every degree requirement is met.
- `verified`: the returned schedule passes its semester constraints.
- `status`: `confirmed` or `tentative` for a complete degree, `partial` for a
  valid incomplete plan, or `infeasible` / `limit_reached` when no plan is returned.
- `missing_courses`, `missing_credits`, `credit_shortfall`, and
  `unsatisfied_requirements`: what is still needed.
- `nodes_explored`, `backtracks`, and `execution_time`: search statistics.
- `major`, `track`, and `math_track`: selected planning options; omitted tracks are `None`.

Unknown times remain flagged in `tentative_courses` and `timetable_status`.
Use `--strict-timetable` or `allow_unknown=False` to reject them. The supplied
foundation courses have unknown times, so full plans are tentative.

All searches share the node budget. `full_search_status` describes the full-degree
attempt; reaching a limit does not prove impossibility. A limited search may
return a partial plan or no plan, and does not guarantee the largest partial
schedule. The CLI exits with code 1 when the degree is incomplete.

## Project structure

| Module | Purpose |
| --- | --- |
| `csp/data.py` | Load datasets and degree requirements |
| `csp/constraints.py` | Prerequisites, credits, offerings, and timetable checks |
| `csp/course_selection.py` | Backtracking course selection |
| `csp/solver.py` | Semester assignment and partial fallback |
| `csp/planner.py` | Coordinate searches, verify results, and display CLI output |
| `csp/search.py` | Shared budget and statistics |
| `csp_solver.py` | Public import and command-line launcher |

## Tests

```powershell
python -m unittest discover -s tests -v
python -m unittest discover -s tests/unit -v
python -m unittest discover -s tests/integration -v
```

Shared sample data is in `tests/helpers.py`. Tests cover degree requirements,
backtracking, timetable rules, partial fallbacks, and full 93-credit generation.
