from __future__ import annotations

from collections import defaultdict
from typing import Dict
from typing import List

from langchain import LLMChain
from langchain import PromptTemplate
from langchain_openai import ChatOpenAI

from jira_telegram_bot.entities.task import TaskData
from jira_telegram_bot.use_cases.interfaces.summary_generator_interface import (
    ISummaryGenerator,
)
from jira_telegram_bot.use_cases.interfaces.task_grouper_interface import ITaskGrouper


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
شما یک فهرست از وظایف (Tasks) دارید که بررسی یا تکمیل شده‌اند. اطلاعات هر وظیفه شامل این موارد است:

Assignee (شخص مسئول)
Summary (خلاصه کار)
Component (دپارتمان، در صورت وجود)
Epic (اپیک، در صورت وجود)
Release Version (نسخه انتشار، در صورت وجود)
ورودی شما در قالب متغیری با نام {grouped_tasks} ارائه می‌شود که حاوی کلیهٔ وظایف و جزئیات آن‌هاست.

لطفاً خروجی نهایی را به زبان فارسی آماده کنید تا در تلگرام قابل خواندن و جذاب باشد. دستورالعمل‌ها به شکل زیر است:

گروه‌بندی بر اساس دپارتمان (Component)

هر دپارتمان را با عنوان **گروه: [نام دپارتمان]** مشخص کنید.
اگر دپارتمان خالی یا None بود، وظیفه را زیر **بدون دپارتمان** قرار دهید.
زیرگروه‌بندی بر اساس اپیک (Epic)

در هر گروه (دپارتمان)، وظایف را براساس اپیک تفکیک کنید.
اگر اپیک خالی یا None بود، از **بدون اپیک** استفاده کنید.
فرمت نمایش وظایف

هر وظیفه را در یک خط مجزا بنویسید.
از نماد یا ایموجی (مثلاً ➖ یا •) ابتدای خط برای جذابیت استفاده کنید.
در ادامه، نام وظیفه را بین براکت بنویسید: [خلاصه وظیفه]
در پرانتز، مسئول را با کلیدواژه مسئول: ذکر کنید. اگر نسخه (Release Version) موجود بود، بعد از آن با کلیدواژه نسخه: اضافه کنید.
مثال وجود نسخه:

➖ [خلاصه کار] (مسئول: [نام], نسخه: [شماره نسخه])

مثال عدم وجود نسخه:

➖ [خلاصه کار] (مسئول: [نام])
خلاصهٔ پایانی در هر اپیک

پس از اتمام وظایف مرتبط با یک اپیک، یک خلاصهٔ مختصر با عنوانی مثل 📄 خلاصه: اضافه کنید.
در این بخش، به دستاوردها، افراد کلیدی و تمرکز اصلی اشاره نمایید.
نتیجه‌گیری کلی

در پایان تمام گروه‌ها، یک خلاصهٔ جامع با عنوانی مانند:

✅ نتیجه‌گیری کلی:
بنویسید تا بیانگر هماهنگی بین گروه‌ها و دستاورد نهایی باشد.
استایل و نکات پایانی

می‌توانید از Bold برای تیترها و ایتالیک برای تأکید استفاده کنید.
از ایموجی‌ها بهره ببرید تا متن جذاب‌تر شود.
ساختار را با خط تفکیک (────────────────────────────) یا هر روش مناسب دیگر خوانا نگه دارید.
اگر فیلد Epic یا Release Version خالی یا None بود، آن را نادیده بگیرید و اصلاً ذکر نکنید.
نمونه خروجی پیشنهادی
less
Copy
Edit
🔰 خلاصه نهایی وظایف پروژه 🔰
────────────────────────────
🏷️ گروه: بدون دپارتمان

اپیک: بدون اپیک
➖ [نام وظیفه اول] (مسئول: [نام], نسخه: [۱.۰])
➖ [نام وظیفه دوم] (مسئول: [نام])

📄 خلاصه:
در این بخش، [نام افراد درگیر] با تمرکز بر [اهداف اصلی]، تغییرات قابل ملاحظه‌ای انجام دادند...

────────────────────────────
🏷️ گروه: [نام دپارتمان]

اپیک: [نام اپیک]
➖ [نام وظیفه] (مسئول: [نام])
➖ ...

📄 خلاصه:
...

✅ نتیجه‌گیری کلی:
[چکیده‌ای از همکاری بین گروه‌ها و دستاورد نهایی] """,
    )
    llm_chain = LLMChain(llm=llm, prompt=prompt)
    return llm_chain
