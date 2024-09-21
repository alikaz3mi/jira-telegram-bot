from __future__ import annotations

import string
from io import BytesIO

import aiohttp
from jira import JIRA
from telegram import InlineKeyboardButton
from telegram import InlineKeyboardMarkup
from telegram import Update
from telegram.ext import CallbackContext
from telegram.ext import ConversationHandler

from jira_telegram_bot import LOGGER
from jira_telegram_bot.settings import JIRA_SETTINGS
from jira_telegram_bot.use_cases.authentication import check_user_allowed


class JiraTaskCreation:
    def __init__(self, jira: JIRA):
        self.jira = jira

        (
            self.PROJECT,
            self.SUMMARY,
            self.DESCRIPTION,
            self.COMPONENT,
            self.ASSIGNEE,
            self.PRIORITY,
            self.SPRINT,
            self.EPIC,
            self.TASK_TYPE,
            self.STORY_POINTS,
            self.IMAGE,
            self.STORY_SELECTION,
        ) = range(12)

        self.PRIORITIES = self.jira.priorities()
        self.STORY_POINTS_VALUES = [0.5, 1, 1.5, 2, 2.5, 3, 3.5, 4.0, 7]

        # Initialize variables that depend on the selected project
        self.JIRA_PROJECT_KEY = None
        self.EPICS = []
        self.BOARD_ID = None
        self.SPRINTS = []
        self.LATEST_SPRINT = None
        self.TASK_TYPES = []

    def _get_epics(self, project_key):
        return [
            epic
            for epic in self.jira.search_issues(
                f'project={project_key} AND issuetype=Epic AND status in ("To Do", "In Progress")',
            )
        ]

    def _get_board_id(self, project_key):
        return next(
            (board.id for board in self.jira.boards() if project_key in board.name),
            None,
        )

    def _get_latest_sprint(self, sprints):
        return next(
            (sprint for sprint in sprints if sprint.state == "active"),
            sprints[-1] if sprints else None,
        )

    def _get_assignees(self, project_key):
        try:
            # Try to get users from project roles
            assignees = set()
            recent_issues = self.jira.search_issues(
                f"project = {project_key} AND createdDate > startOfMonth(-1)",
            )
            for issue in recent_issues:
                if issue.fields.assignee:
                    assignees.add(issue.fields.assignee.name)

            if assignees:
                return sorted(assignees)
            else:
                return self._get_all_users()
        except Exception as e:
            LOGGER.error(f"Error fetching assignees for project {project_key}: {e}")
            # Fallback to all users
            return self._get_all_users()

    def _get_all_users(self):
        try:
            all_users = []
            for char in string.ascii_lowercase:
                users = self.jira.search_users(char, maxResults=1000)
                all_users.extend(users)
            all_users = list(set(all_users))
            return sorted({user.displayName for user in all_users})
        except Exception as e:
            LOGGER.error(f"Error fetching all users: {e}")
            return []

    def build_inline_keyboard(self, items, callback_data_skip="skip", row_size=2):
        """Helper function to build an inline keyboard."""
        keyboard = [
            [
                InlineKeyboardButton(item.name, callback_data=item.name)
                if hasattr(item, "name")
                else InlineKeyboardButton(item, callback_data=item)
                for item in items[i : i + row_size]
            ]
            for i in range(0, len(items), row_size)
        ]
        keyboard.append(
            [InlineKeyboardButton("Skip", callback_data=callback_data_skip)],
        )
        return InlineKeyboardMarkup(keyboard)

    async def select_project(self, update: Update, context: CallbackContext) -> int:
        if not await check_user_allowed(update):
            return ConversationHandler.END

        # Fetch projects from Jira
        projects = self.jira.projects()

        # Build the keyboard with project names
        keyboard = [
            [
                InlineKeyboardButton(project.name, callback_data=project.key)
                for project in projects[i : i + 2]
            ]
            for i in range(0, len(projects), 2)
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            "Please select a project from the list below:",
            reply_markup=reply_markup,
        )
        return self.PROJECT

    async def select_project_callback(
        self,
        update: Update,
        context: CallbackContext,
    ) -> int:
        query = update.callback_query
        await query.answer()

        project_key = query.data
        context.user_data["project_key"] = project_key

        LOGGER.info("Project selected: %s", project_key)

        # Initialize project-specific variables
        self.JIRA_PROJECT_KEY = project_key
        self.EPICS = self._get_epics(project_key)
        self.BOARD_ID = self._get_board_id(project_key)
        if self.BOARD_ID:
            self.SPRINTS = self.jira.sprints(board_id=self.BOARD_ID)
        else:
            self.SPRINTS = []
        self.LATEST_SPRINT = self._get_latest_sprint(self.SPRINTS)
        self.TASK_TYPES = [
            z.name for z in self.jira.issue_types_for_project(self.JIRA_PROJECT_KEY)
        ]

        await query.edit_message_text("Please enter the task summary:")
        return self.SUMMARY

    async def add_summary(self, update: Update, context: CallbackContext) -> int:
        if not await check_user_allowed(update):
            return ConversationHandler.END

        user = update.message.from_user
        task_summary = update.message.text
        context.user_data["task_summary"] = task_summary

        LOGGER.info("User %s sent a summary: %s", user.first_name, task_summary)
        await update.message.reply_text(
            'Got it! Now send me the description of the task (or type "skip" to skip).',
        )

        return self.DESCRIPTION

    async def add_description(self, update: Update, context: CallbackContext) -> int:
        if not await check_user_allowed(update):
            return ConversationHandler.END

        task_description = (
            update.message.text if update.message.text.lower() != "skip" else ""
        )
        context.user_data["task_description"] = task_description

        LOGGER.info("Description received: %s", task_description)

        # Fetch components from Jira
        components = self.jira.project_components(self.JIRA_PROJECT_KEY)

        if components:
            # Build components keyboard
            keyboard = [
                [
                    InlineKeyboardButton(component.name, callback_data=component.name)
                    for component in components[i : i + 2]
                ]
                for i in range(0, len(components), 2)
            ]
            keyboard.append([InlineKeyboardButton("Skip", callback_data="skip")])
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text(
                "Got it! Now choose a component from the list below:",
                reply_markup=reply_markup,
            )
            return self.COMPONENT
        else:
            LOGGER.info("No components found for project %s", self.JIRA_PROJECT_KEY)
            await update.message.reply_text(
                "No components found. Proceeding to the next step.",
            )
            return await self.skip_component(update, context)

    async def button_component(self, update: Update, context: CallbackContext) -> int:
        query = update.callback_query
        await query.answer()
        context.user_data["component"] = query.data if query.data != "skip" else None

        LOGGER.info("Component selected: %s", context.user_data["component"])

        # Fetch assignees from the project
        assignees = self._get_assignees(self.JIRA_PROJECT_KEY)

        if assignees:
            keyboard = [
                [
                    InlineKeyboardButton(assignee, callback_data=assignee)
                    for assignee in assignees[i : i + 3]
                ]
                for i in range(0, len(assignees), 3)
            ]
            keyboard.append([InlineKeyboardButton("Skip", callback_data="skip")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "Got it! Now choose an assignee from the list below:",
                reply_markup=reply_markup,
            )
            return self.ASSIGNEE
        else:
            LOGGER.info("No assignees found for project %s", self.JIRA_PROJECT_KEY)
            await query.edit_message_text(
                "No assignees found. Proceeding to the next step.",
            )
            return await self.skip_assignee(update, context)

    async def button_assignee(self, update: Update, context: CallbackContext) -> int:
        query = update.callback_query
        await query.answer()
        context.user_data["assignee"] = query.data if query.data != "skip" else None

        LOGGER.info("Assignee selected: %s", context.user_data["assignee"])

        reply_markup = self.build_inline_keyboard(self.PRIORITIES, row_size=3)
        await query.edit_message_text(
            "Got it! Now choose a priority from the list below:",
            reply_markup=reply_markup,
        )

        return self.PRIORITY

    async def button_priority(self, update: Update, context: CallbackContext) -> int:
        query = update.callback_query
        await query.answer()
        context.user_data["priority"] = query.data if query.data != "skip" else None

        LOGGER.info("Priority selected: %s", context.user_data["priority"])

        if self.LATEST_SPRINT:
            keyboard = [
                [
                    InlineKeyboardButton(
                        self.LATEST_SPRINT.name,
                        callback_data=str(self.LATEST_SPRINT.id),
                    ),
                ],
                [InlineKeyboardButton("Skip", callback_data="skip")],
            ]

            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "Got it! Now choose a sprint from the list below:",
                reply_markup=reply_markup,
            )
            return self.SPRINT
        else:
            LOGGER.info("No active sprint found for project %s", self.JIRA_PROJECT_KEY)
            await query.edit_message_text(
                "No active sprint found. Proceeding to the next step.",
            )
            return await self.skip_sprint(update, context)

    async def button_sprint(self, update: Update, context: CallbackContext) -> int:
        query = update.callback_query
        await query.answer()
        context.user_data["sprint"] = query.data if query.data != "skip" else None

        LOGGER.info("Sprint selected: %s", context.user_data["sprint"])

        if self.EPICS:
            keyboard = []
            for i in range(0, len(self.EPICS), 3):
                row = [
                    InlineKeyboardButton(
                        epic.fields.summary,
                        callback_data=epic.key,
                    )
                    for epic in self.EPICS[i : i + 3]
                ]
                keyboard.append(row)
            keyboard.append([InlineKeyboardButton("Skip", callback_data="skip")])

            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "Got it! Now choose an epic from the list below:",
                reply_markup=reply_markup,
            )
            return self.EPIC
        else:
            LOGGER.info("No epics found for project %s", self.JIRA_PROJECT_KEY)
            await query.edit_message_text(
                "No epics found. Proceeding to the next step.",
            )
            return await self.skip_epic(update, context)

    async def button_epic(self, update: Update, context: CallbackContext) -> int:
        query = update.callback_query
        await query.answer()
        context.user_data["epic"] = query.data if query.data != "skip" else None

        LOGGER.info("Epic selected: %s", context.user_data["epic"])

        keyboard = [
            [
                InlineKeyboardButton(task_type, callback_data=task_type)
                for task_type in self.TASK_TYPES[i : i + 3]
            ]
            for i in range(0, len(self.TASK_TYPES), 3)
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "Got it! Now choose a task type from the list below:",
            reply_markup=reply_markup,
        )

        return self.TASK_TYPE

    async def button_task_type(self, update: Update, context: CallbackContext) -> int:
        query = update.callback_query
        await query.answer()
        context.user_data["task_type"] = query.data

        LOGGER.info("Task type selected: %s", context.user_data["task_type"])

        if query.data.lower() == "sub-task":
            # Fetch stories from the current sprint or project backlog
            jql = f'project="{self.JIRA_PROJECT_KEY}" AND issuetype=Story'
            if self.LATEST_SPRINT:
                jql += f' AND sprint="{self.LATEST_SPRINT.name}"'
            stories = self.jira.search_issues(jql)

            if not stories:
                await query.edit_message_text(
                    "No stories found in the current sprint or project.",
                )
                return ConversationHandler.END

            keyboard = [
                [
                    InlineKeyboardButton(
                        story.fields.summary,
                        callback_data=story.key,
                    )
                    for story in stories[i : i + 2]
                ]
                for i in range(0, len(stories), 2)
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                "Got it! Now choose a story to assign this sub-task:",
                reply_markup=reply_markup,
            )

            return self.STORY_SELECTION  # New state for story selection
        else:
            keyboard = [
                [
                    InlineKeyboardButton(str(sp), callback_data=str(sp))
                    for sp in self.STORY_POINTS_VALUES[i : i + 3]
                ]
                for i in range(0, len(self.STORY_POINTS_VALUES), 3)
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                "Got it! Now choose the story points:",
                reply_markup=reply_markup,
            )

            return self.STORY_POINTS

    async def button_story_selection(
        self,
        update: Update,
        context: CallbackContext,
    ) -> int:
        query = update.callback_query
        await query.answer()
        context.user_data["story"] = query.data

        LOGGER.info("Story selected for sub-task: %s", context.user_data["story"])

        keyboard = [
            [
                InlineKeyboardButton(str(sp), callback_data=str(sp))
                for sp in self.STORY_POINTS_VALUES[i : i + 3]
            ]
            for i in range(0, len(self.STORY_POINTS_VALUES), 3)
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            "Got it! Now choose the story points:",
            reply_markup=reply_markup,
        )

        return self.STORY_POINTS

    async def button_story_points(
        self,
        update: Update,
        context: CallbackContext,
    ) -> int:
        query = update.callback_query
        await query.answer()
        context.user_data["story_points"] = float(query.data)

        LOGGER.info("Story points selected: %s", context.user_data["story_points"])

        await query.edit_message_text(
            "Got it! Now send me one or more images, or type 'skip' if you don't want to attach any images.",
        )
        return self.IMAGE

    async def handle_image(self, update: Update, context: CallbackContext) -> int:
        if not await check_user_allowed(update):
            return ConversationHandler.END

        if update.message.text and update.message.text.lower() == "skip":
            LOGGER.info("User chose to skip image upload.")
            await self.finalize_task(update, context)
            return ConversationHandler.END

        if update.message.photo:
            image_files = sorted(update.message.photo, key=lambda x: x.file_size)
            image_streams = []

            async with aiohttp.ClientSession() as session:
                for photo in image_files[len(image_files) // 2 :]:
                    photo_file = await photo.get_file()
                    async with session.get(photo_file.file_path) as response:
                        if response.status == 200:
                            image_streams.append(BytesIO(await response.read()))
                        else:
                            LOGGER.error(
                                f"Failed to fetch image from {photo_file.file_path}",
                            )

            LOGGER.info("Images received")
            await self.finalize_task(update, context, image_streams)
            return ConversationHandler.END

        await update.message.reply_text(
            "No images found. Please send one or more images or type 'skip' to skip.",
        )
        return self.IMAGE

    async def finalize_task(
        self,
        update: Update,
        context: CallbackContext,
        image_streams=None,
    ) -> int:
        task_data = {
            "summary": context.user_data.get("task_summary"),
            "description": context.user_data.get("task_description"),
            "component": context.user_data.get("component"),
            "assignee": context.user_data.get("assignee"),
            "priority": context.user_data.get("priority"),
            "sprint": context.user_data.get("sprint"),
            "epic": context.user_data.get("epic"),
            "task_type": context.user_data.get("task_type"),
            "story_points": context.user_data.get("story_points"),
            "story": context.user_data.get("story"),
            "project_key": context.user_data.get("project_key"),
        }

        if not task_data["summary"]:
            await update.message.reply_text("Please send the task summary first.")
            LOGGER.info("Summary not provided")
            return self.SUMMARY

        issue_fields = {
            "project": {"key": task_data["project_key"]},
            "summary": task_data["summary"],
            "description": task_data["description"],
            "issuetype": {"name": task_data["task_type"]},
        }

        if task_data["task_type"].lower() == "sub-task":
            if task_data["story"]:
                issue_fields["parent"] = {"key": task_data["story"]}
        else:
            if task_data["epic"]:
                issue_fields["customfield_10100"] = task_data["epic"]

            if task_data["sprint"]:
                issue_fields["customfield_10104"] = int(task_data["sprint"])

            if task_data["story_points"]:
                issue_fields["customfield_10106"] = task_data["story_points"]

        if task_data["component"]:
            component = next(
                (
                    c
                    for c in self.jira.project_components(task_data["project_key"])
                    if c.name == task_data["component"]
                ),
                None,
            )
            if component:
                issue_fields["components"] = [{"id": component.id}]

        if task_data["assignee"]:
            issue_fields["assignee"] = {"name": task_data["assignee"]}

        if task_data["priority"]:
            issue_fields["priority"] = {"name": task_data["priority"]}

        LOGGER.info("Creating Jira issue with fields: %s", issue_fields)
        new_issue = self.jira.create_issue(fields=issue_fields)
        LOGGER.info("Jira issue created: %s", new_issue.key)

        # If it's a sub-task, update the parent story's components
        if task_data["task_type"].lower() == "sub-task" and task_data["story"]:
            parent_issue = self.jira.issue(task_data["story"])
            existing_components = {c.name for c in parent_issue.fields.components}
            if task_data["component"]:
                existing_components.add(task_data["component"])
                parent_issue.update(
                    fields={"components": [{"name": c} for c in existing_components]},
                )
                LOGGER.info(
                    "Updated components of the parent story %s: %s",
                    task_data["story"],
                    existing_components,
                )

        if image_streams:
            for image_stream in image_streams:
                self.jira.add_attachment(
                    issue=new_issue,
                    attachment=image_stream,
                    filename="task_image.jpg",
                )
            LOGGER.info("Images attached to Jira issue")

        await update.message.reply_text(
            f"Task created successfully! Link: {JIRA_SETTINGS.domain}/browse/{new_issue.key}",
        )
        return ConversationHandler.END

    # Helper methods to skip steps if necessary
    async def skip_component(self, update: Update, context: CallbackContext) -> int:
        context.user_data["component"] = None
        LOGGER.info("Component skipped.")
        return await self.button_component(update, context)

    async def skip_assignee(self, update: Update, context: CallbackContext) -> int:
        context.user_data["assignee"] = None
        LOGGER.info("Assignee skipped.")
        return await self.button_assignee(update, context)

    async def skip_sprint(self, update: Update, context: CallbackContext) -> int:
        context.user_data["sprint"] = None
        LOGGER.info("Sprint skipped.")
        return await self.button_sprint(update, context)

    async def skip_epic(self, update: Update, context: CallbackContext) -> int:
        context.user_data["epic"] = None
        LOGGER.info("Epic skipped.")
        return await self.button_epic(update, context)
