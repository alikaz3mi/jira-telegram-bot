from __future__ import annotations

import json
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
from jira_telegram_bot.use_cases.telegram_commands.advanced_task_creation import AdvancedTaskCreation
from jira_telegram_bot.use_cases.interface.speech_processor_interface import (
    SpeechProcessorInterface,
)
from jira_telegram_bot.use_cases.interface.task_handler_interface import (
    TaskHandlerInterface,
)


class AdvancedTaskCreationHandler(TaskHandlerInterface):
    # Define conversation states
    (
        SELECT_PROJECT,
        WAIT_FOR_DESCRIPTION,
        CONFIRM_TRANSCRIPTION,
        CONFIRM_BREAKDOWN,
    ) = range(4)

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
        projects = self.advanced_task_creation.jira_repo.get_projects()

        # Create keyboard with project options
        keyboard = []
        for project in projects:
            keyboard.append(
                [
                    InlineKeyboardButton(
                        project.name,
                        callback_data=f"project|{project.key}",
                    ),
                ],
            )

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

        # Load project info
        project_info_path = os.path.join(
            DEFAULT_PATH,
            "jira_telegram_bot/settings/projects_info.json",
        )
        with open(project_info_path, "r") as f:
            projects_info = json.load(f)

        if project_key in projects_info:
            context.user_data["project_info"] = projects_info[project_key]
            project_info = projects_info[project_key]

            # Get department info for the message
            departments = project_info["departments"]
            dept_info = "\n".join(
                [
                    f"👥 *{dept}*: {info['description']}"
                    for dept, info in departments.items()
                ],
            )

            await query.edit_message_text(
                f"📋 *Selected Project:* {project_key}\n\n"
                f"*Available Departments:*\n{dept_info}\n\n"
                "Now, please describe the work needed. You can:\n"
                "1️⃣ Type a detailed description\n"
                "2️⃣ Send a voice message (Persian/English)\n"
                "3️⃣ Forward a message with requirements\n\n"
                "*Include information about:*\n"
                "• Overall goals/features\n"
                "• Technical requirements\n"
                "• Component-specific needs\n"
                "• Dependencies\n"
                "• Priority levels",
                parse_mode="Markdown",
            )
            return self.WAIT_FOR_DESCRIPTION
        else:
            await query.edit_message_text(
                f"❌ Sorry, couldn't find project info for {project_key}. "
                "Please contact an administrator.",
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
                await voice_file.download_to_drive(voice_file_tmp.name)

                # Process voice with transcription entity
                result: TranscriptionResult = (
                    await self.speech_processor.process_voice_message(
                        voice_file_tmp.name,
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

        except ValueError as e:
            await update.message.reply_text(
                "❌ Sorry, I couldn't understand the voice message. Please try again "
                "or type your description instead.",
            )
            return self.WAIT_FOR_DESCRIPTION

        except RuntimeError as e:
            LOGGER.error(f"Speech recognition error: {e}")
            await update.message.reply_text(
                "❌ Sorry, there was an error processing your voice message. "
                "Please try again or type your description instead.",
            )
            return self.WAIT_FOR_DESCRIPTION

        except Exception as e:
            LOGGER.error(f"Unexpected error processing voice message: {e}")
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

        await update.message.reply_text(
            "*Task Creation Preview*\n\n"
            f"📝 *Description:*\n{preview}\n\n"
            f"🏢 *Project:* {project_key}\n"
            f"👥 *Available Departments:*\n{department_list}\n\n"
            "The AI will:\n"
            "1️⃣ Create user stories\n"
            "2️⃣ Break down into component tasks\n"
            "3️⃣ Assign to team members\n"
            "4️⃣ Set story points & priorities\n\n"
            "Would you like to proceed?",
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
            created_tasks = await self.advanced_task_creation.create_tasks(
                description=context.user_data["description"],
                project_key=context.user_data["project_key"],
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
                    await query.message.reply_text(part, parse_mode="Markdown")
            else:
                await query.message.reply_text(response, parse_mode="Markdown")

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

    def get_handler(self):
        """Return the ConversationHandler for this flow."""
        return ConversationHandler(
            entry_points=[CommandHandler("advanced_task", self.start)],
            states={
                self.SELECT_PROJECT: [
                    CallbackQueryHandler(self.select_project, pattern="^project\\|"),
                ],
                self.WAIT_FOR_DESCRIPTION: [
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND,
                        self.process_description,
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
