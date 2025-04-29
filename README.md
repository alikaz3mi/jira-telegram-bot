<p align="center">
   <img src="docs/image.png" alt="Jira Telegram Bot" width="50%">
</p>

A powerful Telegram bot that integrates with Jira to streamline task management through chat interface. This bot enables creating, tracking, and managing Jira tasks directly from Telegram, with support for advanced features like AI-powered task breakdown and voice commands.

## Key Features

### Task Management
- **Interactive Task Creation**: Create Jira issues through guided conversations
- **Advanced Task Creation**: AI-powered task breakdown for complex projects
- **Voice Commands**: Support for voice messages with automatic transcription
- **Task Tracking**: Monitor task status and receive notifications
- **Workflow Management**: Transition tasks between different states
- **Media Support**: Attach images, documents, and other media to tasks

### Smart Features
- **AI Integration**: Uses GPT models for task analysis and breakdown
- **Voice Processing**: Converts voice messages to task descriptions
- **Smart Notifications**: Get alerts for deadlines and status changes
- **Multilingual Support**: Handles both English and Persian text

### Project Management
- **Sprint Management**: Integrate with Agile sprints
- **Epic Linking**: Connect tasks to epics
- **Component Management**: Organize tasks by components
- **Release Management**: Track versions and releases
- **Custom Fields**: Support for Jira custom fields

### Team Collaboration
- **User Assignment**: Smart assignee suggestions
- **Team Communication**: Task comments and notifications
- **Permission Control**: Role-based access control
- **Group Chat Support**: Manage tasks in group conversations

## Setup

### Prerequisites
- Python 3.11 or higher
- Telegram Bot Token (from [@BotFather](https://t.me/botfather))
- Jira account with API access
- Optional: OpenAI API key for AI features

### Installation

1. **Clone and Install**
   ```bash
   git clone https://github.com/alikaz3mi/jira-telegram-bot.git
   cd jira-telegram-bot
   python -m venv venv
   source venv/bin/activate  # or 'venv\\Scripts\\activate' on Windows
   pip install -e .
   ```

2. **Configure Environment**
   - Copy sample.env to .env
   - Configure required settings:
     ```
     TELEGRAM_TOKEN=your_bot_token
     TELEGRAM_HOOK_TOKEN=your-token
     JIRA_DOMAIN=https://your-jira-instance.com
     JIRA_USERNAME=your_username
     JIRA_PASSWORD=your_token_or_password
     ```

3. **Run the Bot**
   ```bash
   python -m jira_telegram_bot
   ```

### Docker Deployment
```bash
# Build and run using Docker Compose
docker-compose up -d
```

The docker-compose.yml file includes all necessary configurations and environment variables for running the bot in a containerized environment.

## Usage

### Authentication
Only users defined in the user settings configuration (`settings/user_config.json`) are authorized to use the bot. This restriction ensures secure access control and proper task management attribution.

### Basic Commands
- `/create_task` - Start creating a new task (supports recursive creation)
- `/advanced_task` - Create multiple related tasks with AI assistance (supports voice input)
- `/transition` - Change task status
- `/status` - Check task status
- `/summary_tasks` - Get board summary
- `/setting` - Configure user preferences
- `/help` - Show command list

### Creating Tasks
1. Start with `/create_task`
2. Select project from the list
3. Enter task summary and description
4. Choose component(s)
5. Select assignee
6. Set priority, sprint, and epic
7. Add attachments if needed
8. Choose to create another task (recursive creation) or finish

### Advanced Task Creation
1. Use `/advanced_task`
2. Select project
3. Provide task details through:
   - Text description
   - Voice message (automatically transcribed)
4. Review AI-generated task breakdown
5. Confirm task creation

### Task Transitions
1. Use `/transition`
2. Select the task
3. Choose new status
4. Add transition comment if needed

## Configuration

### Custom Fields
Configure custom field IDs in your environment:
```
JIRA_EPIC_LINK_ID=customfield_10100
JIRA_SPRINT_ID=customfield_10104
JIRA_STORY_POINTS_ID=customfield_10106
```

### User Settings
- Configure default projects
- Set preferred components
- Define custom task templates
- Configure notification preferences

## Troubleshooting

### Common Issues
- **Authentication Errors**: Verify Jira credentials and API token
- **Permission Issues**: Check Jira user permissions
- **Field Errors**: Ensure custom fields are properly configured
- **Rate Limits**: Monitor API usage limits

### Logs
- Check `cron.log` for scheduled tasks
- Enable debug logging in settings

## Contributing
1. Fork the repository
2. Create feature branch
3. Commit changes
4. Submit pull request

## License
This project is licensed under the MIT License - see LICENSE file for details.

## Credits
- Built with [python-telegram-bot](https://python-telegram-bot.org/)
- Uses [jira-python](https://jira.readthedocs.io/)
- AI features powered by OpenAI/Gemini