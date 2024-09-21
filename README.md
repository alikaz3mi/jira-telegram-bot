# Jira Telegram Bot

This Telegram bot allows users to interact with Jira directly from a Telegram chat. Users can create Jira tasks, transition tasks, and check task statuses—all within Telegram. The bot guides users through a series of prompts to collect task details and manage tasks efficiently.

## Features

- **Create Jira Issues**: Interactively create Jira issues from within Telegram.
  - **Project Selection**: Choose the Jira project where you want to create the task.
  - **Dynamic Components and Assignees**:
    - **Components**: Fetched dynamically based on the selected project.
    - **Assignees**:
      - Checks if the project has a team by examining roles like "Developers" or "Team Members".
      - If a team exists, assignees are fetched from the team's members.
      - If no team is found, all users from Jira are fetched.
  - **Support for Priorities and Task Types**: Choose priorities and task types from selectable buttons.
  - **Sprint and Epic Selection**: Select sprints and epics for your task.
  - **Attach Images**: Upload images directly to the Jira issue.

- **Task Transitioning**: Transition tasks to different states on the Jira board.
  - **Assignee Selection**: Choose yourself as the assignee to view your tasks.
  - **Task Actions**: View task details and transition tasks to different statuses.

- **Check Task Status**: Retrieve the status and details of a specific Jira task.

- **User Authorization**: Restrict bot usage to specific Telegram users.

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
    git clone https://github.com/alikaz3mi/jira-telegram-bot.git
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
      - `TELEGRAM_ALLOWED_USERS`: List of users that are allowed to access this robot.
      - `jira_domain`: Your Jira instance URL.
      - `jira_username`: Your Jira username.
      - `jira_password`: Your Jira password or API token.

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

## Usage

### Creating a Jira Task

1. **Start the Task Creation Process:**

   Send the `/start` command in the Telegram chat.

2. **Select a Project:**

   - The bot will display a list of available Jira projects.
   - Select the project where you want to create the task.

3. **Provide Task Summary:**

   - Enter the summary of the task when prompted.

4. **Provide Task Description:**

   - Enter the description of the task, or type 'skip' to skip this step.

5. **Select a Component:**

   - Choose a component from the list provided.
   - Components are fetched dynamically from the selected project.
   - If there are no components, the bot will skip this step.

6. **Select an Assignee:**

   - Choose an assignee for the task.
   - The bot fetches assignees from the project's team:
     - Checks roles like "Developers" and "Team Members".
     - If team members are found, they are presented as options.
     - If no team is found, all Jira users are fetched as potential assignees.
   - If there are no assignees, the bot will skip this step.

7. **Select Priority:**

   - Choose a priority from the list provided.

8. **Select Sprint:**

   - Choose the current active sprint or skip this step.
   - If there is no active sprint, the bot will skip this step.

9. **Select Epic:**

   - Choose an epic from the list provided.
   - Epics are fetched from the selected project.
   - If there are no epics, the bot will skip this step.

10. **Select Task Type:**

    - Choose the type of the task (e.g., Story, Task, Bug, Sub-task).

11. **Assign to a Story (if Sub-task):**

    - If you selected 'Sub-task' as the task type, choose a story to associate the sub-task with.
    - Stories are fetched from the current sprint or project backlog.

12. **Select Story Points:**

    - Choose the story points for the task.

13. **Attach Images:**

    - Send one or more images related to the task.
    - Type 'skip' to skip this step.

14. **Task Creation Confirmation:**

    - The bot will create the task in Jira and provide a link to the new issue.

### Transitioning a Task

1. **Start the Transition Process:**

   Send the `/transition` command in the Telegram chat.

2. **Select Yourself as Assignee:**

   - Choose your name from the list of assignees.
   - The bot fetches the list of assignees dynamically.

3. **Select a Task:**

   - The bot will display a list of your assigned tasks.
   - Select the task you want to transition.

4. **View Task Details:**

   - The bot will display the task details, including the description and current status.

5. **Transition the Task:**

   - Choose the new status for the task from the available options.

6. **Confirmation:**

   - The bot will transition the task and confirm the action.

### Checking Task Status

1. **Start the Status Check:**

   Send the `/status` command in the Telegram chat.

2. **Provide Task ID:**

   - Enter the task ID (e.g., 'PROJECT-123') when prompted.

3. **View Task Status:**

   - The bot will display the task's current status and details.

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

### Environment Variables

Ensure that the environment variables in your `.env` file are correctly set. Important variables include:

- `TELEGRAM_TOKEN`: Your Telegram bot token.
- `JIRA_SERVER`: Your Jira instance URL.
- `JIRA_USERNAME`: Your Jira username.
- `JIRA_PASS`: Your Jira password or API token.
- `ALLOWED_USERS`: Comma-separated list of Telegram usernames allowed to use the bot.

### Permissions

- The bot's Jira user must have permissions to:
  - Create issues in the selected projects.
  - Browse projects.
  - Assign issues.
  - Transition issues.
  - View project roles and users.

## Troubleshooting

- **Field Not on Screen**: If you encounter errors related to fields not being on the appropriate screen, ensure that the fields are configured and available on the issue creation screen in Jira.

- **Authentication**: Ensure that your Jira credentials or API token are correct. If you're using an API token, you might need to replace your password with the token.

- **Assignee Not Found**: If the bot cannot find the assignee, check that the user exists in Jira and has the necessary permissions.

- **Permissions**: Ensure that the bot's Jira user has sufficient permissions to access project roles, users, and create issues.

- **Rate Limits**: Be aware of Jira's API rate limits when fetching large amounts of data.

## Resources

- [Telegram Bot API](https://core.telegram.org/bots/api)
- [Jira REST API Documentation](https://developer.atlassian.com/cloud/jira/platform/rest/v2/)
- [Python-Telegram-Bot Documentation](https://python-telegram-bot.readthedocs.io/en/stable/)

## Contributing

If you'd like to contribute to this project, feel free to open a pull request or submit issues.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

### Notes:

- Replace the placeholder values (`yourusername`, `your_telegram_token`, etc.) with actual values as necessary.
- Ensure that the custom field IDs used in the bot's code match those in your Jira instance.
- Make sure the bot's Jira user has the necessary permissions to access project roles and users.

---