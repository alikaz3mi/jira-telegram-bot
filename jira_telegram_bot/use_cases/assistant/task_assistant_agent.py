"""A LangGraph agent that answers questions about a person's Jira work.

The agent decides which tool to call and with what arguments; it never
decides who it is talking to. Identity is bound when the tool set is built,
so "what should Ms. Lotfian deliver today?" resolves the name, checks the
caller's role in Python, and refuses or answers accordingly — a decision the
model has no way to influence.
"""
from __future__ import annotations

import asyncio
from typing import List

from langchain.agents import create_agent
from langchain_core.messages import AIMessage
from langchain_core.messages import HumanMessage
from langchain_core.tools import StructuredTool

from jira_telegram_bot import LOGGER
from jira_telegram_bot.entities.daily_task_tracking.conversation_turn import (
    ConversationMemory,
)
from jira_telegram_bot.use_cases.assistant.assistant_tools import AssistantTools

# A tool loop that never converges must not leave somebody watching a
# spinner. Long enough for several Jira round trips, short enough to fail
# while the person is still reading.
ANSWER_TIMEOUT_SECONDS = 90

SYSTEM_PROMPT = """\
تو دستیار جیرای یک تیم مهندسی هستی و به سؤال‌های اعضا درباره تسک‌هایشان
پاسخ می‌دهی.

قواعد:

- همیشه از ابزارها استفاده کن. هرگز از حافظه‌ات درباره تسک‌ها حدس نزن.
- وقتی کاربر نام محصول یا شخصی را می‌آورد، همان را عیناً به ابزار بده؛
  ابزار خودش آن را به کلید جیرا تبدیل می‌کند. تو کلید جیرا را حدس نزن.
- خروجی ابزار را همان‌طور که هست برگردان. لینک‌های <a href> را دست‌نخورده
  نگه دار و هیچ تگ HTML دیگری اضافه نکن.
- کوتاه جواب بده. این پیام در تلگرام و روی موبایل خوانده می‌شود:
  بدون مقدمه، بدون تکرار سؤال، بدون جمع‌بندی اضافه.
- وقتی توضیح یک تسک از استوری یا اپیک والد می‌آید، اول با یک جمله بگو آن
  استوری چیست و عنوانش را با لینک بیاور — «این تسک بخشی از استوری
  <a …>KEY</a> «عنوان» است» — بعد بگو خودِ این تسک چه سهمی از آن دارد.
  کاربر باید بفهمد کار در چه زمینه‌ای است، نه فقط فهرست کارها را ببیند.
- اگر تسک وابستگی دارد (blocks / is blocked by)، آن را بگو؛ همان تعیین
  می‌کند الان می‌شود شروع کرد یا باید منتظر ماند.
- اگر ابزار گفت اجازه دسترسی نیست، همان را بگو و توجیه نکن.
- به زبان کاربر جواب بده. سؤال فارسی، پاسخ فارسی.
- اگر سؤال ادامه گفت‌وگوی قبلی است، به آن تکیه کن و فهرست قبلی را دوباره
  چاپ نکن؛ تأیید یا اصلاح کن.
- سؤال درباره «اسپرینت» یا «تیم» یا یک واحد کاری (طراحی، بک‌اند،
  فرانت، هوش، دواپس) با list_tasks جواب داده نمی‌شود؛ آن ابزار فقط
  تسک‌های خودِ کاربر را می‌بیند. برای این سؤال‌ها sprint_board را
  صدا بزن.
- «چه کاری هست» و «کی تمام می‌شود» دو سؤال جدا هستند و دو ابزار
  جدا دارند: محتوا با sprint_board، زمان با releases. اگر پیام
  کاربر هر دو را پرسید، هر دو ابزار را صدا بزن و هر دو را جواب بده؛
  جواب دادن به یکی و رها کردن دیگری یعنی نصف سؤال بی‌پاسخ مانده.
- هرگز فهرستی را با برچسبی که ابزار نداده معرفی نکن. اگر ابزار
  نگفت این تسک‌ها «طراحی» هستند، تو هم نگو.
"""


