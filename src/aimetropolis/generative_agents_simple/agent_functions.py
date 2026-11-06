from aimetropolis.backends import OpenAIBackend
from aimetropolis.backends import SGLangBackend


def generate_event_poig_score(persona_name, step, persona_iss, event):
    # return prompt and max_tokens
    s = ""
    s += "Here is a brief description of " + persona_name + ".\n"
    s += persona_iss + "\n"
    s += "On the scale of 1 to 10, where 1 is purely mundane (e.g., brushing teeth, making bed) and 10 is extremely poignant (e.g., a break up, college acceptance), rate the likely poignancy of the following event for"
    s += persona_name + ".\n\n"
    s += "Event: " + event
    s += "Rate (return a number between 1 to 10):"
    regex_constraint = "^[1-9]|10$"
    return OpenAIBackend.generate(s, max_tokens=2, regex_constrain=regex_constraint, trace_id=f"{persona_name}:{step}")


def common_llm_call(persona_name, step, prompt, max_tokens, stop, ignore_eos=False, trace_label=None):
    return SGLangBackend.generate(prompt,
                                  max_tokens=max_tokens,
                                  step=step,
                                  stop=stop,
                                  ignore_eos=ignore_eos,
                                  trace_id=f"{persona_name}:{step}",
                                  trace_label=trace_label)
