import aiohttp
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    CallbackContext,
    ConversationHandler,
)
from jira import JIRA
from io import BytesIO

from jira_telegram_bot import LOGGER
from jira_telegram_bot.settings import JIRA_SETTINGS
from jira_telegram_bot.use_cases.config import JIRA_PROJECT_KEY
from jira_telegram_bot.use_cases.authentication import check_user_allowed


jira = JIRA(
    server=JIRA_SETTINGS.domain,
    basic_auth=(JIRA_SETTINGS.username, JIRA_SETTINGS.password),
)

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

sprints = jira.sprints(board_id=board_id)
try:
    latest_sprint = next(sprint for sprint in sprints if sprint.state == "active")
except Exception as e:
    LOGGER.error(f"No sprint is active: {e}.")
    latest_sprint = sprints[-1]
priorities = jira.priorities()
task_types = [z.name for z in jira.issue_types_for_project(JIRA_PROJECT_KEY)]
story_points_values = [0.5, 1, 1.5, 2, 2.5, 3, 3.5, 4.0, 7]


async def add_summary(update: Update, context: CallbackContext) -> int:
    if not await check_user_allowed(update):
        return ConversationHandler.END
    user = update.message.from_user
    LOGGER.info("User %s sent a summary: %s", user.first_name, update.message.text)

    task_summary = update.message.text
    context.user_data["task_summary"] = task_summary
    await update.message.reply_text(
        'Got it! Now send me the description of the task (or type "skip" to skip).'
    )
    LOGGER.info("Summary received: %s", task_summary)
    return DESCRIPTION


async def add_description(update: Update, context: CallbackContext) -> int:
    if not await check_user_allowed(update):
        return ConversationHandler.END
    task_description = update.message.text

    if task_description.lower() == "skip":
        task_description = ""

    context.user_data["task_description"] = task_description
    LOGGER.info("Description received: %s", task_description)

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
    LOGGER.info("Components listed")
    return COMPONENT


async def button_component(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    await query.answer()
    component = query.data

    if component == "skip":
        component = None

    context.user_data["component"] = component
    LOGGER.info("Component selected: %s", component)

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
    LOGGER.info("Assignees listed")
    return ASSIGNEE


async def button_assignee(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    await query.answer()
    assignee = query.data

    if assignee == "skip":
        assignee = None

    context.user_data["assignee"] = assignee
    LOGGER.info("Assignee selected: %s", assignee)

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
    LOGGER.info("Priorities listed")
    return PRIORITY


async def button_priority(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    await query.answer()
    priority = query.data

    if priority == "skip":
        priority = None

    context.user_data["priority"] = priority
    LOGGER.info("Priority selected: %s", priority)

    # Present sprints as inline buttons
    keyboard = [
        [InlineKeyboardButton(latest_sprint.name, callback_data=str(latest_sprint.id))],
        [InlineKeyboardButton("Skip", callback_data="skip")],
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        "Got it! Now choose a sprint from the list below:", reply_markup=reply_markup
    )
    LOGGER.info("Sprints listed")
    return SPRINT


async def button_sprint(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    await query.answer()
    sprint = query.data

    if sprint == "skip":
        sprint = None

    context.user_data["sprint"] = sprint
    LOGGER.info("Sprint selected: %s", sprint)

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
    LOGGER.info("Epics listed")
    return EPIC


async def button_epic(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    await query.answer()
    epic = query.data

    if epic == "skip":
        epic = None

    context.user_data["epic"] = epic
    LOGGER.info("Epic selected: %s", epic)

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
    LOGGER.info("Task type selected: %s", task_type)

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
    LOGGER.info("Story points selected: %s", story_points)

    await query.edit_message_text(
        "Got it! Now send me one or more images, or type 'skip' if you don't want to attach any images."
    )
    return IMAGE


async def handle_image(update: Update, context: CallbackContext) -> int:
    if not await check_user_allowed(update):
        return ConversationHandler.END

    if update.message.text and update.message.text.lower() == "skip":
        LOGGER.info("User chose to skip image upload.")
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
                        LOGGER.error(
                            f"Failed to fetch image from {photo_file.file_path}"
                        )

        LOGGER.info("Images received")

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
        LOGGER.info("Summary not provided")
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

    LOGGER.info(f"issue fields = {issue_fields}")
    new_issue = jira.create_issue(fields=issue_fields)
    LOGGER.info("Jira issue created: %s", new_issue.key)

    # Attach the images to the issue if any
    if image_streams:
        for image_stream in image_streams:
            jira.add_attachment(
                issue=new_issue, attachment=image_stream, filename="task_image.jpg"
            )
        LOGGER.info("Images attached to Jira issue")

    await update.message.reply_text(
        f"Task created successfully! Issue key: {new_issue.key}"
    )
    return ConversationHandler.END
