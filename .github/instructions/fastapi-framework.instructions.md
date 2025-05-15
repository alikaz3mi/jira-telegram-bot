---
mode: agent
description: Scaffold a Clean-Architecture FastAPI endpoint layer (schemas + endpoint + DI + tests) that follows all Copilot Custom Instructions
tools: [terminalLastCommand, githubRepo]
---

# 🎯 Goal  
Create every file required for a **new REST endpoint** in the `frameworks/api` layer of **jira_telegram_bot**, while **obeying** the repository’s Copilot Custom Instructions (Clean Architecture boundaries, coding style, ≥ 90 % test coverage, etc.).

# 🔄 Interactive variables  
| Variable | Purpose |
|----------|---------|
| `${input:endpoint_name_pascal:Endpoint class in PascalCase (e.g. CollectionAPIEndpoint)}` | Class/file names |
| `${input:use_case_names:Comma-separated list of Use-Case classes this endpoint calls}` | Business logic injection |
| `${input:tag:OpenAPI tag (e.g. "Collections")}` | Docs grouping |
| `${input:route_prefix:Route prefix (e.g. "/collections")}` | Base path |
| `${input:http_ops:HTTP operations in op:path format (e.g. POST:/  ,  GET:/list)}` | Routes to expose |
| `${input:permission_classes:Comma-separated permission/authorize classes (blank = none)}` | Security dependencies |

# 🛠️ Tasks  

## 1 Pydantic Schemas  
* Location: `jira_telegram_bot/entities/api_schemas/<snake_case>.py`  
* For every operation in **`http_ops`**, create request/response models.  
* Each model: single concise NumPy-style docstring, full type hints, **no inline comments**.

## 2 Endpoint class  
* Location: `jira_telegram_bot/frameworks/api/endpoints/<snake_case>.py`  
* Create the class **`${endpoint_name_pascal}(ServiceAPIEndpointBluePrint)`**.  
* Implement `create_rest_api_route` and register routes exactly as listed in `http_ops`, e.g.  
  ```python
  api_route.post("/", ...)
  api_route.get("/list", ...)
  ```  
* Inject `${use_case_names}` via Lagom DI; call them inside handler closures.  
* Add `Depends(<PermissionClass>)` for every entry in `${permission_classes}`.

## 3 Dependency-Injection wiring  
* Edit `jira_telegram_bot/config_dependency_injection.py` and `jira_telegram_bot/app_container.py` (or the designated DI file) to add:  
  ```python
  container[SubServiceEndpoints].register(container[${endpoint_name_pascal}])
  ```  
* Append the new endpoint to `jira_telegram_bot/frameworks/api/__init__.py` → `__all__`.

## 4 OpenAPI docs  
* Update `jira_telegram_bot/frameworks/api/configs/fastapi_doc.py` → `fastapi_tags_metadata`;  
  add a tag object if `${tag}` is not present.

## 5 Automated tests  
After files are generated, automatically call:  
```text
/write-unit-tests: paths=<comma_separated_new_files>
/write-integration-tests: entry='python -m uvicorn jira_telegram_bot.frameworks.api.entry_point:app --port 8000' paths=<comma_separated_new_files>
```  
so that combined coverage stays **≥ 90 %**.

## 6 Quality gates  
* Ensure `ruff`, `mypy --strict`, and `pytest -q` all succeed.  
* No `print`, no magic numbers, conforms to repo naming conventions.

# 📤 Deliverables  
* A concise **change summary** (paths created/updated).  
* **Do not** paste file contents in chat; they will be written directly to the workspace.
