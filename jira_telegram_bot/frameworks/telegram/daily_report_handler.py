import tempfile
import os
from typing import List, Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackContext, CommandHandler, ConversationHandler, MessageHandler, filters, CallbackQueryHandler

from jira_telegram_bot.adapters.stt.speech_recogniser import SpeechRecogniser
from jira_telegram_bot.use_cases.ai_agents.generate_progress_report_usecase import GenerateProgressReportUseCase
from jira_telegram_bot.use_cases.jira.get_sprint_issues_usecase import GetSprintIssuesUseCase


# Conversation states
SELECTING_TASKS, RECORDING_PROGRESS, PROCESSING_REPORT = range(3)


class DailyReportHandler:
    """Telegram handler for daily progress reports."""

    def __init__(
        self,
        generate_progress_report_usecase: GenerateProgressReportUseCase,
        get_sprint_issues_usecase: GetSprintIssuesUseCase,
        speech_recogniser: SpeechRecogniser,
        sprint_label: str,
        report_channel_id: str,
    ):
        """Initialize the daily report handler.

        Args:
            generate_progress_report_usecase: Use case for generating progress reports.
            get_sprint_issues_usecase: Use case for fetching sprint issues.
            speech_recogniser: Service for speech-to-text conversion.
            sprint_label: The current sprint label.
            report_channel_id: Channel ID for aggregated reports.
        """
        self._generate_progress_report_usecase = generate_progress_report_usecase
        self._get_sprint_issues_usecase = get_sprint_issues_usecase
        self._speech_recogniser = speech_recogniser
        self._sprint_label = sprint_label
        self._report_channel_id = report_channel_id

    def get_conversation_handler(self) -> ConversationHandler:
        """Get the conversation handler for daily reports.

        Returns:
            ConversationHandler configured for daily report flow.
        """
        return ConversationHandler(
            entry_points=[
                CommandHandler("daily_report", self.start_daily_report),
                CallbackQueryHandler(self.handle_progress_callback, pattern=r"^progress_.*"),
            ],
            states={
                SELECTING_TASKS: [
                    CallbackQueryHandler(self.handle_task_selection, pattern=r"^task_.*"),
                    CallbackQueryHandler(self.handle_task_selection_done, pattern="^selection_done$"),
                ],
                RECORDING_PROGRESS: [
                    MessageHandler(filters.VOICE, self.handle_voice_progress),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text_progress),
                ],
                PROCESSING_REPORT: [
                    MessageHandler(filters.ALL, self.ignore_during_processing),
                ],
            },
            fallbacks=[
                CommandHandler("cancel", self.cancel_daily_report),
                CallbackQueryHandler(self.cancel_daily_report, pattern="^progress_skip$"),
            ],
            per_chat=True,
            per_user=True,
        )

    async def start_daily_report(self, update: Update, context: CallbackContext) -> int:
        """Start the daily report conversation.

        Args:
            update: The Telegram update.
            context: The callback context.

        Returns:
            Next conversation state.
        """
        user = update.effective_user
        
        try:
            # Get user's assigned tasks
            sprint_issues = await self._get_sprint_issues_usecase.execute(
                sprint_label=self._sprint_label
            )
            
            user_tasks = [
                issue for issue in sprint_issues
                if issue.assignee and issue.assignee.lower() == user.username.lower()
            ]
            
            # Store context data
            context.user_data['sprint_issues'] = sprint_issues
            context.user_data['user_tasks'] = user_tasks
            context.user_data['selected_tasks'] = []
            
            message = f"📋 **Daily Progress Report**\n\nHi {user.first_name}! Ready to share your progress?\n\nChoose how you'd like to proceed:"
            
            keyboard = [
                [
                    InlineKeyboardButton("🎤 Voice Report", callback_data="progress_voice"),
                    InlineKeyboardButton("💬 Text Report", callback_data="progress_text"),
                ],
                [
                    InlineKeyboardButton("📋 Select Specific Tasks", callback_data="progress_select_tasks"),
                ],
                [
                    InlineKeyboardButton("❌ Cancel", callback_data="progress_skip"),
                ]
            ]
            
            await update.message.reply_text(
                message,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
            
            return RECORDING_PROGRESS
            
        except Exception as e:
            await update.message.reply_text(f"❌ Error starting daily report: {str(e)}")
            return ConversationHandler.END

    async def handle_progress_callback(self, update: Update, context: CallbackContext) -> int:
        """Handle progress report callback buttons.

        Args:
            update: The Telegram update.
            context: The callback context.

        Returns:
            Next conversation state.
        """
        query = update.callback_query
        await query.answer()
        
        if query.data == "progress_voice":
            await query.edit_message_text(
                "🎤 **Voice Progress Report**\n\nPlease record and send a voice message with your progress update.\n\nTalk about:\n• What you accomplished today\n• Any blockers or challenges\n• Time spent on tasks",
                parse_mode='Markdown'
            )
            return RECORDING_PROGRESS
            
        elif query.data == "progress_text":
            await query.edit_message_text(
                "💬 **Text Progress Report**\n\nPlease type your progress update.\n\nInclude:\n• What you accomplished today\n• Any blockers or challenges\n• Time spent on tasks",
                parse_mode='Markdown'
            )
            return RECORDING_PROGRESS
            
        elif query.data == "progress_select_tasks":
            return await self.show_task_selection(update, context)
            
        elif query.data == "progress_skip":
            await query.edit_message_text("👋 Daily report cancelled. Have a great day!")
            return ConversationHandler.END
            
        return RECORDING_PROGRESS

    async def show_task_selection(self, update: Update, context: CallbackContext) -> int:
        """Show task selection interface.

        Args:
            update: The Telegram update.
            context: The callback context.

        Returns:
            Next conversation state.
        """
        query = update.callback_query
        sprint_issues = context.user_data.get('sprint_issues', [])
        user = update.effective_user
        
        # Filter tasks for the user or show all if none assigned
        user_tasks = [
            issue for issue in sprint_issues
            if issue.assignee and issue.assignee.lower() == user.username.lower()
        ]
        
        if not user_tasks:
            user_tasks = sprint_issues[:10]  # Show first 10 tasks if none assigned
        
        if not user_tasks:
            await query.edit_message_text("❌ No tasks found in the current sprint.")
            return ConversationHandler.END
        
        keyboard = []
        for task in user_tasks:
            keyboard.append([
                InlineKeyboardButton(
                    f"☐ {task.key}: {task.summary[:50]}...",
                    callback_data=f"task_{task.key}"
                )
            ])
        
        keyboard.append([
            InlineKeyboardButton("✅ Done Selecting", callback_data="selection_done")
        ])
        
        await query.edit_message_text(
            f"📋 **Select Tasks for Progress Report**\n\nTap tasks to select/deselect them:\n\n*Selected: {len(context.user_data.get('selected_tasks', []))} tasks*",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        
        return SELECTING_TASKS

    async def handle_task_selection(self, update: Update, context: CallbackContext) -> int:
        """Handle task selection/deselection.

        Args:
            update: The Telegram update.
            context: The callback context.

        Returns:
            Next conversation state.
        """
        query = update.callback_query
        await query.answer()
        
        task_key = query.data.replace("task_", "")
        selected_tasks = context.user_data.get('selected_tasks', [])
        
        if task_key in selected_tasks:
            selected_tasks.remove(task_key)
        else:
            selected_tasks.append(task_key)
        
        context.user_data['selected_tasks'] = selected_tasks
        
        # Update the message to show current selection
        sprint_issues = context.user_data.get('sprint_issues', [])
        user = update.effective_user
        
        user_tasks = [
            issue for issue in sprint_issues
            if issue.assignee and issue.assignee.lower() == user.username.lower()
        ]
        
        if not user_tasks:
            user_tasks = sprint_issues[:10]
        
        keyboard = []
        for task in user_tasks:
            check_mark = "☑️" if task.key in selected_tasks else "☐"
            keyboard.append([
                InlineKeyboardButton(
                    f"{check_mark} {task.key}: {task.summary[:50]}...",
                    callback_data=f"task_{task.key}"
                )
            ])
        
        keyboard.append([
            InlineKeyboardButton("✅ Done Selecting", callback_data="selection_done")
        ])
        
        await query.edit_message_text(
            f"📋 **Select Tasks for Progress Report**\n\nTap tasks to select/deselect them:\n\n*Selected: {len(selected_tasks)} tasks*",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        
        return SELECTING_TASKS

    async def handle_task_selection_done(self, update: Update, context: CallbackContext) -> int:
        """Handle completion of task selection.

        Args:
            update: The Telegram update.
            context: The callback context.

        Returns:
            Next conversation state.
        """
        query = update.callback_query
        await query.answer()
        
        selected_tasks = context.user_data.get('selected_tasks', [])
        
        if not selected_tasks:
            await query.edit_message_text(
                "⚠️ No tasks selected. Please select at least one task or use the general report option.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Back to Selection", callback_data="progress_select_tasks")],
                    [InlineKeyboardButton("💬 General Text Report", callback_data="progress_text")],
                ])
            )
            return SELECTING_TASKS
        
        await query.edit_message_text(
            f"✅ **{len(selected_tasks)} tasks selected**\n\nNow please share your progress by voice message or text.",
            parse_mode='Markdown'
        )
        
        return RECORDING_PROGRESS

    async def handle_voice_progress(self, update: Update, context: CallbackContext) -> int:
        """Handle voice progress report.

        Args:
            update: The Telegram update.
            context: The callback context.

        Returns:
            Next conversation state.
        """
        await update.message.reply_text("🎤 Processing your voice message...")
        
        try:
            # Download voice message
            voice_file = await update.message.voice.get_file()
            
            with tempfile.NamedTemporaryFile(suffix='.ogg', delete=False) as temp_file:
                await voice_file.download_to_drive(temp_file.name)
                temp_file_path = temp_file.name
            
            try:
                # Transcribe voice to text
                transcript = await self._speech_recogniser.transcribe_voice_message(temp_file_path)
                
                if not transcript:
                    await update.message.reply_text("❌ Could not transcribe your voice message. Please try again or use text input.")
                    return RECORDING_PROGRESS
                
                # Process the transcript
                return await self._process_progress_report(update, context, transcript)
                
            finally:
                # Clean up temporary file
                if os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)
                    
        except Exception as e:
            await update.message.reply_text(f"❌ Error processing voice message: {str(e)}")
            return RECORDING_PROGRESS

    async def handle_text_progress(self, update: Update, context: CallbackContext) -> int:
        """Handle text progress report.

        Args:
            update: The Telegram update.
            context: The callback context.

        Returns:
            Next conversation state.
        """
        transcript = update.message.text
        return await self._process_progress_report(update, context, transcript)

    async def _process_progress_report(self, update: Update, context: CallbackContext, transcript: str) -> int:
        """Process the progress report using AI.

        Args:
            update: The Telegram update.
            context: The callback context.
            transcript: The transcribed or typed text.

        Returns:
            Next conversation state.
        """
        await update.message.reply_text("🤖 Generating your progress report...")
        
        try:
            user = update.effective_user
            selected_tasks = context.user_data.get('selected_tasks', [])
            sprint_issues = context.user_data.get('sprint_issues', [])
            
            # Generate progress report
            reports = await self._generate_progress_report_usecase.execute(
                assignee=user.username or user.first_name,
                sprint_label=self._sprint_label,
                selected_issue_keys=selected_tasks,
                available_tasks=sprint_issues,
                raw_transcript=transcript,
            )
            
            # Format and send the generated report
            report_text = self._format_progress_report(reports, user.first_name)
            
            await update.message.reply_text(
                report_text,
                parse_mode='Markdown'
            )
            
            # Send summary to report channel
            await self._send_to_report_channel(context, user, reports)
            
            await update.message.reply_text("✅ Progress report submitted successfully! Thank you.")
            
            return ConversationHandler.END
            
        except Exception as e:
            await update.message.reply_text(f"❌ Error generating progress report: {str(e)}")
            return RECORDING_PROGRESS

    def _format_progress_report(self, reports: List, user_name: str) -> str:
        """Format progress reports for display.

        Args:
            reports: List of progress reports.
            user_name: Name of the user.

        Returns:
            Formatted report text.
        """
        if not reports:
            return "⚠️ No progress reports were generated."
        
        formatted_text = f"📋 **Progress Report for {user_name}**\n\n"
        
        for i, report in enumerate(reports, 1):
            formatted_text += f"**{i}. {report.issue_key}**\n"
            formatted_text += f"• **Progress:** {report.progress}\n"
            formatted_text += f"• **Blockers:** {report.blockers}\n"
            formatted_text += f"• **Time Spent:** {report.time_spent}\n\n"
        
        return formatted_text

    async def _send_to_report_channel(self, context: CallbackContext, user, reports: List) -> None:
        """Send summary report to the report channel.

        Args:
            context: The callback context.
            user: The Telegram user.
            reports: List of progress reports.
        """
        try:
            summary = f"📊 **Daily Report - {user.first_name}** (@{user.username})\n\n"
            
            for report in reports:
                summary += f"• **{report.issue_key}**: {report.progress[:100]}...\n"
            
            summary += f"\n🕒 *Reported at {reports[0].reported_at.strftime('%H:%M')}*"
            
            await context.bot.send_message(
                chat_id=self._report_channel_id,
                text=summary,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            # Don't fail the main flow if channel posting fails
            pass

    async def cancel_daily_report(self, update: Update, context: CallbackContext) -> int:
        """Cancel the daily report conversation.

        Args:
            update: The Telegram update.
            context: The callback context.

        Returns:
            Conversation end state.
        """
        if update.callback_query:
            await update.callback_query.edit_message_text("👋 Daily report cancelled. Have a great day!")
        else:
            await update.message.reply_text("👋 Daily report cancelled. Have a great day!")
        
        return ConversationHandler.END

    async def ignore_during_processing(self, update: Update, context: CallbackContext) -> int:
        """Ignore messages during processing.

        Args:
            update: The Telegram update.
            context: The callback context.

        Returns:
            Current conversation state.
        """
        await update.message.reply_text("⏳ Please wait while I process your report...")
        return PROCESSING_REPORT
