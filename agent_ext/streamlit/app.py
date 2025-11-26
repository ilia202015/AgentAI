
import streamlit as st
import sys, logging, os, time

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('agent_ext/agent_ext.log')
    ]
)
logger = logging.getLogger(__name__)


# Добавляем корневую директорию проекта в sys.path
# Это необходимо, чтобы можно было импортировать agent_ext.agent
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from agent_ext.agent import Chat

# Настройка страницы Streamlit
st.set_page_config(page_title="Agent Chat", layout="wide")
st.title("Чат с AI-Агентом")

# Инициализация агента в состоянии сессии Streamlit
# Это позволяет сохранить один и тот же экземпляр агента для пользователя
if 'agent' not in st.session_state:
    st.session_state.agent = Chat(output_mode="user")
    # Добавляем системное сообщение, чтобы оно не отображалось в чате, но было в истории
    st.session_state.messages = [{"role": "system", "content": st.session_state.agent.system_prompt}]

# Функция для отображения сообщений из истории
def display_chat_history():
    # Пропускаем первое системное сообщение
    for message in st.session_state.messages[1:]:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            # Отображаем вызовы инструментов, если они есть
            if "tool_calls" in message and message["tool_calls"]:
                with st.expander("Вызов инструментов", expanded=False):
                    for tool_call in message["tool_calls"]:
                        st.code(f"{tool_call['function']['name']}({tool_call['function']['arguments']})", language="python")

# Отображаем существующую историю чата
display_chat_history()

# Обработка ввода пользователя
if prompt := st.chat_input("Ваше сообщение..."):
    # Добавляем сообщение пользователя в историю и отображаем его
    user_message = {"role": "user", "content": prompt}
    st.session_state.messages.append(user_message)
    with st.chat_message("user"):
        st.markdown(prompt)

    # Получаем ответ от агента
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        full_response = ""
        
        # Переопределяем метод _handle_stream_response для вывода в Streamlit
        def streamlit_stream_handler(self, response_stream):
            global full_response, message_placeholder
            tool_calls = []
            
            for chunk in response_stream:
                content_delta = chunk.choices[0].delta.content
                tool_calls_delta = chunk.choices[0].delta.tool_calls
                
                if content_delta:
                    full_response += content_delta
                    message_placeholder.markdown(full_response + "▌")
                
                if tool_calls_delta:
                    for tool_call in tool_calls_delta:
                        if tool_call.index is None or tool_call.index >= len(tool_calls):
                             tool_calls.append({
                                 "id": tool_call.id,
                                 "type": "function",
                                 "function": {"name": tool_call.function.name, "arguments": tool_call.function.arguments or ""}
                             })
                        else:
                            tool_calls[tool_call.index]["function"]["arguments"] += tool_call.function.arguments or ""

            message_placeholder.markdown(full_response)
            
            assistant_message = {"role": "assistant", "content": full_response}
            if tool_calls:
                assistant_message["tool_calls"] = tool_calls
                st.session_state.messages.append(assistant_message)
                # Добавляем вызов инструментов в UI
                with st.expander("Вызов инструментов", expanded=True):
                    for tool_call in tool_calls:
                        st.code(f"{tool_call['function']['name']}({tool_call['function']['arguments']})", language="python")
            else:
                 st.session_state.messages.append(assistant_message)
            
            self.messages.append(assistant_message)
            logger.info("Получен потоковый ответ от модели.")
            
            if tool_calls:
                self._execute_tool_calls(tool_calls)
        
            return "Streamlit display completed."

        st.session_state.agent._handle_stream_response = streamlit_stream_handler.__get__(st.session_state.agent, Chat)
        
        # Вызываем send, который теперь будет использовать наш кастомный обработчик
        st.session_state.agent.send(user_message)
