import { createApp } from 'vue';
import { store } from './store.js';
import Sidebar from './components/Sidebar.js';
import ChatArea from './components/ChatArea.js';

const App = {
    components: { Sidebar, ChatArea },
    template: `
        <div class="flex w-full h-full font-sans antialiased bg-gray-950 text-gray-200">
            <Sidebar />
            <ChatArea />
        </div>
    `,
    setup() {
        const initSSE = () => {
            const eventSource = new EventSource('/stream');
            
            eventSource.onmessage = (event) => {
                try {
                    const payload = JSON.parse(event.data);
                    
                    // payload теперь имеет вид: { type: 'text'|'thought'|'tool', data: '...' }
                    if (payload && payload.type) {
                        store.isThinking = false; // Пришло сообщение - значит, агент уже отвечает
                        
                        // Если это просто пинг 'keep-alive' (мы его не парсим как JSON в server.py, но вдруг)
                        // В server.py мы шлем ": keep-alive", это игнорируется браузером как комментарий.
                        // Если мы шлем data: ..., это попадает сюда.
                        
                        store.appendChunk(payload);
                    }
                } catch (e) {
                    // console.error("SSE parse error", e);
                }
            };

            eventSource.onerror = (e) => {
                eventSource.close();
                store.isThinking = false; // Сбрасываем флаг при обрыве
                setTimeout(initSSE, 3000);
            };
        };

        initSSE();

        return { store };
    }
};

createApp(App).mount('#app');
