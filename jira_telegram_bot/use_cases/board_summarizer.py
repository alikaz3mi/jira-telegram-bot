from __future__ import annotations

from collections import defaultdict
from typing import Dict
from typing import List

from langchain import LLMChain
from langchain import PromptTemplate
from langchain_openai import ChatOpenAI

from jira_telegram_bot.entities.task import TaskData
from jira_telegram_bot.use_cases.interface.summary_generator_interface import (
    ISummaryGenerator,
)
from jira_telegram_bot.use_cases.interface.task_grouper_interface import ITaskGrouper


class TaskGrouper(ITaskGrouper):
    def group_tasks(
        self,
        tasks: List[TaskData],
    ) -> Dict[str, Dict[str, List[TaskData]]]:
        component_groups = defaultdict(lambda: defaultdict(list))
        for task in tasks:
            component_key = (
                task.component if task.component else "no executive department"
            )
            epic_key = task.epics if task.epics else "no epic"
            component_groups[component_key][epic_key].append(task)
        return component_groups


class SummaryGenerator(ISummaryGenerator):
    def __init__(self, llm_chain: LLMChain):
        self.llm_chain = llm_chain

    def generate_summary(
        self,
        grouped_tasks: Dict[str, Dict[str, List[TaskData]]],
    ) -> str:
        summaries = []
        for component, epics in grouped_tasks.items():
            component_summary = f"**executive department: {component}**\n"
            for epic, tasks in epics.items():
                epic_summary = f"  - **epic: {epic}**\n"
                for task in tasks:
                    task_summary = (
                        f"task {task.summary}"
                        f"    - وظیفه توسط {task.assignee} برای نسخه {task.release} انجام شد. "
                        f"جزئیات: {task.description}\n"
                    )
                    epic_summary += task_summary
                component_summary += epic_summary
            summaries.append(component_summary)
        final_summary = "\n".join(summaries)
        response = self.llm_chain.run(final_summary)
        return response


class TaskProcessor:
    def __init__(
        self,
        llm_chain: LLMChain,
        grouper: ITaskGrouper = None,
        generator: ISummaryGenerator = None,
    ):
        self.grouper = grouper if grouper else TaskGrouper()
        self.generator = generator if generator else SummaryGenerator(llm_chain)

    def process_tasks(self, tasks: List[TaskData]) -> str:
        grouped_tasks = self.grouper.group_tasks(tasks)
        summary = self.generator.generate_summary(grouped_tasks)
        return summary


def create_llm_chain(settings):
    llm = ChatOpenAI(model_name="gpt-4o-mini", openai_api_key=settings.token)
    prompt = PromptTemplate(
        input_variables=["grouped_tasks"],
        template="""
        You are provided with a list of tasks that have been reviewed or completed.

        {grouped_tasks}

        ---------
        Each task contains the following information:

        - **Assignee**
        - **Summary**
        - **Component** (if any)
        - **Epic** (if any)
        - **Release Version**

        Please write a summary in **Persian** for these tasks by following these instructions:

        1. **Group the tasks by component**:
        - If a task has a component, include it in the respective component group.
        - If a task does not have a component, place it under a group titled "بدون دپارتمان".

        **Example**:
        - Component: `UI`
            - Tasks might include: "بهبود صفحه ورود", "به‌روزرسانی رنگ‌بندی فرم ثبت‌نام"
        - Component: `Backend`
            - Tasks might include: "افزایش سرعت جستجو در پایگاه داده", "رفع مشکل ذخیره‌سازی اطلاعات کاربر"
        - "بدون دپارتمان"
            - Tasks might include: "بررسی مستندات پروژه", "هماهنگی با تیم طراحی"

        2. **Within each component**, **group the tasks by epic**:
        - If a task has an epic, include it in the respective epic group.
        - If a task does not have an epic, place it under a group titled "بدون اپیک".

        **Example**:
        - For Component `UI`, you might have:
            - Epic: `بهبود تجربه کاربری (UX Improvements)`
            - Tasks: "بهبود صفحه ورود" (Assignee: Ali, Release: 1.2.0), "به‌روزرسانی رنگ‌بندی فرم ثبت‌نام" (Assignee: Sara, Release: 1.2.0)
            - Epic: `بدون اپیک`
            - Tasks: "بررسی آیکون‌های دکمه‌ها" (Assignee: Reza, Release: 1.1.0)

        3. **For each group**, provide a concise summary that includes:
        - The names of the assignees.
        - The release version.
        - Key details or achievements of the tasks in that group.

        **Example Summary**:
        - For the `UI` Component under `بهبود تجربه کاربری` Epic:
            - "در این گروه، علی و سارا در نسخه 1.2.0 روی بهینه‌سازی فرم‌های ورود و ثبت‌نام کار کرده‌اند که منجر به سهولت بیشتر کاربر در ثبت اطلاعات شده است."

        - For the `UI` Component under `بدون اپیک`:
            - "رضا در نسخه 1.1.0 آیکون‌های دکمه‌ها را بررسی و اصلاح کرده است که منجر به ظاهری یکپارچه‌تر شده است."

        - For the `بدون دپارتمان` Component under `بدون اپیک`:
            - "در این بخش، علی در نسخه 1.0.0 مستندات را بررسی کرده و هماهنگی بین تیم‌ها را بهبود داده است."

        Ensure the final summary is well-organized and written in clear Persian. The summary must be informative and reflect all given tasks appropriately.


        """,
    )
    llm_chain = LLMChain(llm=llm, prompt=prompt)
    return llm_chain
