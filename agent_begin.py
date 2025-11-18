import os
import json
from openai import OpenAI

with open("api.key") as f:
    api_key = f.read()

client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

class chat:
    system_prompt = """
Ты нейросеть-агент, ты запущен из файла "agent_begin.py".

Ты можешь использовать инструменты, используй не более 1 за раз

Пример:
Запрос пользователя:
Посчитай log 10! по основанию 2 с точностью 3 знака после запятой

Ответ (вызов функции):
function=Function(arguments='{"code": "print(\\"Hello world\\")"}', name='python'), type='function', index=0)

Результат кода (вместо запроса пользователя):
21.791

Ответ:
log 10! по основанию 2 равен 21.791
"""

    tools = [
        {
            "type": "function",
            "function": {
                "name": "python",
                "description": """Выполнить python код, после выполнения тебе придёт результат выполнения кода (его нужно сохранить в глобальную строку result), код выполняется в том скрипте, который управляет чатом (например, если выполнить print("Hello world"), в консоль пользователя будет выведено Hello world), локальные и глобальные переменные между запусками сохраняются (кроме result)""",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "code": {
                            "type": "string",
                            "description": "Код, который нужно выполнить",
                        }
                    },
                    "required": ["location"]
                },
            }
        },
    ]

    messages=[
            {"role": "system", "content": system_prompt},
        ]

    global_env = {}
    local_env = {}

    def send(self, message):
        self.messages.append(message)

        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=self.messages,
            tools=self.tools,
        )
        self.messages.append(response.choices[0].message)

        print("\n\ncontent:", response.choices[0].message.content, sep='\n')
        if response.choices[0].message.tool_calls:
            tool = response.choices[0].message.tool_calls[0]
            code = json.loads(tool.function.arguments)["code"]
            print("\n\ncode:", code, sep='\n')

            self.local_env["result"] = ""
            exec(code, self.global_env, self.local_env)
            self.send({"role": "tool", "tool_call_id": tool.id, "content": str(self.local_env["result"])})


def main():
    chat1 = chat()

    while(1):
        chat1.send({"role": "user", "content": input()})


if __name__ == "__main__":
    main()
