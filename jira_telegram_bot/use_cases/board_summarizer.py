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
    llm = ChatOpenAI(model_name="o3-mini", openai_api_key=settings.token)
    prompt = PromptTemplate(
        input_variables=["grouped_tasks"],
        template="""
     شما لیستی از وظایف دارید که بازبینی یا تکمیل شده‌اند:

{grouped_tasks}

هر وظیفه شامل اطلاعات زیر است:
- Assignee (شخص مسئول)
- Summary (خلاصه کار)
- Component (دپارتمان، در صورت وجود)
- Epic (اپیک، در صورت وجود)
- Release Version (نسخه انتشار، در صورت وجود)

لطفاً یک خلاصه نهایی به **زبان فارسی** برای این وظایف بنویسید و از دستورالعمل‌های زیر پیروی کنید:

1. **گروه‌بندی وظایف بر اساس Component (دپارتمان)**:
   - هر دپارتمان را با عنوان «گروه» مشخص کنید.
   - اگر یک وظیفه دارای دپارتمان نیست، آن را در گروهی با عنوان **«بدون دپارتمان»** قرار دهید.

   **مثال ساختار کلی:**
   ────────────────────────────────
   **گروه: [نام دپارتمان]**
   - اپیک: [نام اپیک]
     - [خلاصه کار]
       (مسئول: [نام مسئول]، نسخه: [در صورت وجود])
     - [خلاصه کار دوم]
       (مسئول: [نام مسئول]، نسخه: [در صورت وجود])
   - **خلاصه**: [توضیح مختصر از کارهای انجام شده و دستاوردها]
   ────────────────────────────────

2. **زیرگروه‌بندی وظایف هر دپارتمان بر اساس Epic**:
   - اگر یک وظیفه دارای اپیک است، آن را در زیرگروه مربوط به آن اپیک قرار دهید.
   - اگر اپیک مشخص نیست، آن وظیفه را در زیرگروه **«بدون اپیک»** قرار دهید.

3. **فرمت نمایش وظایف**:
   - هر وظیفه را در یک خط مجزا ذکر کنید و از نمادها یا ایموجی‌ها برای تفکیک و جذابیت استفاده کنید. برای مثال:
     - «➖» یا «•» یا هر ایموجی مناسب برای ذکر وظیفه.
   - اگر **نسخه** موجود نباشد یا *None* باشد، به‌کلی آن را ذکر نکنید.
   - در داخل پرانتز، مسئول را با برچسب *مسئول* بیاورید، و فقط در صورتی که نسخه معتبر داشتید، نسخه را هم بیاورید.

   **نمونه قالب برای هر وظیفه**:
[عنوان وظیفه] (مسئول: [نام], نسخه: [در صورت وجود])
یا:
➖ [عنوان وظیفه] (مسئول: [نام], نسخه: [در صورت وجود])


4. **خلاصه پایانی در انتهای هر زیرگروه (Epic)**:
- با عنوان **«📄 خلاصه»** یا هر عنوان مناسب دیگر، یک توضیح مختصر بنویسید که:
  - چه کسی یا چه کسانی در این گروه فعالیت داشتند.
  - تمرکز اصلی تغییرات یا بهبودها چه بوده است.
  - دستاوردها یا نتایج اصلی چه بوده‌اند.

5. **خلاصه کلی نهایی در انتهای تمام گروه‌ها**:
- در انتها، یک جمع‌بندی از کل پروژه ارائه کنید که چگونه دپارتمان‌های مختلف (یا بدون دپارتمان) در کنار هم پروژه را پیش برده‌اند.
- می‌توانید از ایموجی‌ها برای جلوه بیشتر استفاده کنید؛ برای مثال:
  ```
  ✅ نتیجه‌گیری کلی:
  هر گروه با تمرکز بر حیطه تخصصی خود...
  ```
- ساختار مناسبی برای جدا کردن هر گروه و خلاصه پایانی رعایت کنید (خط تفکیک، ایموجی، یا موارد دیگر).

6. **نمونه‌ای از استایل خروجی** (به صورت خلاصه):
🔰 خلاصه نهایی وظایف پروژه 🔰 ──────────────────────────── 🏷️ گروه: بدون دپارتمان

اپیک: بدون اپیک • [نام وظیفه] (مسئول: [نام], نسخه: [در صورت وجود]) • [نام وظیفه دیگر] (مسئول: [نام], نسخه: [در صورت وجود])

📄 خلاصه: در این بخش، [نام افراد] با تمرکز بر [حوزه] تغییرات مهمی اعمال کرده‌اند که ...

──────────────────────────── 🏷️ گروه: [نام دپارتمان]

اپیک: بدون اپیک ...
✅ نتیجه‌گیری کلی: ...


**⚠️ نکات مهم**:
- از **ایموجی‌ها** برای جذابیت استفاده کنید.
- از بولد (**...**) برای تیترها یا عبارات کلیدی.
- از ایتالیک (*...*) در صورت نیاز برای تأکید.
- اطلاعات را به‌صورت منسجم و کاملاً خوانا بنویسید.
- در صورت خالی بودن یا *None* بودن **Release Version**، از نوشتن آن صرف‌نظر کنید.

        """,
    )
    llm_chain = LLMChain(llm=llm, prompt=prompt)
    return llm_chain
