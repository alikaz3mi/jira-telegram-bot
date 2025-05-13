from __future__ import annotations

import os
import tempfile

from telegram import InlineKeyboardButton
from telegram import InlineKeyboardMarkup
from telegram import Update
from telegram.ext import CallbackContext
from telegram.ext import CallbackQueryHandler
from telegram.ext import CommandHandler
from telegram.ext import ConversationHandler
from telegram.ext import filters
from telegram.ext import MessageHandler

from jira_telegram_bot import DEFAULT_PATH
from jira_telegram_bot import LOGGER
from jira_telegram_bot.entities.speech import TranscriptionResult
from jira_telegram_bot.use_cases.interfaces.speech_processor_interface import (
    SpeechProcessorInterface,
)
from jira_telegram_bot.use_cases.interfaces.task_handler_interface import (
    TaskHandlerInterface,
)
from jira_telegram_bot.use_cases.telegram_commands.advanced_task_creation import (
    AdvancedTaskCreation,
)


class AdvancedTaskCreationHandler(TaskHandlerInterface):
    # Define conversation states
    (
        SELECT_PROJECT,
        SELECT_EPIC,
        SELECT_TASK_TYPE,
        SELECT_STORY,  # For selecting parent story when creating subtasks
        WAIT_FOR_DESCRIPTION,
        CONFIRM_TRANSCRIPTION,
        CONFIRM_BREAKDOWN,
    ) = range(7)

    def __init__(
        self,
        advanced_task_creation: AdvancedTaskCreation,
        speech_processor: SpeechProcessorInterface,
    ):
        self.advanced_task_creation = advanced_task_creation
        self.speech_processor = speech_processor

    async def start(self, update: Update, context: CallbackContext) -> int:
        """Start advanced task creation flow."""
        # Get projects from Jira
        projects = self.advanced_task_creation.task_manager_repository.get_projects()

        # Create keyboard with project options - 3 per row
        keyboard = []
        current_row = []

        for project in projects:
            button = InlineKeyboardButton(
                project.name,
                callback_data=f"project|{project.key}",
            )
            current_row.append(button)

            # When we have 3 buttons or it's the last project, add the row
            if len(current_row) == 3 or project == projects[-1]:
                keyboard.append(current_row)
                current_row = []

        # If there are any remaining buttons (less than 3), add them
        if current_row:
            keyboard.append(current_row)

        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            "🌟 Welcome to Advanced Task Creation!\n\n"
            "This will help break down complex tasks into well-organized stories and subtasks.\n\n"
            "You can:\n"
            "📝 Type a detailed description\n"
            "🎤 Send a voice message (Persian or English)\n"
            "↪️ Forward existing requirements\n\n"
            "First, please select a project:",
            reply_markup=reply_markup,
            parse_mode="Markdown",
        )

        return self.SELECT_PROJECT

    async def select_project(self, update: Update, context: CallbackContext) -> int:
        """Handle project selection."""
        query = update.callback_query
        await query.answer()

        project_key = query.data.split("|")[1]
        context.user_data["project_key"] = project_key

        try:
            # Load project info using the repository
            project_info = await self.advanced_task_creation.project_info_repository.get_project_info(project_key)
            context.user_data["project_info"] = project_info

            # Get epics for the project
            epics = self.advanced_task_creation.task_manager_repository.get_epics(
                project_key,
            )

            # Create keyboard with epic options - 3 per row
            keyboard = []
            current_row = []

            if epics:
                for epic in epics:
                    button = InlineKeyboardButton(
                        f"{epic.fields.summary}",
                        callback_data=f"epic|{epic.key}",
                    )
                    current_row.append(button)

                    # When we have 3 buttons or it's the last epic, add the row
                    if len(current_row) == 3 or epic == epics[-1]:
                        keyboard.append(current_row)
                        current_row = []

                # If there are any remaining buttons (less than 3), add them
                if current_row:
                    keyboard.append(current_row)

                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.edit_message_text(
                    "Please select an epic from the list below:",
                    reply_markup=reply_markup,
                )
                return self.SELECT_EPIC
            else:
                await query.edit_message_text(
                    "❌ No epics found in this project. Please create an epic first.",
                )
                return ConversationHandler.END

        except ValueError:
            await query.edit_message_text(
                f"❌ Sorry, couldn't find project info for {project_key}. "
                "Please contact an administrator.",
            )
            return ConversationHandler.END
        except Exception as e:
            LOGGER.error(f"Error loading project info: {str(e)}")
            await query.edit_message_text(
                f"❌ An error occurred while loading project information: {str(e)}",
            )
            return ConversationHandler.END

    async def process_voice_message(
        self,
        update: Update,
        context: CallbackContext,
    ) -> int:
        """Handle voice message input with improved Persian support."""
        try:
            # Download the voice file
            voice = update.message.voice
            voice_file = await voice.get_file()

            with tempfile.NamedTemporaryFile(
                suffix=".oga",
                delete=False,
            ) as voice_file_tmp:
                file_path = f"{DEFAULT_PATH}/{voice_file.file_path.split('/')[-1]}"
                await voice_file.download_to_drive(file_path)

                # Process voice with transcription entity
                result: TranscriptionResult = (
                    await self.speech_processor.process_voice_message(
                        file_path,
                    )
                )

                # Clean up
                os.unlink(voice_file_tmp.name)

                # Store original text
                context.user_data["original_text"] = result.text

                if result.is_persian:
                    context.user_data["translated_text"] = result.translation

                    # Show both versions for confirmation
                    keyboard = [
                        [
                            InlineKeyboardButton(
                                "✅ Correct",
                                callback_data="trans_confirm",
                            ),
                            InlineKeyboardButton(
                                "❌ Try Again",
                                callback_data="trans_retry",
                            ),
                        ],
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)

                    confidence_indicator = (
                        "🟢"
                        if result.confidence > 0.8
                        else "🟡"
                        if result.confidence > 0.6
                        else "🔴"
                    )

                    await update.message.reply_text(
                        f"*I transcribed your message* {confidence_indicator}\n\n"
                        f"🇮🇷 *Persian:*\n{result.text}\n\n"
                        f"🇬🇧 *English:*\n{result.translation}\n\n"
                        "Is this correct?",
                        reply_markup=reply_markup,
                        parse_mode="Markdown",
                    )
                else:
                    # If English, just confirm transcription
                    keyboard = [
                        [
                            InlineKeyboardButton(
                                "✅ Correct",
                                callback_data="trans_confirm",
                            ),
                            InlineKeyboardButton(
                                "❌ Try Again",
                                callback_data="trans_retry",
                            ),
                        ],
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)

                    confidence_indicator = (
                        "🟢"
                        if result.confidence > 0.8
                        else "🟡"
                        if result.confidence > 0.6
                        else "🔴"
                    )

                    await update.message.reply_text(
                        f"*I transcribed your message* {confidence_indicator}\n\n"
                        f"{result.text}"
                        "\n\n"
                        "Is this correct?",
                        reply_markup=reply_markup,
                        parse_mode="Markdown",
                    )

                return self.CONFIRM_TRANSCRIPTION

        except ValueError:
            await update.message.reply_text(
                "❌ Sorry, I couldn't understand the voice message. Please try again "
                "or type your description instead.",
            )
            return self.WAIT_FOR_DESCRIPTION

        except RuntimeError as error:
            LOGGER.error(f"Speech recognition error: {error}")
            await update.message.reply_text(
                "❌ Sorry, there was an error processing your voice message. "
                "Please try again or type your description instead.",
            )
            return self.WAIT_FOR_DESCRIPTION

        except Exception as error:
            LOGGER.error(f"Unexpected error processing voice message: {error}")
            await update.message.reply_text(
                "❌ An unexpected error occurred. Please try again or type your description.",
            )
            return self.WAIT_FOR_DESCRIPTION

    async def handle_transcription_confirmation(
        self,
        update: Update,
        context: CallbackContext,
    ) -> int:
        """Handle user's confirmation of voice transcription."""
        query = update.callback_query
        await query.answer()

        if query.data == "trans_confirm":
            # Use translated text if it exists, otherwise original
            text = context.user_data.get(
                "translated_text",
                context.user_data.get("original_text", ""),
            )

            # Clean up stored texts
            if "original_text" in context.user_data:
                del context.user_data["original_text"]
            if "translated_text" in context.user_data:
                del context.user_data["translated_text"]

            return await self.process_description(update, context, text)
        else:  # trans_retry
            await query.edit_message_text(
                "Please send your voice message again, or type your description.",
            )
            return self.WAIT_FOR_DESCRIPTION

    async def process_description(
        self,
        update: Update,
        context: CallbackContext,
        text: str = None,
    ) -> int:
        """Process the task description and create subtasks."""
        if text is None:
            text = update.message.text

        project_key = context.user_data["project_key"]
        project_info = context.user_data["project_info"]

        # Store description for confirmation
        context.user_data["description"] = text

        # Show confirmation message with preview
        preview = text[:200] + "..." if len(text) > 200 else text
        department_list = "\n".join(
            [f"• {dept}" for dept in project_info["departments"].keys()],
        )

        keyboard = [
            [
                InlineKeyboardButton("✅ Create Tasks", callback_data="confirm"),
                InlineKeyboardButton("❌ Cancel", callback_data="cancel"),
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        message_text = (
            "*Task Creation Preview*\n\n"
            f"📝 *Description:*\n{preview}\n\n"
            f"🏢 *Project:* {project_key}\n"
            f"👥 *Available Departments:*\n{department_list}\n\n"
            "The AI will:\n"
            "1️⃣ Create user stories\n"
            "2️⃣ Break down into component tasks\n"
            "3️⃣ Assign to team members\n"
            "4️⃣ Set story points & priorities\n\n"
            "Would you like to proceed?"
        )

        if hasattr(update, "callback_query") and update.callback_query:
            await update.callback_query.edit_message_text(
                text=message_text,
                reply_markup=reply_markup,
                parse_mode="Markdown",
            )
        else:
            await update.message.reply_text(
                text=message_text,
                reply_markup=reply_markup,
                parse_mode="Markdown",
            )

        return self.CONFIRM_BREAKDOWN

    async def create_tasks(self, update: Update, context: CallbackContext) -> int:
        """Handle task creation confirmation."""
        query = update.callback_query
        await query.answer()

        if query.data == "cancel":
            await query.edit_message_text("❌ Task creation cancelled.")
            return ConversationHandler.END

        await query.edit_message_text("🔄 Creating tasks... This might take a minute.")

        try:
            user_story = await self.advanced_task_creation.create_structured_user_story(
                description=context.user_data["description"],
                project_key=context.user_data["project_key"],
                epic_key=context.user_data.get("epic_key"),
                parent_story_key=context.user_data.get("parent_story_key"),
            )
            context.user_data["user_story"] = user_story

            created_tasks = await self.advanced_task_creation.create_tasks(
                description=context.user_data["description"],
                project_key=context.user_data["project_key"],
                task_type=context.user_data["task_type"],
                parent_story_key=context.user_data.get("parent_story_key"),
                epic_key=context.user_data.get("epic_key"),
            )

            # Group tasks by story for better visualization
            stories = {}
            for task in created_tasks:
                if task.fields.issuetype.name == "Story":
                    stories[task.key] = {
                        "summary": task.fields.summary,
                        "components": [c.name for c in task.fields.components],
                        "priority": task.fields.priority.name
                        if task.fields.priority
                        else "Medium",
                        "points": task.fields.customfield_10106 or "?",
                        "subtasks": [],
                    }
                else:  # Subtask
                    parent_key = task.fields.parent.key
                    if parent_key in stories:
                        stories[parent_key]["subtasks"].append(
                            {
                                "key": task.key,
                                "summary": task.fields.summary,
                                "assignee": task.fields.assignee.displayName
                                if task.fields.assignee
                                else "Unassigned",
                                "component": task.fields.components[0].name
                                if task.fields.components
                                else "No component",
                                "points": task.fields.customfield_10106 or "?",
                            },
                        )

            # Format response message
            response = "✅ *Successfully created the following structure:*\n\n"
            response += f"📝 *User Story: {user_story.summary}*\n"
            response += f"🏢 Project: {user_story.description}\n"
            for story_key, story_info in stories.items():
                response += f"📎 *{story_key}: {story_info['summary']}*\n"
                response += f"⭐️ Priority: {story_info['priority']}\n"
                response += f"🎯 Points: {story_info['points']}\n"
                response += f"🏢 Components: {', '.join(story_info['components'])}\n\n"

                for subtask in story_info["subtasks"]:
                    response += f"  • [{subtask['component']}] {subtask['key']}\n"
                    response += f"    {subtask['summary']}\n"
                    response += (
                        f"    👤 {subtask['assignee']} (🎯 {subtask['points']} pts)\n\n"
                    )

            # Split long messages if needed
            if len(response) > 4000:
                parts = [response[i : i + 4000] for i in range(0, len(response), 4000)]
                for part in parts:
                    await query.message.reply_text(part, parse_mode="HTML")
            else:
                await query.message.reply_text(response, parse_mode="HTML")

        except Exception as e:
            LOGGER.error(f"Error creating tasks: {str(e)}")
            await query.message.reply_text(
                "❌ Sorry, there was an error creating the tasks. Please try again or contact support.",
            )

        return ConversationHandler.END

    async def cancel(self, update: Update, context: CallbackContext) -> int:
        """Cancel the conversation."""
        await update.message.reply_text("❌ Advanced task creation cancelled.")
        return ConversationHandler.END

    async def select_epic(self, update: Update, context: CallbackContext) -> int:
        """Handle epic selection after project selection."""
        query = update.callback_query
        await query.answer()

        epic_key = query.data.split("|")[1]
        context.user_data["epic_key"] = epic_key

        # Create keyboard with epic options
        keyboard = []
        keyboard.append(
            [
                InlineKeyboardButton(
                    "Create New Story/Epic",
                    callback_data="task_type|story",
                ),
            ],
        )
        keyboard.append(
            [
                InlineKeyboardButton(
                    "Add Subtasks to Existing Story",
                    callback_data="task_type|subtask",
                ),
            ],
        )

        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            "How would you like to proceed?\n\n"
            "• Create a new story/epic\n"
            "• Add subtasks to an existing story\n"
            "• Create a story under an existing epic",
            reply_markup=reply_markup,
        )

        return self.SELECT_TASK_TYPE

    async def handle_task_type_selection(
        self,
        update: Update,
        context: CallbackContext,
    ) -> int:
        """Handle task type selection (story or subtask)."""
        query = update.callback_query
        await query.answer()

        selection = query.data.split("|")[1]
        project_key = context.user_data["project_key"]
        epic_key = context.user_data.get("epic_key")

        if selection == "story":
            context.user_data["task_type"] = "story"
            # Show available departments and proceed to description
            project_info = context.user_data["project_info"]
            dept_info = "\n".join(
                [
                    f"👥 *{dept}*: {info['description']}"
                    for dept, info in project_info["departments"].items()
                ],
            )

            await query.edit_message_text(
                f"📋 *Creating New Story*\n\n"
                f"*Available Departments:*\n{dept_info}\n\n"
                "Please describe the work needed. You can:\n"
                "1️⃣ Type a detailed description\n"
                "2️⃣ Send a voice message\n"
                "3️⃣ Forward requirements",
                parse_mode="Markdown",
            )
            return self.WAIT_FOR_DESCRIPTION

        elif selection == "subtask":
            # Get stories from the project related to the epic
            stories = self.advanced_task_creation.task_manager_repository.get_stories_by_project(
                project_key,
                epic_key,
                status='"In Progress", "To Do", "Backlog", "Selected for Development"',
                filters='description !~ "acceptance criteria" OR description  is EMPTY',
            )

            if not stories:
                await query.edit_message_text(
                    "No stories found in this project. Please create a story first.",
                )
                return ConversationHandler.END

            # Create keyboard with story options - 3 items per row
            keyboard = []
            current_row = []

            for story in stories:
                button = InlineKeyboardButton(
                    f"{story.fields.summary}",
                    callback_data=f"story|{story.key}",
                )
                current_row.append(button)

                # When we have 3 buttons or it's the last story, add the row
                if len(current_row) == 2 or story == stories[-1]:
                    keyboard.append(current_row)
                    current_row = []

            # If there are any remaining buttons (less than 3), add them as the last row
            if current_row:
                keyboard.append(current_row)

            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "Select the story to add subtasks to:",
                reply_markup=reply_markup,
            )

            return self.SELECT_STORY

        return ConversationHandler.END

    async def handle_story_selection(
        self,
        update: Update,
        context: CallbackContext,
    ) -> int:
        """Handle selection of parent story for subtasks."""
        query = update.callback_query
        await query.answer()

        story_key = query.data.split("|")[1]
        context.user_data["parent_story_key"] = story_key
        context.user_data["task_type"] = "subtask"
        # get story summary with story key from query.message.reply_markup.inline_keyboard
        story_summary = [
            button.text
            for row in query.message.reply_markup.inline_keyboard
            for button in row
            if button.callback_data == f"story|{story_key}"
        ][0]

        # Show available departments and proceed to description
        project_info = context.user_data["project_info"]
        dept_info = "\n".join(
            [
                f"👥 *{dept}*: {info['description']}"
                for dept, info in project_info["departments"].items()
            ],
        )

        await query.edit_message_text(
            f"📋 *Adding Subtasks to {story_key}: {story_summary}*\n\n"
            f"*Available Departments:*\n{dept_info}\n\n"
            "Please describe the subtasks needed. You can:\n"
            "1️⃣ Type a detailed description\n"
            "2️⃣ Send a voice message\n"
            "3️⃣ Forward requirements",
            parse_mode="Markdown",
        )
        return self.WAIT_FOR_DESCRIPTION

    async def process_text_description(
        self,
        update: Update,
        context: CallbackContext,
    ) -> int:
        """Process text description input from user.

        Args:
            update: The update containing the user's message.
            context: The callback context.

        Returns:
            The next conversation state.
        """
        text = update.message.text
        return await self.process_description(update, context, text)

    async def handle_epic_selection(
        self,
        update: Update,
        context: CallbackContext,
    ) -> int:
        """Handle epic selection for attaching to a story.

        Args:
            update: The update containing the callback query.
            context: The callback context.

        Returns:
            The next conversation state.
        """
        query = update.callback_query
        await query.answer()

        project_key = context.user_data["project_key"]
        epics = self.advanced_task_creation.task_manager_repository.get_epics(
            project_key,
        )

        # Create keyboard with epic options - 2 per row
        keyboard = []
        current_row = []

        for epic in epics:
            button = InlineKeyboardButton(
                f"{epic.key}: {epic.fields.summary}...",
                callback_data=f"epic_select|{epic.key}",
            )
            current_row.append(button)

            # When we have 2 buttons or it's the last epic, add the row
            if len(current_row) == 2 or epic == epics[-1]:
                keyboard.append(current_row)
                current_row = []

        # Add a "None" option
        keyboard.append(
            [
                InlineKeyboardButton("No Epic", callback_data="epic_select|none"),
            ],
        )

        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            "Select an epic to attach to your new story:",
            reply_markup=reply_markup,
        )

        return self.SELECT_EPIC

    def get_handler(self):
        """Return the ConversationHandler for this flow."""
        return ConversationHandler(
            entry_points=[CommandHandler("advanced_task", self.start)],
            states={
                self.SELECT_PROJECT: [
                    CallbackQueryHandler(self.select_project, pattern="^project\\|"),
                ],
                self.SELECT_EPIC: [
                    CallbackQueryHandler(self.select_epic, pattern="^epic\\|"),
                    CallbackQueryHandler(
                        self.handle_task_type_selection,
                        pattern="^task_type\\|",
                    ),
                ],
                self.SELECT_TASK_TYPE: [
                    CallbackQueryHandler(
                        self.handle_task_type_selection,
                        pattern="^task_type\\|",
                    ),
                    CallbackQueryHandler(
                        self.handle_epic_selection,
                        pattern="^select_epic$",
                    ),
                ],
                self.SELECT_STORY: [
                    CallbackQueryHandler(
                        self.handle_story_selection,
                        pattern="^story\\|",
                    ),
                ],
                self.WAIT_FOR_DESCRIPTION: [
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND,
                        self.process_text_description,
                    ),
                    MessageHandler(filters.VOICE, self.process_voice_message),
                ],
                self.CONFIRM_TRANSCRIPTION: [
                    CallbackQueryHandler(
                        self.handle_transcription_confirmation,
                        pattern="^trans_",
                    ),
                ],
                self.CONFIRM_BREAKDOWN: [
                    CallbackQueryHandler(
                        self.create_tasks,
                        pattern="^confirm$|^cancel$",
                    ),
                ],
            },
            fallbacks=[CommandHandler("cancel", self.cancel)],
        )
