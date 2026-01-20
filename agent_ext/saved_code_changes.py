
# Saved on: 2026-01-20 15:54:32
def send_patched(self, messages):
    from google.genai import types
    import base64
    
    if not isinstance(messages, list):
        messages = [messages]

    for msg in messages:
        if isinstance(msg, dict):
                parts = []
                # Текст
                if "content" in msg and msg["content"]:
                    parts.append(types.Part(text=msg["content"]))
                
                # Картинки
                if "images" in msg and isinstance(msg["images"], list):
                    for img_data in msg["images"]:
                        try:
                            # Ожидаем format: "data:image/png;base64,..."
                            if "base64," in img_data:
                                header, b64_str = img_data.split("base64,", 1)
                                mime_type = header.split(":")[1].split(";")[0]
                            else:
                                b64_str = img_data
                                mime_type = "image/jpeg"
                            
                            parts.append(types.Part.from_data(data=base64.b64decode(b64_str), mime_type=mime_type))
                        except Exception as e:
                            print(f"Ошибка декодирования изображения: {e}")
                
                # Если части созданы - добавляем
                if parts:
                    self.messages.append(types.Content(role=msg["role"], parts=parts))
        
        elif isinstance(msg, str):
                self.messages.append(types.Content(role="user", parts=[types.Part(text=msg)]))
        else:
                self.messages.append(msg)
    
    return self._process_request()

# Патчим класс Chat, чтобы все новые экземпляры тоже получили этот метод
Chat.send = send_patched
print("✅ Метод Chat.send пропатчен для поддержки изображений.")

################################################################################
