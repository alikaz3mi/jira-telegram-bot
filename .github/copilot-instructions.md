# Copilot Custom Instructions
_These guidelines apply to every suggestion Copilot makes in this repository._

---

## 1 . High‑level architecture
* **Follow Clean Architecture** boundaries exactly, located in `jira_telegram_bot` directory:
  * `entities/` ⇢ pure business objects (Pydantic models only).
  * `use_cases/` ⇢ application logic & interfaces.
  * `use_cases/interfaces`: Interfaces (class names must end with 'Interface', e.g., `RepositoryInterface`)
  * `adapters/` and `frameworks/` ⇢ I/O, DB, HTTP, etc.
  * Never import outward: e.g., `entities` must not import `use_cases`, and `use_cases` must not import frameworks.
  * prompts must be located in `adapters/ai_models/ai_agents/prompts`

## 2 . Coding style
* Conform to **PEP 8** and the “Clean Code” spirit: short, intention‑revealing names and small functions/classes.
* **Inside every function: no comments.**
  * Provide **one concise docstring** (NumPy‑style) describing purpose, parameters, return type, and raised exceptions.
  * All parameters and returns **must be type‑annotated**.
* Prefer `pathlib.Path` over raw strings for paths and `datetime` with explicit time‑zones.
* Use **Lagom** for dependency injection; bindings live in `config_dependency_injection.py` and the container is created in `app_container.py`. Dependencies flow inward (frameworks -> adapters -> use cases -> entities)

### Naming Conventions
* Use **snake_case** for:
  * Variable names: `user_count`, `total_items`
  * Function names: `calculate_total()`, `get_user_data()`
  * Module names: `data_processor.py`, `error_handler.py`
* Use **PascalCase** (CapWords) for:
  * Class names: `UserProfile`, `DatabaseConnection`
  * Exception names: `ValidationError`, `DatabaseConnectionError`
* Use **SCREAMING_SNAKE_CASE** for:
  * Constants: `MAX_CONNECTIONS`, `DEFAULT_TIMEOUT`
  * Environment variables: `DATABASE_URL`, `API_KEY`
* Use **lowercase** with underscores for:
  * File names: `user_service.py`, `test_validation.py`
  * Package names: `jira_telegram_bot`, `data_services`


## 3 . Domain & settings
* **Entities** are Pydantic `BaseModel` subclasses — immutable where possible.
* **Settings** classes inherit from `pydantic_settings.BaseSettings`; keep all environment configuration in `settings/`. Settings must be injected to class via dependency injection. 

## 4 . Tests
* Write tests **only with `unittest`**, located under `tests/` (mirroring package structure when practical).
* Main tests for use cases are in `tests/use_cases`
* Fixtures or sample data go in `tests/samples/`.
* Aim for ≥ 90 % line coverage; favour clear Arrange‑Act‑Assert sections.
* Test each use case thoroughly
* Test both sync and async methods
* Use factories for test data
* Mock external dependencies
* Test files are prefixed with `test_`
* Test classes are prefixed with `Test`
* Test functions are prefixed with `test_`
* Asynchronous test functions are prefixed with `test_a`

#### Testing Patterns
- Arrange-Act-Assert pattern
- Fixture-based test setup
- Mocking external dependencies
- Test both success and failure cases
- Use factories for test data creation

## 5 . Package layout & build
* Treat the repo as an installable package (`setup.py`, `requirements.txt`).
* Keep public exports in `jira_telegram_bot/__init__.py`.
* When adding external deps, list them in `requirements.txt` and pin minimal compatible versions (`~= ` specifier).

## 6 . Working with Use Cases

Use cases represent the core application logic and should:
- Be independent of UI, database, or external frameworks
- Have clear inputs and outputs
- Implement specific business flows
- Be thoroughly tested

## 7 . Error Handling

- Custom exceptions are defined in `jira_telegram_bot/utils/exceptions.py`
- Use specific exception types for different error scenarios
- Properly handle and propagate errors through layers


## 8 . Asynchronous Programming

- The project uses async/await patterns extensively
- Use asynchronous methods where appropriate
- Both sync and async versions of methods are provided where needed
- Properly manage and clean up async resources


## 7 . Function template

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
```

*(No inline comments, full typing, single concise docstring.)*

## 8. Prompt Template. 

Always write prompts in this template:

```python
class StructuredPromptSpec:
    prompt: str = Field()
    schemas: List[ResponseSchema] = Field()
    format_instructions: str = Field(
        description="The output of parser.get_format_instructions()"
    )
    template: PromptTemplate = Field(
        description="Runnable used at the beginning of the chain."
    )
    parser: StructuredOutputParser = Field(
        description="Runnable used at the end of the chain."
    )
```

Then, when creating the chain in the related class in `ai_agents`, import it, and create the chain. I.e `chain = SamplePrompt.prompt | llm | SamplePrompt.parser`

## 9 . Things to avoid
* No `# ` comments in committed code; open an issue instead.
* Never use `print` for logging — rely on `LOGGER` configured in `__init__`.
* Skip magic numbers/strings — extract to `constants.py` or Enum. And must be in entities 
* If function length is longer than 30 lines, it means that the function must break down to multiple functions.
* Avoid using too many chained if statements. Each if statement must be a function.
* Everything dependencies must be imported in the beginning of the script.

---  

**Remember:** Suggestions that violate any rule above should be suppressed or rewritten automatically.
