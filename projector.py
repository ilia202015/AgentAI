from agent import Chat

class Projector:
    def __init__(self, chat: Chat, plan_data: dict):
        self.chat = chat
        self.plan = plan_data
        self.blocks = self.plan.get("blocks", [])
        self.b_idx = 0
        self.s_idx = -1

    def advance(self):
        if self.b_idx >= len(self.blocks):
            return False
        
        block = self.blocks[self.b_idx]
        steps = block.get("steps", [])
        
        if self.s_idx < len(steps):
            self.s_idx += 1
        else:
            self.b_idx += 1
            self.s_idx = 0
        
        return True

    def get_context_str(self):
        if self.b_idx >= len(self.blocks):
            return "ФАЗА: Финализация всего проекта.\nВся работа по плану завершена. Проверь общую интеграцию и работоспособность проекта.\nПроведи тест по циклу:\nЗапуск проекта\nЧтение логов\nЕсли вылет или ошибка: фикс и в начало цикла, иначе завершить цикл\n"
        
        block = self.blocks[self.b_idx]
        steps = block.get("steps", [])
        
        if self.s_idx < len(steps):
            step_desc = steps[self.s_idx]
            return f"ФАЗА: Разработка.\nТекущий блок: {block.get('name', 'Без имени')} ({self.b_idx + 1}/{len(self.blocks)})\nТекущий шаг: {step_desc} ({self.s_idx + 1}/{len(steps)})"
        else:
            return f"ФАЗА: Финализация блока.\nБлок: {block.get('name', 'Без имени')} завершен.\nЗадача: провести общее тестирование и интеграцию всех шагов этого блока."

    def get_prompt(self, action):
        if action == "next":
            has_next = self.advance()
            if not has_next:
                return "Проект полностью завершен. Дальнейших шагов нет."
            
            context = self.get_context_str()
            return f"{context}\n\nИНСТРУКЦИЯ: Начинай реализацию этого этапа. Выполни ТОЛЬКО этот этап. Напиши или измени нужный код."
        
        context = self.get_context_str()
        if action == "find_bug":
            return f"{context}\n\nИНСТРУКЦИЯ: Внимательно изучи реализацию текущего этапа. Найди потенциальные баги, утечки ресурсов или логические ошибки. Если есть баги, ты должен найти как можно больше. НЕ ПИШИ ПРОБЛЕМЫ, КОТОРЫЕ ИСПРАВЯТСЯ В СЛЕДУЮЩИХ ШАГАХ (Например, заглушки). НЕ ИСПРАВЛЯЙ ИХ, только напиши отчет."
        elif action == "analyze":
            return f"{context}\n\nИНСТРУКЦИЯ: Проанализируй качество кода текущего этапа. Оцени архитектуру, читаемость, следование SOLID. НЕ ПИШИ ПРОБЛЕМЫ, КОТОРЫЕ ИСПРАВЯТСЯ В СЛЕДУЮЩИХ ШАГАХ (Например, заглушки). НЕ ПИШИ КОД, только дай оценку."
        elif action == "fix":
            return f"{context}\n\nИНСТРУКЦИЯ: Исправь все найденные ранее баги на текущем этапе. Напиши и примени исправленный код."
        elif action == "refactor":
            return f"{context}\n\nИНСТРУКЦИЯ: Проведи рефакторинг кода текущего этапа для улучшения его качества и читаемости без изменения бизнес-логики."
        
        return f"Неизвестное действие: {action}"

    def run_to_block_end(self, auto_mode=False):
        if self.b_idx >= len(self.blocks):
            return 'Проект завершен.'
        
        block = self.blocks[self.b_idx]
        steps = block.get('steps', [])
        
        prompt_end = "\n\nСейчас ты работаешь в авто-режиме, выполни шаг и выведи \"OK\" в качестве ответа (без лишнего текста)\n"

        if self.s_idx == len(steps):
            prompt = self.get_prompt('next')
            if prompt:
                self.chat.print(prompt + prompt_end)
                self.chat.send(prompt + prompt_end)
        
        while self.s_idx < len(steps) - 1:
            prompt = self.get_prompt('next')
            if prompt:
                self.chat.print(prompt + prompt_end)
                self.chat.send(prompt + prompt_end)
                
        return self.get_prompt('next') + (prompt_end if auto_mode else "\n\nВыход из авто-режима, давай нормальные ответы\n")
