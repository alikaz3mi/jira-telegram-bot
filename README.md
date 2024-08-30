# Jira Telegram Bot

This Telegram bot allows users to create Jira tasks directly from a Telegram chat. The bot guides users through a series of prompts to collect task details, such as summary, description, component, assignee, priority, sprint, epic, and task type. Users can also attach images to the task, which are then added to the Jira issue.

In addition, the bot now supports transitioning Jira tasks to different states within the Jira board, allowing users to manage their workflow directly from Telegram.

## Features

- **Create Jira Issues**: Interactively create Jira issues from within Telegram.
- **Task Transitioning**: Transition tasks to different states on the Jira board.
- **Support for Components, Assignees, and Priorities**: Choose components, assignees, and priorities from selectable buttons.
- **Sprint and Epic Selection**: Select sprints and epics for your task.
- **Attach Images**: Upload images directly to the Jira issue.
- **User Authorization**: Restrict task creation and transitions to specific Telegram users.
- **Custom Field Support**: Configure and set custom Jira fields such as Epic Link and Sprint.

## Setup

### Prerequisites

- Python 3.8+
- A Telegram bot token. [Create a bot with BotFather](https://core.telegram.org/bots#botfather).
- Jira account with appropriate permissions to create issues and manage task transitions.
- Basic understanding of Jira's REST API.

### Installation

1. **Clone the repository:**
    ```bash
    git clone https://github.com/yourusername/jira-telegram-bot.git
    cd jira-telegram-bot
    ```

2. **Install dependencies:**
    Create a virtual environment and install the necessary Python packages:
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    pip install -e .
    ```

3. **Configure environment variables:**

   Use the `sample.env` file provided as a template to create your `.env` file:
   1. Rename `sample.env` to `.env`.
   2. Fill in the following variables in your `.env` file:
      - `TELEGRAM_TOKEN`: Your Telegram bot token.
      - `JIRA_SERVER`: Your Jira instance URL.
      - `JIRA_USERNAME`: Your Jira username.
      - `JIRA_PASS`: Your Jira password or API token.
      - `JIRA_PROJECT_KEY`: The key of the Jira project where issues will be created.
      - `JIRA_BOARD_PROJECT_NAME`: Name of the board in Jira.
      - `JIRA_BOARD_ASSIGNEES`: Comma-separated list of assignees of interest.
      - `ALLOWED_USERS`: Comma-separated list of Telegram usernames allowed to create tasks and transition them.

4. **Run the bot:**

   Start the bot by running the following command:

    ```bash
    python jira_telegram_bot
    ```

### Docker Setup (Optional)

If you prefer to run the bot in a Docker container, you can use the provided Dockerfile and docker-compose configuration.

1. **Build the Docker image:**

    ```bash
    docker build -t jira-telegram-bot .
    ```

2. **Run the container:**

    ```bash
    docker run -d --name jira-bot jira-telegram-bot
    ```

3. **Using Docker Compose:**

    Start the service:
    ```bash
    docker-compose up -d
    ```

## Configuration

### Custom Fields

To set custom fields like `Epic Link` and `Sprint`, you need to find their custom field IDs from your Jira instance. You can use the following methods:

1. **Jira REST API:**
   Use the following endpoint to retrieve all custom fields:

   ```
   GET https://your-jira-instance.com/rest/api/2/field
   ```

2. **Jira UI:**
   Navigate to Jira Admin > Issues > Custom Fields to find the custom field IDs.

   For more details, refer to the [Jira REST API documentation](https://developer.atlassian.com/cloud/jira/platform/rest/v2/).

### Troubleshooting

- **Field not on screen**: If you encounter errors related to fields not being on the appropriate screen, ensure that the fields are configured and available on the issue creation screen in Jira.

- **Authentication**: Ensure that your Jira credentials or API token are correct. If you're using an API token, you might need to replace your password with the token.

## Task Transition

### Overview

The task transition feature allows users to select themselves as an assignee, view their tasks, and transition a selected task to another state on the Jira board.

### Usage

1. **Start the Transition Process**: Send the `/transition` command in the Telegram chat.
2. **Select Assignee**: Choose your name from the list of assignees.
3. **View Tasks**: After selecting yourself, you will see a list of your tasks along with their priorities.
4. **View Task Details**: Select a task to view its details, including the description and current status.
5. **Transition the Task**: You can either return to select another task or choose to continue and transition the task to another state (e.g., from "To Do" to "In Progress").

This feature streamlines the task management process, enabling you to handle Jira tasks directly from your Telegram bot.

## Resources

- [Telegram Bot API](https://core.telegram.org/bots/api)
- [Jira REST API Documentation](https://developer.atlassian.com/cloud/jira/platform/rest/v2/)
- [Python-Telegram-Bot Documentation](https://python-telegram-bot.readthedocs.io/en/stable/)

## Contributing

If you'd like to contribute to this project, feel free to open a pull request or submit issues.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

### Notes:
- Replace the placeholder values (`your_telegram_token`, `your_username`, etc.) with actual values as necessary.