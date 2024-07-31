import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler, MessageHandler, filters, CallbackContext, Application, ConversationHandler, CallbackQueryHandler
from jira import JIRA
import requests
from io import BytesIO

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Telegram bot token and Jira credentials
TELEGRAM_TOKEN = '7434072786:AAHXpfT9QTMf2H8rhlh9k8TpbsZrYDvFmiM'
JIRA_SERVER = 'https://jira.parstechai.com'
JIRA_USERNAME = 'a_kazemi'
JIRA_PASS = 'a_kazemi'
JIRA_PROJECT_KEY = 'PARSCHAT'

ALLOWED_USERS = ['Mousavi_Shoushtari', 'alikaz3mi', 'GroupAnonymousBot']

# Initialize JIRA client
jira = JIRA(server=JIRA_SERVER, basic_auth=(JIRA_USERNAME, JIRA_PASS))

# Define states
SUMMARY, DESCRIPTION, COMPONENT, ASSIGNEE, PRIORITY, IMAGE = range(6)

async def check_user_allowed(update: Update) -> bool:
    user_id = update.message.from_user.username
    chat_type = update.message.chat.type
    if user_id not in ALLOWED_USERS:
        await update.message.reply_text(f"{user_id} : You are not authorized to create tasks.")
        logger.info(f"Unauthorized user: {user_id} in chat type: {chat_type}")
        return False
    return True

async def start(update: Update, context: CallbackContext) -> int:
    if not await check_user_allowed(update):
        return ConversationHandler.END
    await update.message.reply_text('Hi! Send me the summary of the task. Type /help for more instructions.')
    logger.info(f"Starting task creation process in chat type: {update.message.chat.type}")
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
        "7. **Image**: Send one or more images related to the task.\n\n"
        "The bot will then create a new Jira task with the provided details and attach the images to the task."
    )
    await update.message.reply_text(help_text)
    logger.info("Displayed help information")

async def terminate(update: Update, context: CallbackContext) -> int:
    await update.message.reply_text('Task creation process terminated.')
    logger.info("Task creation process terminated")
    return ConversationHandler.END

async def add_summary(update: Update, context: CallbackContext) -> int:
    if not await check_user_allowed(update):
        return ConversationHandler.END
    user = update.message.from_user
    logger.info("User %s sent a summary: %s", user.first_name, update.message.text)
    
    task_summary = update.message.text
    context.user_data['task_summary'] = task_summary
    await update.message.reply_text('Got it! Now send me the description of the task (or type "skip" to skip).')
    logger.info("Summary received: %s", task_summary)
    return DESCRIPTION

async def add_description(update: Update, context: CallbackContext) -> int:
    if not await check_user_allowed(update):
        return ConversationHandler.END
    user = update.message.from_user
    task_description = update.message.text
    
    if task_description.lower() == 'skip':
        task_description = None
    
    context.user_data['task_description'] = task_description
    logger.info("Description received: %s", task_description)

    # Fetch components from Jira
    components = jira.project_components(JIRA_PROJECT_KEY)
    components_text = "\n".join([component.name for component in components])
    
    await update.message.reply_text(f'Got it! Now choose a component from the following list:\n{components_text}')
    logger.info("Components listed")
    return COMPONENT

