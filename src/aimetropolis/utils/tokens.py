from functools import lru_cache

import tiktoken


@lru_cache(maxsize=1)
def _encoding():
    # the first call may download the encoding, so it must not run at import time
    return tiktoken.encoding_for_model("gpt-3.5-turbo")


def count_tokens(text: str) -> int:
    return len(_encoding().encode(text, disallowed_special=()))
