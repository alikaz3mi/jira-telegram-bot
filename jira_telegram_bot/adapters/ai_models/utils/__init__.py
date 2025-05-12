from __future__ import annotations

import re

from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda


def correction_chain(message: AIMessage, **kwargs) -> str:
    # match unquoted values until the next key or the end of the json object
    pattern = (
        r"(\"[a-zA-Z0-9_]*\"):\s*(.*?)(?=(,\n\s*(\"[a-zA-Z0-9_]*\"):|\n}$|\n}.{3,5}$))"
    )

    def correct_content(match):
        key, value = match.groups()[0], match.groups()[1]

        if kwargs.get("double_quates2single_quate", False):
            value = re.sub(r'"', "'", value)

        # single backslashes not indicating python special character should be removed
        PATTERN_WORD = (
            r'(?<!\\)(?:\\\\)*\\(?!["\\\/]|[bfnrt](?![a-zA-Z])|u[0-9a-fA-F]{4})'
        )
        corrected_value = re.sub(PATTERN_WORD, r"\\\\", value)

        if kwargs.get("ensure_value_quates", False):
            corrected_value = (
                corrected_value[1:-1]
                if (corrected_value.startswith("'") and corrected_value.endswith("'"))
                else corrected_value
            )
            # quote the corrected value
            return f'{key}: "{corrected_value}"'
        else:
            return f"{key}: {corrected_value}"

    return re.sub(pattern, correct_content, message.content, flags=re.DOTALL)


llm_result_correction_chain = RunnableLambda(correction_chain)
