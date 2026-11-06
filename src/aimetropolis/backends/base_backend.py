import re
import json
import redis
import random
from time import time
from collections import Counter
from typing import Optional, Callable, Type

TRACE_DELIMITER = "__TRACE__"


def most_frequent_element(elements):
    # Count the occurrences of each element in the list
    counts = Counter(elements)
    # Find the maximum count
    max_count = max(counts.values())
    # Gather all elements that have the maximum count
    most_frequent = [key for key, count in counts.items() if count == max_count]
    # Randomly pick one if there are ties
    return random.choice(most_frequent)


class BaseBackend:
    INSTRUMENTATION = True

    @staticmethod
    def api_call(prompt: str, max_tokens: int, stop: Optional[str], ignore_eos: bool, step: int,
                 regex_constrain: Optional[str]) -> str:
        raise NotImplementedError

    @classmethod
    def generate(cls: Type['BaseBackend'],
                 prompt: str,
                 max_tokens: int,
                 step: int = 0,
                 repeat: int = 3,
                 stop: Optional[str] = None,
                 ignore_eos: bool = False,
                 regex_constrain: Optional[str] = None,
                 func_validate: Optional[Callable] = None,
                 trace_id: Optional[str] = "trace",
                 trace_label: Optional[str] = None) -> str:

        def __func_validate(response: str):
            if func_validate is not None:
                return func_validate(response)
            elif regex_constrain is not None:
                return bool(re.fullmatch(regex_constrain, response))
            else:
                return True

        responses = []
        tic = time()
        for _ in range(repeat):
            response = cls.api_call(prompt, max_tokens, stop, ignore_eos, step, regex_constrain)
            if __func_validate(response):
                responses.append(response)
                break
        duration = time() - tic
        if not responses:
            print(f"Failed to generate a valid response after {repeat} attempts, return N/A instead")
            responses.append("N/A")
        if cls.INSTRUMENTATION:
            trace_db = redis.Redis(host='localhost', port=6379, db=2)
            trace_sample = {
                "prompt": prompt,
                "config": {
                    "max_tokens": max_tokens,
                    "stop": stop,
                    "regex_constrain": regex_constrain,
                },
                "label": trace_label,
                "response": responses[0],
                "start_time": tic,
                "duration": duration
            }
            if not trace_db.exists(trace_id):
                trace_db.set(trace_id, json.dumps(trace_sample))
            else:
                trace_db.append(trace_id, TRACE_DELIMITER + json.dumps(trace_sample))
            # print(f"Generated response in {duration:.2f} seconds")
        return responses[0]
        # or we can return the most frequent response out of repeat attempts
        # return most_frequent_element(responses)