async def add_component(update: Update, context: CallbackContext) -> int:
    if not await check_user_allowed(update):
        return ConversationHandler.END
    user = update.message.from_user
    component_name = update.message.text

    # Check if the component exists
    components = jira.project_components(JIRA_PROJECT_KEY)
    component_names = [component.name for component in components]

    if component_name not in component_names:
        await update.message.reply_text('Invalid component name. Please choose a valid component from the list.')
        logger.info("Invalid component name: %s", component_name)
        return COMPONENT

    context.user_data['component'] = component_name
    logger.info("Component received: %s", component_name)

    # Present assignees as inline buttons
    assignees = ['O_Sadeghnezhad', 'm_fouladpanah', 'ah_ahmadi', 'z_lotfian', 'k_korminejad', 'a_janloo', 'm_Mousavi', 'p_etemad', 'a_kazemi', 'M_samei']
    keyboard = [[InlineKeyboardButton(assignee, callback_data=assignee) for assignee in assignees]]
    keyboard.append([InlineKeyboardButton("Skip", callback_data="skip")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('Got it! Now choose an assignee from the list below:', reply_markup=reply_markup)
    logger.info("Assignees listed")
    return ASSIGNEE

async def button_assignee(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    await query.answer()
    assignee = query.data
    
    if assignee == 'skip':
        assignee = None
    
    context.user_data['assignee'] = assignee
    logger.info("Assignee selected: %s", assignee)
    
    # Present priorities as inline buttons
    priorities = jira.priorities()
    keyboard = [[InlineKeyboardButton(priority.name, callback_data=priority.name) for priority in priorities]]
    keyboard.append([InlineKeyboardButton("Skip", callback_data="skip")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text('Got it! Now choose a priority from the list below:', reply_markup=reply_markup)
    logger.info("Priorities listed")
    return PRIORITY

async def button_priority(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    await query.answer()
    priority = query.data
    
    if priority == 'skip':
        priority = None
    
    context.user_data['priority'] = priority
    logger.info("Priority selected: %s", priority)
    
    await query.edit_message_text('Got it! Now send me one or more images.')
    return IMAGE

async def handle_image(update: Update, context: CallbackContext) -> int:
    if not await check_user_allowed(update):
        return ConversationHandler.END
    task_summary = context.user_data.get('task_summary')
    task_description = context.user_data.get('task_description')
    component_name = context.user_data.get('component')
    assignee = context.user_data.get('assignee')
    priority = context.user_data.get('priority')

    if not task_summary:
        await update.message.reply_text('Please send the task summary first.')
        logger.info("Summary not provided")
        return SUMMARY

    # Fetch the image files
    image_files = update.message.photo
    image_streams = []

    for photo in image_files:
        photo_file = await photo.get_file()
        image_data = requests.get(photo_file.file_path).content
        image_stream = BytesIO(image_data)
        image_streams.append(image_stream)
    logger.info("Images received")

    # Find the component object
    component = next(component for component in jira.project_components(JIRA_PROJECT_KEY) if component.name == component_name)

    # Create a new Jira issue
    issue_fields = {
        'project': {'key': JIRA_PROJECT_KEY},
        'summary': task_summary,
        'description': task_description,
        'issuetype': {'name': 'Task'},
        'components': [{'id': component.id}]
    }

    if assignee:
        issue_fields['assignee'] = {'name': assignee}

    if priority:
        issue_fields['priority'] = {'name': priority}

    new_issue = jira.create_issue(fields=issue_fields)
    logger.info("Jira issue created: %s", new_issue.key)

    # Attach the images to the issue
    for image_stream in image_streams:
        jira.add_attachment(issue=new_issue, attachment=image_stream, filename='task_image.jpg')
    
    await update.message.reply_text(f'Task created successfully! Issue key: {new_issue.key}')
    logger.info("Images attached to Jira issue")
    return ConversationHandler.END

async def cancel(update: Update, context: CallbackContext) -> int:
    await update.message.reply_text('Operation cancelled.')
    logger.info("Operation cancelled by user")
    return ConversationHandler.END

async def error(update: Update, context: CallbackContext) -> None:
    logger.warning('Update "%s" caused error "%s"', update, context.error)
    await update.message.reply_text(f'An error occurred: {context.error}')

def main() -> None:
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            SUMMARY: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_summary)],
            DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_description)],
            COMPONENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_component)],
            ASSIGNEE: [CallbackQueryHandler(button_assignee)],
            PRIORITY: [CallbackQueryHandler(button_priority)],
            IMAGE: [MessageHandler(filters.PHOTO, handle_image)]
        },
        fallbacks=[CommandHandler('cancel', cancel), CommandHandler('terminate', terminate)]
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("help", help_command))
    application.add_error_handler(error)

    logger.info("Starting bot")
    application.run_polling()

if __name__ == '__main__':
    main()