"""Script to find the custom field ID for 'Root Cause' in Jira."""
from __future__ import annotations

from jira_telegram_bot import LOGGER
from jira_telegram_bot.config_dependency_injection import configure_container
from jira_telegram_bot.use_cases.interfaces.jira_data_service_interface import JiraDataServiceInterface


def main():
    """Find the custom field ID for Root Cause."""
    try:
        container = configure_container()
        jira_service = container[JiraDataServiceInterface]
        
        # Get all fields from Jira
        fields = jira_service._jira_repository.jira.fields()
        
        LOGGER.info("Searching for 'Root Cause' field...")
        
        # Find fields with 'root' or 'cause' in the name
        matching_fields = []
        for field in fields:
            name_lower = field['name'].lower()
            if 'root' in name_lower or 'cause' in name_lower:
                matching_fields.append(field)
                LOGGER.info(
                    f"Found: {field['name']} -> {field['id']} "
                    f"(Type: {field.get('schema', {}).get('type', 'N/A')})"
                )
        
        if not matching_fields:
            LOGGER.warning("No fields found with 'root' or 'cause' in the name")
            LOGGER.info("Showing all custom fields:")
            for field in fields:
                if field['id'].startswith('customfield_'):
                    LOGGER.info(f"{field['name']} -> {field['id']}")
        else:
            LOGGER.info(f"\nFound {len(matching_fields)} matching field(s)")
            LOGGER.info("\nTo use the field, update this line in jira_data_service.py:")
            for field in matching_fields:
                LOGGER.info(
                    f"  root_cause=getattr(issue.fields, '{field['id']}', None),"
                )
        
    except Exception as e:
        LOGGER.error(f"Failed to find root cause field: {e}")
        raise


if __name__ == "__main__":
    main()
