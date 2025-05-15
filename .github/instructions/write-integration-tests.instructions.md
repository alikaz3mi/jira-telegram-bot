---
mode: agent
description: Create integration & concurrency tests with ≥ 90 % coverage
tools: [terminalLastCommand, githubRepo, testFailure]
---

# 🌐 Scope  
End-to-end tests across service API, DB, brokers, external APIs, incl. load/concurrency (e.g. 50 parallel requests).

# ✅ Checklist  
- Use real services via Docker Compose or testcontainers-python.  
- Start deps in `setUpClass` / `setUpModule`, tear down afterwards.  
- Place files in `tests/integration/`, prefixed `test_`.  
- Cover happy paths, failure modes, and race conditions.  
- Assert overall coverage ≥ 90 %; export JUnit & HTML reports to `reports/`.
- Make sure that all tests are passed

# 🏗️ Steps  
1. Ask for entry command if unknown: `${input:entry:Entrypoint cmd}`.  
2. Parse or create a minimal `docker-compose.yml`.  
3. Draft a **concurrency scenario**, e.g.:

   ```python
   async with aiohttp.ClientSession() as s:
       tasks = [asyncio.create_task(s.post("/payments", json=payload))
                for _ in range(50)]
       results = await asyncio.gather(*tasks)
       assert all(r.status == 200 for r in results)
   ```

4. For each public endpoint/use-case, write:  
   * Happy-path test  
   * Failure-mode test  
   * Concurrency/load test (if applicable)  
5. Add a `Makefile` target `integration-tests` that:

   ```
   docker compose up -d
   pytest tests/integration -n auto --cov --cov-report=xml:reports/coverage.xml \
          --junitxml=reports/junit.xml
   docker compose down
   ```

# 📜 Output  
* New/updated `tests/integration/test_*.py` files  
* Helper scripts / Docker Compose snippets  
* `README.md#Integration Tests` section with run instructions
