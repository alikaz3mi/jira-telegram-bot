# JiraCloudRepository cannot be instantiated

## What happens

`JiraCloudRepository` does not implement six abstract methods of
`TaskManagerRepositoryInterface`:

- `get_time_tracking`
- `get_user_actionable_tasks`
- `get_user_upcoming_tasks`
- `get_worklog_data`
- `log_work`
- `set_delay_reason`

Python refuses to instantiate an abstract class, so constructing it raises:

```
TypeError: Can't instantiate abstract class JiraCloudRepository without an
implementation for abstract methods 'get_time_tracking', ...
```

## Why it matters

`config_dependency_injection.py:433` selects this class whenever
`JiraConnectionSettings.connection_type` is `CLOUD`:

```python
container[TaskManagerRepositoryInterface] = Singleton(
    lambda c: JiraCloudRepository(c[JiraConnectionSettings])
    if c[JiraConnectionSettings].connection_type == JiraConnectionType.CLOUD
    else JiraServerRepository(c[JiraConnectionSettings]),
)
```

So a Cloud deployment fails at container build, not at the first call. This
instance runs Jira Server, which is why nobody has hit it.

## How it was found

`tests/integration/adapters/repositories/jira/test_jira_cloud_repository.py`
errored in `setUpClass`. Two other faults hid this one: the test read an env
file that was never committed, and line 188 referenced a bare `JIRA_SETTINGS`
that does not exist — so the file had never run to completion. Both are fixed;
the test now skips with the missing method names in its reason.

## What to do

Implement the six methods against the Jira Cloud REST API, then remove the
skip guard in `setUpClass`. The Server implementations in
`jira_server_repository.py` are the reference, but the worklog and
time-tracking endpoints differ between Server and Cloud — they need checking
against Cloud's API rather than copying.

Until then the skip is honest: it names the production gap rather than
reporting a broken test.
