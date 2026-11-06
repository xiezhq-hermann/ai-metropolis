import os
from typing import Optional

from openai import OpenAI

from aimetropolis.backends import BaseBackend


class OpenAIBackend(BaseBackend):

    @staticmethod
    def api_call(prompt: str, max_tokens: int, stop: Optional[str], ignore_eos: bool, step: int,
                 regex_constrain: Optional[str]) -> str:
        # todo: more config options like temperature, top_p, etc.

        client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

        try:
            response = client.chat.completions.create(model="gpt-3.5-turbo",
                                                      messages=[{
                                                          "role": "user",
                                                          "content": prompt
                                                      }],
                                                      max_tokens=max_tokens,
                                                      stop=stop)
            return response.choices[0].message.content
        except Exception as e:
            # todo, retry for rate limit
            print(f"Error: {e}")
            return "OpenAI API call failed"
