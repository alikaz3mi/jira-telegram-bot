import aiohttp
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    CommandHandler,
    MessageHandler,
    filters,
    CallbackContext,
    Application,
    ConversationHandler,
    CallbackQueryHandler,
)
from jira import JIRA
from io import BytesIO

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Telegram bot token and Jira credentials
TELEGRAM_TOKEN = "7434072786:AAHXpfT9QTMf2H8rhlh9k8TpbsZrYDvFmiM"
JIRA_SERVER = "https://jira.parstechai.com"
JIRA_USERNAME = "a_kazemi"
JIRA_PASS = "a_kazemi"
JIRA_PROJECT_KEY = "PARSCHAT"

ALLOWED_USERS = ["Mousavi_Shoushtari", "alikaz3mi", "GroupAnonymousBot"]

# Initialize JIRA client
jira = JIRA(server=JIRA_SERVER, basic_auth=(JIRA_USERNAME, JIRA_PASS))

# Define states
(
    SUMMARY,
    DESCRIPTION,
    COMPONENT,
    ASSIGNEE,
    PRIORITY,
    SPRINT,
    EPIC,
    TASK_TYPE,
    STORY_POINTS,
    IMAGE,
) = range(10)

epics = list(
    epic
    for epic in jira.search_issues(
        f'project={JIRA_PROJECT_KEY} AND issuetype=Epic AND status in ("To Do", "In Progress")'
    )
)
for board in jira.boards():
    if JIRA_PROJECT_KEY in board.name:
        board_id = board.id
        break

sprints = jira.sprints(board_id=board_id)  # Assuming board_id=1, adjust as necessary
try:
    latest_sprint = next(sprint for sprint in sprints if sprint.state == "active")
except Exception as e:
    logger.error(f"No sprint is active: {e}.")
    latest_sprint = sprints[-1]
priorities = jira.priorities()
task_types = [z.name for z in jira.issue_types_for_project(JIRA_PROJECT_KEY)]
story_points_values = [0.5, 1, 1.5, 2, 2.5, 3, 3.5, 4.0, 7]


async def check_user_allowed(update: Update) -> bool:
    user_id = update.message.from_user.username
    chat_type = update.message.chat.type
    if user_id not in ALLOWED_USERS:
        await update.message.reply_text(
            f"{user_id}: You are not authorized to create tasks."
        )
        logger.info(f"Unauthorized user: {user_id} in chat type: {chat_type}")
        return False
    return True


async def start(update: Update, context: CallbackContext) -> int:
    if not await check_user_allowed(update):
        return ConversationHandler.END
    await update.message.reply_text(
        "Hi! Send me the summary of the task. Type /help for more instructions."
    )
    logger.info(
        f"Starting task creation process in chat type: {update.message.chat.type}"
    )
    return SUMMARY


async def help_command(update: Update, context: CallbackContext) -> None:
    help_text = (
        "Here's how to use this bot to create a Jira task:\n\n"
        "1. **/start**: Start the process of creating a new task.\n"
        "2. **Summary**: Send the summary of the task when prompted.\n"
        "3. **Description**: Send the description of the task when prompted, or type 'skip' to skip this step.\n"
        "4. **Component**: Choose the component for the task from the list provided.\n"
        "5. **Assignee**: Choose an assignee for the task from the list provided, or type 'skip' to skip.\n"
        "6. **Priority**: Choose a priority for the task from the list provided, or type 'skip' to skip.\n"
        "7. **Sprint**: Choose the sprint or backlog for the task.\n"
        "8. **Epic**: Choose an epic for the task from the list provided, or type 'skip' to skip.\n"
        "9. **Task Type**: Choose the type of the task.\n"
        "10. **Image**: Send one or more images related to the task.\n\n"
        "The bot will then create a new Jira task with the provided details and attach the images to the task."
    )
    await update.message.reply_text(help_text)
    logger.info("Displayed help information")


async def terminate(update: Update, context: CallbackContext) -> int:
    await update.message.reply_text("Task creation process terminated.")
    logger.info("Task creation process terminated")
    return ConversationHandler.END


async def add_summary(update: Update, context: CallbackContext) -> int:
    if not await check_user_allowed(update):
        return ConversationHandler.END
    user = update.message.from_user
    logger.info("User %s sent a summary: %s", user.first_name, update.message.text)

    task_summary = update.message.text
    context.user_data["task_summary"] = task_summary
    await update.message.reply_text(
        'Got it! Now send me the description of the task (or type "skip" to skip).'
    )
    logger.info("Summary received: %s", task_summary)
    return DESCRIPTION


