# Copilot Custom Instructions
_These guidelines apply to every suggestion Copilot makes in this repository._

---

## 1 . High‑level architecture
* **Follow Clean Architecture** boundaries exactly:
  * `entities/` ⇢ pure business objects (Pydantic models only).
  * `use_cases/` ⇢ application logic & interfaces.
  * `adapters/` and `frameworks/` ⇢ I/O, DB, HTTP, etc.
  * Never import outward: e.g., `entities` must not import `use_cases`, and `use_cases` must not import frameworks.

## 2 . Coding style
* Conform to **PEP 8** and the “Clean Code” spirit: short, intention‑revealing names and small functions/classes.
* **Inside every function: no comments.**
  * Provide **one concise docstring** (NumPy‑style) describing purpose, parameters, return type, and raised exceptions.
  * All parameters and returns **must be type‑annotated**.
* Prefer `pathlib.Path` over raw strings for paths and `datetime` with explicit time‑zones.
* Use **Lagom** for dependency injection; bindings live in `config_dependency_injection.py` and the container is created in `app_container.py`.

## 3 . Domain & settings
* **Entities** are Pydantic `BaseModel` subclasses — immutable where possible.
* **Settings** classes inherit from `pydantic_settings.BaseSettings`; keep all environment configuration in `settings/`.

## 4 . Tests
* Write tests **only with `unittest`**, located under `tests/` (mirroring package structure when practical).
* Fixtures or sample data go in `tests/samples/`.
* Aim for ≥ 90 % line coverage; favour clear Arrange‑Act‑Assert sections.

## 5 . Package layout & build
* Treat the repo as an installable package (`setup.py`, `requirements.txt`).
* Keep public exports in `jira_telegram_bot/__init__.py`.
* When adding external deps, list them in `requirements.txt` and pin minimal compatible versions (`~= ` specifier).

## 6 . Function template
Copilot, when completing a new function, use this skeleton:

```python
def example(name: str) -> str:
    """Return a polite greeting.

    Args:
        name: Person’s display name.

    Returns:
        A greeting string.
    """
    return f"Hello, {name}!"
````

*(No inline comments, full typing, single concise docstring.)*

## 7 . Things to avoid

* No `# TODO:` comments in committed code; open an issue instead.
* Do not use `print` for logging — rely on `LOGER` configured in `__init__`.
* Skip magic numbers/strings — extract to `constants.py` or Enum.
* If function length is longer than 30 lines, it means that the function must break down to multiple functions.
* Avoid using too many chained if statements. Each if statement must be a function

---

**Remember:** Suggestions that violate any rule above should be suppressed or rewritten automatically.
