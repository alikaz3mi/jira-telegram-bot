---
mode: agent
description: Generate high-coverage unittest files (≥ 90 %) for selected Python modules
---

# 🎯 Goal  
Produce/extend tests so project-wide line coverage is at least 90 % while following the rules below.

# 📜 Rules (verbatim)
```
## 4 . Tests
* Write tests only with `unittest`, located under `tests/` (mirroring package structure when practical).
* Main tests for use cases are in `tests/use_cases`
* Fixtures or sample data go in `tests/samples/`.
* Aim for ≥ 90 % line coverage; favour clear Arrange-Act-Assert sections.
* Test each use case thoroughly
* Test both sync and async methods
* Use factories for test data
* Mock external dependencies
* Test files are prefixed with `test_`
* Test classes are prefixed with `Test`
* Test functions are prefixed with `test_`
* Asynchronous test functions are prefixed with `test_a`
```

# 🚦 Workflow  
1. Ask (if nothing selected): `${input:paths:Modules/folders to cover?}`  
2. Mirror each target under `tests/unit_tests/…`, e.g. `pkg/foo.py` → `tests/unit_tests/pkg/test_foo.py`.  
3. Add `Test<ClassName>` suites and free-function tests.  
4. For async code use `IsolatedAsyncioTestCase` and prefix with `test_a_…`.  
5. Mock I/O, network, DB and external calls.  
6. Drop sample fixtures in `tests/samples/` as needed.  
7. Output new or updated test files plus a brief coverage summary.
