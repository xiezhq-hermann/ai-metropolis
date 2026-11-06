from typing import Optional, Callable
from aimetropolis.backends import BaseBackend

import sglang as sgl
from sglang import set_default_backend, RuntimeEndpoint


class SGLangBackend(BaseBackend):

    @staticmethod
    def api_call(prompt: str, max_tokens: int, stop: Optional[str], ignore_eos: bool, step: int,
                 regex_constrain: Optional[str]) -> str:
        set_default_backend(RuntimeEndpoint("http://localhost:30000"))

        @sgl.function
        def func_wrapper(s, prompt):
            # todo, support for priority scheduling for sgl
            s += prompt
            s += sgl.gen("response",
                         max_tokens=max_tokens,
                         stop=stop,
                         ignore_eos=ignore_eos,
                         regex=regex_constrain if regex_constrain else None)

        response = func_wrapper.run(prompt)
        return response["response"]

    @classmethod
    def generate(cls,
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
        return super().generate(prompt, max_tokens, step, repeat, stop, ignore_eos, regex_constrain, func_validate,
                                trace_id, trace_label)