class TaskAssistantAgent:
    """Answers questions about tasks by calling scoped tools."""

    def __init__(self, model, alias_repository, get_user_daily_tasks_use_case,
                 base_url: str = "", task_manager_repository=None,
                 user_config_repository=None, rank_candidates_use_case=None):
        """Initialize the agent.

        Args:
            model: Chat model the agent reasons with
            alias_repository: Resolves names to Jira keys and usernames
            get_user_daily_tasks_use_case: Source of a person's open tasks
            base_url: Jira base URL, used to build issue links
            task_manager_repository: Reads parent Stories and Epics for a
                Sub-task that carries no description of its own
            user_config_repository: Maps people to their unit on a project,
                so "the design side" resolves to actual people
            rank_candidates_use_case: Ranks issues against a topic by
                meaning, for subject questions
        """
        self.model = model
        self.alias_repository = alias_repository
        self.get_user_daily_tasks = get_user_daily_tasks_use_case
        self.base_url = base_url
        self.task_manager_repository = task_manager_repository
        self.user_config_repository = user_config_repository
        self.rank_candidates = rank_candidates_use_case

    async def answer(
        self,
        question: str,
        context,
        memory: ConversationMemory = None,
        media_sink: List = None,
    ) -> str:
        """Answer one question as the given caller.

        Args:
            question: What the user asked
            context: Who is asking and what they may read
            memory: Recent turns, so a follow-up reads as a follow-up
            media_sink: List the tools append sendable attachments to; the
                caller sends them after the text

        Returns:
            The reply, ready to send as Telegram HTML.
        """
        tools = AssistantTools(
            context=context,
            get_user_daily_tasks_use_case=self.get_user_daily_tasks,
            alias_repository=self.alias_repository,
            base_url=self.base_url,
            task_manager_repository=self.task_manager_repository,
            user_config_repository=self.user_config_repository,
            media_sink=media_sink,
            rank_candidates_use_case=self.rank_candidates,
        )

        agent = create_agent(
            model=self.model,
            tools=self._build_tools(tools),
            system_prompt=SYSTEM_PROMPT,
        )

        try:
            result = await asyncio.wait_for(
                agent.ainvoke(
                    {
                        "messages": self._history(memory)
                        + [HumanMessage(content=question)],
                    },
                ),
                timeout=ANSWER_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            # Without this the tool loop can run until the user gives up,
            # leaving them looking at a "thinking" message that never
            # resolves. Failing visibly is the lesser harm.
            LOGGER.error(
                f"Assistant agent timed out after {ANSWER_TIMEOUT_SECONDS}s "
                f"on: {question[:80]}",
            )
            return ""
        except Exception as exc:
            LOGGER.error(f"Assistant agent failed: {exc}", exc_info=True)
            return ""

        for message in reversed(result.get("messages", [])):
            if isinstance(message, AIMessage) and message.content:
                return str(message.content).strip()
        return ""

    @staticmethod
    def _build_tools(tools: AssistantTools) -> List[StructuredTool]:
        """Expose the scoped tool set to the agent.

        The caller is already captured in ``tools``; none of these take a
        parameter that could redirect them at a different user.

        Args:
            tools: The per-request tool set

        Returns:
            The tools, described for the model.
        """
        return [
            StructuredTool.from_function(
                coroutine=tools.board_link,
                name="board_link",
                description=(
                    "لینک جیرا برای دیدن همه تسک‌های یک نفر. person نام شخص "
                    "(خالی یعنی خود کاربر)، project نام محصول. وقتی کاربر "
                    "لینک می‌خواهد یا می‌خواهد همه را خودش ببیند، از این "
                    "استفاده کن."
                ),
            ),
            StructuredTool.from_function(
                coroutine=tools.task_details,
                name="task_details",
                description=(
                    "توضیح کامل یک تسک: شرح کار، وضعیت، مهلت و وابستگی‌ها. "
                    "issue_key کلید جیرا مثل «FOLLOWUP-128». وقتی کاربر می‌پرسد "
                    "این تسک چیست یا چه کاری باید انجام دهد، از این استفاده کن."
                ),
            ),
            StructuredTool.from_function(
                coroutine=tools.list_tasks,
                name="list_tasks",
                description=(
                    "فهرست تسک‌های باز. person نام شخص همان‌طور که کاربر گفته "
                    "(خالی یعنی خود کاربر)، project نام محصول همان‌طور که گفته "
                    "(مثل «پارسچت» یا «آواخرد»)، status وضعیت جیرا، "
                    "issue_type نوع آیتم مثل Story یا Bug، "
                    "in_active_sprint=true فقط کارهای داخل اسپرینت جاری، "
                    "due_within_days تعداد روز تا مهلت. "
                    "دقت کن: «استوری‌های اسپرینت جاری» یعنی issue_type=Story "
                    "و in_active_sprint=true — این ربطی به status ندارد."
                ),
            ),
            StructuredTool.from_function(
                coroutine=tools.my_briefing,
                name="my_briefing",
                description=(
                    "خلاصه‌ی کار کاربر: اول باگ‌های فوری، بعد هدف اسپرینت "
                    "جاری بر اساس اپیک‌ها، بعد سهم خود کاربر با لینک. "
                    "project اختیاری است. برای سؤال‌های کلی مثل «تسک‌های من "
                    "چیه؟»، «امروز چیکار کنم؟»، «وضعیتم چطوره؟» از این "
                    "استفاده کن، نه از list_tasks — این تصویر کامل‌تری "
                    "می‌دهد و باگ فوری را جا نمی‌اندازد."
                ),
            ),
            StructuredTool.from_function(
                coroutine=tools.releases,
                name="releases",
                description=(
                    "ریلیزهای پیش‌رو یک پروژه: تاریخ تحویل، توضیح، و کارهای "
                    "بازی که هنوز مانده. project نام محصول، topic موضوع اگر "
                    "کاربر درباره چیز خاصی پرسید. "
                    "هر سؤالی درباره «کی» — کی تمام می‌شود، کی تحویل داده "
                    "می‌شود، کی وریفای می‌شود، ددلاین چیست — با این جواب "
                    "داده می‌شود، نه با sprint_board. تاریخ تحویل روی ریلیز "
                    "ثبت می‌شود نه روی اسپرینت."
                ),
            ),
            StructuredTool.from_function(
                coroutine=tools.sprint_board,
                name="sprint_board",
                description=(
                    "کارهای اسپرینت جاری یک پروژه برای کل تیم. "
                    "project نام محصول (مثل «پارسچت»)، "
                    "unit واحد کاری اگر کاربر گفت (مثل «طراحی»، «بک‌اند»، "
                    "«فرانت»، «هوش»، «دواپس»)، "
                    "person اگر درباره یک نفر خاص پرسید، "
                    "issue_type مثل Story، "
                    "topic موضوعی که کاربر پرسیده (مثل «اینستاگرام» یا "
                    "«سهمیه») — این با معنا جست‌وجو می‌کند نه با کلمه، پس "
                    "کارهای مرتبط با عبارت متفاوت را هم پیدا می‌کند. "
                    "اگر کاربر درباره یک موضوع پرسید حتماً topic را بده؛ "
                    "بدون آن کل اسپرینت برمی‌گردد و جواب اشتباه می‌شود. "
                    "برای هر سؤالی درباره «توی اسپرینت چه کاری هست» که "
                    "مخصوص خودِ کاربر نیست، حتماً از این استفاده کن — "
                    "list_tasks فقط تسک‌های خودِ کاربر را می‌بیند و برای "
                    "این سؤال‌ها جواب اشتباه می‌دهد."
                ),
            ),
            StructuredTool.from_function(
                coroutine=tools.sprint_epics,
                name="sprint_epics",
                description=(
                    "اپیک‌های اسپرینت جاری یک پروژه، همراه با استوری‌های زیر "
                    "هرکدام. project نام محصول همان‌طور که کاربر گفت (مثل "
                    "«خردیار»). برای سؤال‌هایی مثل «چه اپیک‌هایی در اسپرینت "
                    "جاری هستند؟» یا «از این اسپرینت چه چیزی آماده عرضه "
                    "می‌شود؟» حتماً از این استفاده کن. "
                    "اپیک‌ها assignee ندارند، پس هرگز با list_tasks پیدا "
                    "نمی‌شوند؛ list_tasks فقط تسک‌های خودِ افراد را می‌بیند."
                ),
            ),
            StructuredTool.from_function(
                coroutine=tools.count_tasks,
                name="count_tasks",
                description=(
                    "شمارش تسک‌های باز، با تفکیک پروژه. برای سؤال‌هایی مثل "
                    "«چند تا تسک دارم؟» از این استفاده کن، نه از فهرست کردن."
                ),
            ),
            StructuredTool.from_function(
                coroutine=tools.logged_hours,
                name="logged_hours",
                description=(
                    "مجموع ساعت‌های ثبت‌شده روی تسک‌های باز یک نفر."
                ),
            ),
            StructuredTool.from_function(
                func=tools.whoami,
                name="whoami",
                description=(
                    "کاربر فعلی و سطح دسترسی او. وقتی لازم است بدانی کاربر "
                    "کیست یا اجازه چه چیزی را دارد."
                ),
            ),
        ]

    @staticmethod
    def _history(memory: ConversationMemory = None) -> list:
        """Render remembered turns as chat messages.

        Args:
            memory: The conversation memory, if any

        Returns:
            Alternating human and AI messages, oldest first.
        """
        if not memory or not memory.turns:
            return []
        messages = []
        for turn in memory.turns:
            messages.append(HumanMessage(content=turn.user))
            messages.append(AIMessage(content=turn.assistant))
        return messages
