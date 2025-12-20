"""Helper script to find the delay_reason custom field ID in Jira."""
from jira_telegram_bot import LOGGER
from jira_telegram_bot.config_dependency_injection import configure_container
from jira_telegram_bot.use_cases.interfaces.jira_data_service_interface import JiraDataServiceInterface


def main():
    """Find the custom field ID for delay_reason."""
    try:
        container = configure_container()
        jira_service = container[JiraDataServiceInterface]
        
        # Get all fields from Jira
        fields = jira_service._jira_repository.jira.fields()
        
        LOGGER.info("Searching for 'delay_reason' or 'delay' field...")
        
        # Find fields with 'delay' in the name
        matching_fields = []
        for field in fields:
            name_lower = field['name'].lower()
            if 'delay' in name_lower:
                matching_fields.append(field)
                LOGGER.info(
                    f"Found: {field['name']} -> {field['id']} "
                    f"(Type: {field.get('schema', {}).get('type', 'N/A')})"
                )
        
        if not matching_fields:
            LOGGER.warning("No fields found with 'delay' in the name")
            LOGGER.info("\nShowing all custom fields (first 50):")
            custom_count = 0
            for field in fields:
                if field['id'].startswith('customfield_'):
                    LOGGER.info(f"{field['name']} -> {field['id']}")
                    custom_count += 1
                    if custom_count >= 50:
                        break
        else:
            LOGGER.info(f"\nFound {len(matching_fields)} matching field(s)")
            LOGGER.info("\nTo use the field, add these lines:")
            for field in matching_fields:
                LOGGER.info(f"\n# In JiraServerRepository __init__:")
                LOGGER.info(f"  self.jira_delay_reason_id = '{field['id']}'")
                LOGGER.info(f"\n# In jira_data_service.py:")
                LOGGER.info(f"  delay_reason=getattr(issue.fields, '{field['id']}', None),")
        
    except Exception as e:
        LOGGER.error(f"Failed to find delay_reason field: {e}")
        raise


if __name__ == "__main__":
    main()
