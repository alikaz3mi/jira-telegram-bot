from __future__ import annotations

from typing import Dict, List, Optional, cast
from io import BytesIO

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, ConversationHandler, CallbackQueryHandler

from jira_telegram_bot import LOGGER
from jira_telegram_bot.use_cases.telegram_commands.get_current_stories import GetCurrentStoriesUseCase
from jira_telegram_bot.settings.jira_settings import JiraConnectionSettings


class GetCurrentStoriesHandler:
    """Telegram handler for the get current stories command.
    
    This class handles the Telegram-specific interaction for the command,
    delegating business logic to the use case.
    """
    
    # Conversation states
    SELECT_PROJECT = 0
    SELECT_SPRINT = 1
    
    def __init__(
        self,
        get_current_stories_use_case: GetCurrentStoriesUseCase,
        jira_settings: JiraConnectionSettings,
    ):
        """Initialize the handler.
        
        Args:
            get_current_stories_use_case: Use case for current stories business logic
            jira_settings: Jira connection settings for getting base URL
        """
        self.get_current_stories_use_case = get_current_stories_use_case
        self.jira_settings = jira_settings
    
    def get_handler(self) -> ConversationHandler:
        """Get the conversation handler for this command.
        
        Returns:
            ConversationHandler configured for get current stories flow
        """
        return ConversationHandler(
            entry_points=[CommandHandler("get_current_stories", self.start_command)],
            states={
                self.SELECT_PROJECT: [
                    CallbackQueryHandler(self.select_project, pattern="^project:")
                ],
                self.SELECT_SPRINT: [
                    CallbackQueryHandler(self.select_sprint, pattern="^sprint:")
                ],
            },
            fallbacks=[CommandHandler("cancel", self.cancel)],
        )
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Start the get current stories command conversation.
        
        Args:
            update: Update from Telegram
            context: Context from Telegram handler
            
        Returns:
            Next conversation state
        """
        try:
            projects = await self.get_current_stories_use_case.get_projects()
            
            if not projects:
                await update.message.reply_text("No projects available.")
                return ConversationHandler.END
            
            keyboard = []
            # Group projects into rows of 3
            for i in range(0, len(projects), 3):
                row = []
                for j in range(i, min(i + 3, len(projects))):
                    project = projects[j]
                    row.append(InlineKeyboardButton(
                        f"{project['name']} ({project['key']})",
                        callback_data=f"project:{project['key']}"
                    ))
                keyboard.append(row)
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                "📊 *Get Current Stories*\n\n"
                "Please select a project:",
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
            
            return self.SELECT_PROJECT
            
        except Exception as e:
            LOGGER.error(f"Error starting get current stories command: {e}")
            await update.message.reply_text(f"Error: {str(e)}")
            return ConversationHandler.END
    
    async def select_project(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle project selection.
        
        Args:
            update: Update from Telegram
            context: Context from Telegram handler
            
        Returns:
            Next conversation state
        """
        query = update.callback_query
        await query.answer()
        
        project_key = query.data.split(":", 1)[1]
        context.user_data["selected_project"] = project_key
        
        try:
            sprints = await self.get_current_stories_use_case.get_sprints_for_project(
                project_key
            )
            
            if not sprints:
                await query.edit_message_text(
                    f"No active sprints found for project {project_key}."
                )
                return ConversationHandler.END
            
            keyboard = []
            for sprint in sprints:
                keyboard.append([
                    InlineKeyboardButton(
                        sprint['name'],
                        callback_data=f"sprint:{sprint['id']}"
                    )
                ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                f"Project selected: *{project_key}*\n\n"
                "Please select a sprint:",
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
            
            return self.SELECT_SPRINT
            
        except Exception as e:
            LOGGER.error(f"Error selecting project {project_key}: {e}")
            await query.edit_message_text(f"Error: {str(e)}")
            return ConversationHandler.END
    
    async def select_sprint(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle sprint selection and generate report.
        
        Args:
            update: Update from Telegram
            context: Context from Telegram handler
            
        Returns:
            ConversationHandler.END
        """
        query = update.callback_query
        await query.answer()
        
        sprint_id = query.data.split(":", 1)[1]
        project_key = context.user_data["selected_project"]
        
        try:
            await query.edit_message_text(
                "🔄 Generating current stories report...",
                parse_mode="Markdown"
            )
            
            report = await self.get_current_stories_use_case.generate_current_stories_report(
                project_key, sprint_id
            )
            
            if not report.stories:
                await query.edit_message_text(
                    f"No stories found in the selected sprint for project {project_key}."
                )
                return ConversationHandler.END
            
            # Generate XLSX file
            xlsx_data = await self.get_current_stories_use_case.generate_xlsx_report(report)
            
            # Save to Google Sheets
            google_sheets_success = await self.get_current_stories_use_case.save_to_google_sheets(
                report, 
                report.sprint_name,
                self.jira_settings.server_url
            )
            
            filename = f"current_stories_{project_key}_{report.sprint_name.replace(' ', '_')}.xlsx"
            
            # Send XLSX file
            await context.bot.send_document(
                chat_id=query.message.chat_id,
                document=xlsx_data,
                filename=filename,
                caption=(
                    f"📊 *Current Stories Report*\n\n"
                    f"**Project:** {project_key}\n"
                    f"**Sprint:** {report.sprint_name}\n"
                    f"**Stories Found:** {len(report.stories)}"
                ),
                parse_mode="Markdown"
            )
            
            # Create status message
            status_message = (
                f"✅ Current stories report generated successfully!\n\n"
                f"**Project:** {project_key}\n"
                f"**Sprint:** {report.sprint_name}\n"
                f"**Stories:** {len(report.stories)} found\n"
            )
            
            if google_sheets_success:
                status_message += f"📄 Report saved to Google Sheets: '{report.sprint_name}'"
            else:
                status_message += "⚠️ Failed to save to Google Sheets (XLSX file still available)"
            
            await query.edit_message_text(status_message)
            
            return ConversationHandler.END
            
        except Exception as e:
            LOGGER.error(f"Error generating report for {project_key}/{sprint_id}: {e}")
            await query.edit_message_text(f"❌ Error generating report: {str(e)}")
            return ConversationHandler.END
    
    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Cancel the conversation.
        
        Args:
            update: Update from Telegram
            context: Context from Telegram handler
            
        Returns:
            ConversationHandler.END
        """
        await update.message.reply_text("Get current stories command cancelled.")
        return ConversationHandler.END
