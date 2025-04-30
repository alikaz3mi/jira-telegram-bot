from __future__ import annotations

import logging

from langchain import LLMChain
from langchain.prompts import PromptTemplate
from telegram import InlineKeyboardButton
from telegram import InlineKeyboardMarkup
from telegram import Update
from telegram import Voice
from telegram.ext import CallbackContext
from telegram.ext import CallbackQueryHandler
from telegram.ext import CommandHandler
from telegram.ext import ConversationHandler
from telegram.ext import filters
from telegram.ext import MessageHandler

from jira_telegram_bot.adapters.ai_models.openai_model import OpenAIGateway
from jira_telegram_bot.use_cases.interface.task_handler_interface import (
    TaskHandlerInterface,
)
from jira_telegram_bot.use_cases.interface.task_manager_repository_interface import (
    TaskManagerRepositoryInterface,
)
from jira_telegram_bot.use_cases.interface.user_config_interface import (
    UserConfigInterface,
)

LOGGER = logging.getLogger(__name__)

# Conversation states
(
    SELECT_PROJECT,
    SELECT_TASKS,
    WAIT_FOR_VOICE,
    CONFIRM_POST,
) = range(4)


class VoiceReportHandler(TaskHandlerInterface):
    """
    This conversation:
    1) Asks user to pick a project or uses their default from user_config.
    2) Fetches the tasks assigned to them in that project from Jira.
    3) Allows multi-select of tasks for the report.
    4) Accepts a voice note from user (in Persian).
    5) Transcribes + cleans the text using OpenAI's 'o3-mini' model.
    6) Uses LangChain & a special Persian prompt to generate a formal report referencing each task.
    7) Posts that formal Farsi report to Jira (e.g., as a comment) for each selected task or as one aggregated ticket.
    """

    def __init__(
        self,
        user_config_repo: UserConfigInterface,
        jira_repo: TaskManagerRepositoryInterface,
        openai_gateway: OpenAIGateway,
    ) -> None:
        """
        :param user_config_repo: to fetch the user’s default project/Jira user name
        :param jira_repo: to retrieve tasks from Jira
        :param openai_gateway: to run transcription & text generation
        """
        self.user_config_repo = user_config_repo
        self.jira_repo = jira_repo
        self.openai = openai_gateway

        # Create an LLMChain for final formal Farsi summarization.
        # We'll use the same 'o3-mini' or a different model if needed.
        # The prompt is just an example. Adjust to suit your needs.
        self.summary_prompt = PromptTemplate(
            input_variables=["transcribed_text", "task_list"],
            template="""
شما یک دستیار هوشمند هستید که متن زیر را از کاربر دریافت کرده‌اید و وظایف انتخاب‌شده کاربر در جیرا را نیز می‌دانید.

متن: {transcribed_text}

فهرست تسک‌ها:
{task_list}

وظیفه شما این است که یک گزارش رسمی فارسی تولید کنید که به هر یک از تسک‌های فوق مرتبط باشد.
از هر بخش صحبت کاربر نتیجه‌گیری کنید و آن را ذیل تسک یا تسک‌های مرتبط قرار دهید.
گزارش نهایی را کاملاً فارسی و رسمی بنویسید.
            """,
        )
        self.summary_chain = LLMChain(
            llm=self.openai.get_llm(),
            prompt=self.summary_prompt,
        )

    def get_handler(self):
        """
        Returns a ConversationHandler to integrate into your main PTB Application.
        """
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler("voice_report", self.start)],
            states={
                SELECT_PROJECT: [
                    CallbackQueryHandler(self.select_project_callback),
                ],
                SELECT_TASKS: [
                    CallbackQueryHandler(self.select_tasks_callback),
                ],
                WAIT_FOR_VOICE: [
                    MessageHandler(filters.VOICE, self.handle_voice_message),
                ],
                CONFIRM_POST: [
                    CallbackQueryHandler(self.handle_confirm_post),
                ],
            },
            fallbacks=[CommandHandler("cancel", self.cancel)],
            allow_reentry=True,
        )
        return conv_handler

    def start(self, update: Update, context: CallbackContext) -> int:
        """
        1) Check if user_config has default project.
        2) If user has multiple or unknown, let them pick from a list of projects.
        """
        user_telegram = update.effective_user.username
        user_cfg = self.user_config_repo.get_user_config(user_telegram)
        if not user_cfg:
            update.message.reply_text(
                "Cannot find your user config. Please set your settings first.",
            )
            return ConversationHandler.END

        # Check if we have a default project in user_config:
        default_project_key = user_cfg.project or None
        projects = self.jira_repo.get_projects()
        # If user_config has a single known project, skip selection:
        if default_project_key and any(p.key == default_project_key for p in projects):
            context.user_data["selected_project"] = default_project_key
            return self._ask_for_tasks(update, context)
        else:
            # Let user pick from all possible projects
            keyboard = []
            for p in projects:
                keyboard.append([InlineKeyboardButton(p.name, callback_data=p.key)])
            update.message.reply_text(
                "Select your project:",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
            return SELECT_PROJECT

    def select_project_callback(self, update: Update, context: CallbackContext) -> int:
        """
        Stores the chosen project key in user_data, then goes on to tasks.
        """
        query = update.callback_query
        query.answer()
        project_key = query.data
        context.user_data["selected_project"] = project_key
        return self._ask_for_tasks(update, context)

    def _ask_for_tasks(self, update: Update, context: CallbackContext) -> int:
        """
        Show tasks assigned to the user so they can pick multiple tasks for the final report.
        """
        user_telegram = update.effective_user.username
        user_cfg = self.user_config_repo.get_user_config(user_telegram)
        jira_username = user_cfg.jira_username or user_telegram  # fallback

        project_key = context.user_data["selected_project"]
        # Search tasks assigned to this user:
        jql = f'assignee="{jira_username}" AND project="{project_key}" AND statusCategory != Done order by created DESC'
        issues = self.jira_repo.jira.search_issues(jql, maxResults=20)

        if not issues:
            update.effective_message.reply_text(
                "No tasks found for you in this project.",
            )
            return ConversationHandler.END

        # Show them as inline keyboard for multi-select
        # We'll store selected issues in user_data["report_task_keys"] as a set
        context.user_data["report_task_keys"] = set()

        keyboard = []
        for issue in issues:
            button_text = f"{issue.key} - {issue.fields.summary}"
            keyboard.append(
                [InlineKeyboardButton(button_text, callback_data=issue.key)],
            )
        # We'll add a "Done selecting" button
        keyboard.append(
            [
                InlineKeyboardButton(
                    "تمام (پایان انتخاب)",
                    callback_data="done_selecting",
                ),
            ],
        )

        update.effective_message.reply_text(
            "Please tap on the tasks you want to include in your report.\n"
            "Tap 'تمام' when you are finished.",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return SELECT_TASKS

    def select_tasks_callback(self, update: Update, context: CallbackContext) -> int:
        """
        Each click toggles the selected task. If user clicks "done_selecting", proceed.
        """
        query = update.callback_query
        query.answer()
        if query.data == "done_selecting":
            # proceed to voice recording
            query.edit_message_text(
                text="حالا لطفاً پیام صوتی فارسی خود را ارسال کنید تا آن را دریافت کنم.",
            )
            return WAIT_FOR_VOICE
        else:
            # Toggle the selection
            selected_set = context.user_data["report_task_keys"]
            if query.data in selected_set:
                selected_set.remove(query.data)
                query.answer(text=f"Removed {query.data} from selection.")
            else:
                selected_set.add(query.data)
                query.answer(text=f"Selected {query.data}.")
            return SELECT_TASKS

    def handle_voice_message(self, update: Update, context: CallbackContext) -> int:
        """
        We receive the voice note, pass it to OpenAI for speech2text using 'o3-mini',
        then again for cleaning. Store final text in user_data and ask user to confirm.
        """
        voice_msg: Voice = update.message.voice
        file_id = voice_msg.file_id

        # 1) Get the actual file data
        file_obj = update.message.bot.get_file(file_id)
        file_content = file_obj.download_as_bytearray()

        # 2) Send audio to OpenAI for transcription (ASR) using model_name='o3-mini'
        #    For demonstration, we directly call openai speech2text with our openai_gateway
        #    or your own method.
        raw_transcript = self.openai.transcribe_audio(
            audio_content=file_content,
            model="o3-mini",  # hypothetical
            language="fa",  # for Persian
        )
        # 3) Clean the text using the same model or a simple text-lint pass:
        cleaned_text = self.openai.clean_text(raw_transcript, model="o3-mini")
        #   (You might do something like a second LLM call that rewrites, or do nothing if not needed.)

        context.user_data["transcribed_text"] = cleaned_text
        update.message.reply_text(
            f"متن تشخیص داده‌شده:\n\n{cleaned_text}\n\nآیا مایل هستید این گزارش نهایی شود؟",
        )

        # Provide a confirm step
        keyboard = [
            [
                InlineKeyboardButton("بله، ثبت شود", callback_data="confirm_post"),
                InlineKeyboardButton("خیر، انصراف", callback_data="cancel"),
            ],
        ]
        update.message.reply_markup = InlineKeyboardMarkup(keyboard)
        return CONFIRM_POST

    def handle_confirm_post(self, update: Update, context: CallbackContext) -> int:
        """
        1) Combine the selected tasks with the transcribed text in a final LLM chain,
        2) Post the final text to Jira as a comment (or a new ‘report’ issue).
        """
        query = update.callback_query
        query.answer()
        if query.data == "confirm_post":
            transcribed_text = context.user_data.get("transcribed_text", "")
            selected_task_keys = list(context.user_data["report_task_keys"])

            # Build a helpful string about the tasks for the final prompt
            tasks_formatted = []
            for k in selected_task_keys:
                try:
                    issue = self.jira_repo.jira.issue(k)
                    tasks_formatted.append(f"- {k}: {issue.fields.summary}")
                except Exception as e:
                    LOGGER.error(f"Error fetching task {k}: {e}")
                    pass
            task_list_str = "\n".join(tasks_formatted)

            # Run the final LLM summarization
            final_persian_report = self.summary_chain.run(
                transcribed_text=transcribed_text,
                task_list=task_list_str,
            )

            # Post the final text to each selected task as a comment
            for key in selected_task_keys:
                self.jira_repo.add_comment(key, final_persian_report)

            query.edit_message_text(
                f"✅ گزارش شما ارسال شد.\n\n{final_persian_report[:2000]}",  # show snippet
            )
        else:
            query.edit_message_text("گزارش لغو شد.")
        return ConversationHandler.END

    def cancel(self, update: Update, context: CallbackContext) -> int:
        """
        Cancels the conversation.
        """
        update.message.reply_text("عملیات گزارش لغو شد.")
        return ConversationHandler.END