async def add_description(update: Update, context: CallbackContext) -> int:
    if not await check_user_allowed(update):
        return ConversationHandler.END
    task_description = update.message.text

    if task_description.lower() == "skip":
        task_description = None

    context.user_data["task_description"] = task_description
    logger.info("Description received: %s", task_description)

    # Fetch components from Jira
    components = jira.project_components(JIRA_PROJECT_KEY)
    keyboard = []
    for i in range(0, len(components), 2):
        row = []
        if i < len(components):
            row.append(
                InlineKeyboardButton(
                    components[i].name, callback_data=components[i].name
                )
            )
        if i + 1 < len(components):
            row.append(
                InlineKeyboardButton(
                    components[i + 1].name, callback_data=components[i + 1].name
                )
            )
        keyboard.append(row)

    keyboard.append([InlineKeyboardButton("Skip", callback_data="skip")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Got it! Now choose a component from the list below:", reply_markup=reply_markup
    )
    logger.info("Components listed")
    return COMPONENT


async def button_component(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    await query.answer()
    component = query.data

    if component == "skip":
        component = None

    context.user_data["component"] = component
    logger.info("Component selected: %s", component)

    # Present assignees as inline buttons
    assignees = [
        "O_Sadeghnezhad",
        "m_fouladpanah",
        "ah_ahmadi",
        "z_lotfian",
        "k_korminejad",
        "a_janloo",
        "m_Mousavi",
        "p_etemad",
        "a_kazemi",
        "M_samei",
    ]
    keyboard = []
    for i in range(0, len(assignees), 4):
        row = [
            InlineKeyboardButton(assignee, callback_data=assignee)
            for assignee in assignees[i : i + 4]
        ]
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("Skip", callback_data="skip")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        "Got it! Now choose an assignee from the list below:", reply_markup=reply_markup
    )
    logger.info("Assignees listed")
    return ASSIGNEE


async def button_assignee(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    await query.answer()
    assignee = query.data

    if assignee == "skip":
        assignee = None

    context.user_data["assignee"] = assignee
    logger.info("Assignee selected: %s", assignee)

    # Present priorities as inline buttons
    keyboard = [
        [
            InlineKeyboardButton(priority.name, callback_data=priority.name)
            for priority in priorities[i : i + 3]
        ]
        for i in range(0, len(priorities), 3)
    ]
    keyboard.append([InlineKeyboardButton("Skip", callback_data="skip")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        "Got it! Now choose a priority from the list below:", reply_markup=reply_markup
    )
    logger.info("Priorities listed")
    return PRIORITY


async def button_priority(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    await query.answer()
    priority = query.data

    if priority == "skip":
        priority = None

    context.user_data["priority"] = priority
    logger.info("Priority selected: %s", priority)

    # Present sprints as inline buttons
    keyboard = [
        [InlineKeyboardButton(latest_sprint.name, callback_data=str(latest_sprint.id))],
        [InlineKeyboardButton("Skip", callback_data="skip")],
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        "Got it! Now choose a sprint from the list below:", reply_markup=reply_markup
    )
    logger.info("Sprints listed")
    return SPRINT


async def button_sprint(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    await query.answer()
    sprint = query.data

    if sprint == "skip":
        sprint = None

    context.user_data["sprint"] = sprint
    logger.info("Sprint selected: %s", sprint)

    # Present epics as inline buttons
    keyboard = []
    for i in range(0, len(epics), 3):
        row = [
            InlineKeyboardButton(epic.fields.summary, callback_data=epic.key)
            for epic in epics[i : i + 3]
        ]
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("Skip", callback_data="skip")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        "Got it! Now choose an epic from the list below:", reply_markup=reply_markup
    )
    logger.info("Epics listed")
    return EPIC


async def button_epic(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    await query.answer()
    epic = query.data

    if epic == "skip":
        epic = None

    context.user_data["epic"] = epic
    logger.info("Epic selected: %s", epic)

    # Present task types as inline buttons
    keyboard = [
        [
            InlineKeyboardButton(task_type, callback_data=task_type)
            for task_type in task_types[i : i + 3]
        ]
        for i in range(0, len(task_types), 3)
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        "Got it! Now choose a task type from the list below:", reply_markup=reply_markup
    )
    return TASK_TYPE


# Add the story points selection step after task type selection
async def button_task_type(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    await query.answer()
    task_type = query.data

    context.user_data["task_type"] = task_type
    logger.info("Task type selected: %s", task_type)

    # Present story points as inline buttons
    keyboard = [
        [
            InlineKeyboardButton(str(sp), callback_data=str(sp))
            for sp in story_points_values[i : i + 3]
        ]
        for i in range(0, len(story_points_values), 3)
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        "Got it! Now choose the story points:", reply_markup=reply_markup
    )
    return STORY_POINTS


async def button_story_points(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    await query.answer()
    story_points = float(query.data)

    context.user_data["story_points"] = story_points
    logger.info("Story points selected: %s", story_points)

    await query.edit_message_text(
        "Got it! Now send me one or more images, or type 'skip' if you don't want to attach any images."
    )
    return IMAGE


async def handle_image(update: Update, context: CallbackContext) -> int:
    if not await check_user_allowed(update):
        return ConversationHandler.END

    if update.message.text and update.message.text.lower() == "skip":
        logger.info("User chose to skip image upload.")
        await finalize_task(update, context)
        return ConversationHandler.END

    # Process images if any are provided
    if update.message.photo:
        image_files = update.message.photo
        image_streams = []
        async with aiohttp.ClientSession() as session:
            for photo in image_files:
                photo_file = await photo.get_file()
                async with session.get(photo_file.file_path) as response:
                    if response.status == 200:
                        image_data = await response.read()
                        image_stream = BytesIO(image_data)
                        image_streams.append(image_stream)
                    else:
                        logger.error(
                            f"Failed to fetch image from {photo_file.file_path}"
                        )

        logger.info("Images received")

        # Attach images and finalize the task
        await finalize_task(update, context, image_streams)
        return ConversationHandler.END
    else:
        await update.message.reply_text(
            "No images found. Please send one or more images or type 'skip' to skip."
        )
        return IMAGE


async def finalize_task(
    update: Update, context: CallbackContext, image_streams=None
) -> int:
    task_summary = context.user_data.get("task_summary")
    task_description = context.user_data.get("task_description")
    component_name = context.user_data.get("component")
    assignee = context.user_data.get("assignee")
    priority = context.user_data.get("priority")
    sprint = context.user_data.get("sprint")
    epic = context.user_data.get("epic")
    task_type = context.user_data.get("task_type")
    story_points = context.user_data.get("story_points")

    if not task_summary:
        await update.message.reply_text("Please send the task summary first.")
        logger.info("Summary not provided")
        return SUMMARY

    # Create a new Jira issue
    issue_fields = {
        "project": {"key": JIRA_PROJECT_KEY},
        "summary": task_summary,
        "description": task_description,
        "issuetype": {"name": task_type},
        "customfield_10100": epic,  # Replace with your epic link field ID
        "customfield_10104": int(sprint)
        if sprint is not None
        else sprint,  # Replace with your sprint field ID
        "customfield_10106": story_points,  # Replace with your story points field ID
    }

    if component_name:
        # Find the component object
        component = next(
            (
                component
                for component in jira.project_components(JIRA_PROJECT_KEY)
                if component.name == component_name
            ),
            None,
        )
        if component:
            issue_fields["components"] = [{"id": component.id}]

    if assignee:
        issue_fields["assignee"] = {"name": assignee}

    if priority:
        issue_fields["priority"] = {"name": priority}

    logger.info(f"issue fields = {issue_fields}")
    new_issue = jira.create_issue(fields=issue_fields)
    logger.info("Jira issue created: %s", new_issue.key)

    # Attach the images to the issue if any
    if image_streams:
        for image_stream in image_streams:
            jira.add_attachment(
                issue=new_issue, attachment=image_stream, filename="task_image.jpg"
            )
        logger.info("Images attached to Jira issue")

    await update.message.reply_text(
        f"Task created successfully! Issue key: {new_issue.key}"
    )
    return ConversationHandler.END


async def cancel(update: Update, context: CallbackContext) -> int:
    await update.message.reply_text("Operation cancelled.")
    logger.info("Operation cancelled by user")
    return ConversationHandler.END


async def error(update: Update, context: CallbackContext) -> None:
    logger.warning('Update "%s" caused error "%s"', update, context.error)

    try:
        if update.message:
            await update.message.reply_text(f"An error occurred: {context.error}")
        elif update.callback_query:
            await update.callback_query.message.reply_text(
                f"An error occurred: {context.error}"
            )
    except Exception as e:
        logger.error("Failed to send error message to user: %s", e)


def main() -> None:
    application = (
        Application.builder()
        .token(TELEGRAM_TOKEN)
        .read_timeout(20)
        .connect_timeout(20)
        .build()
    )

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            SUMMARY: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_summary)],
            DESCRIPTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_description)
            ],
            COMPONENT: [CallbackQueryHandler(button_component)],
            ASSIGNEE: [CallbackQueryHandler(button_assignee)],
            PRIORITY: [CallbackQueryHandler(button_priority)],
            SPRINT: [CallbackQueryHandler(button_sprint)],
            EPIC: [CallbackQueryHandler(button_epic)],
            TASK_TYPE: [CallbackQueryHandler(button_task_type)],
            STORY_POINTS: [CallbackQueryHandler(button_story_points)],
            IMAGE: [MessageHandler(filters.PHOTO | filters.TEXT, handle_image)],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CommandHandler("terminate", terminate),
        ],
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("help", help_command))
    application.add_error_handler(error)

    logger.info("Starting bot")
    application.run_polling()


if __name__ == "__main__":
    main()
