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
                    const data = JSON.parse(event.data);
                    if (data.text) {
                        store.isThinking = false;
                        store.appendChunk(data.text);
                    }
                } catch (e) {
                    console.error("SSE parse error", e);
                }
            };

            eventSource.onerror = (e) => {
                eventSource.close();
                // Simple reconnect logic
                setTimeout(initSSE, 3000);
            };
        };

        // Start listening
        initSSE();

        return { store };
    }
};

createApp(App).mount('#app');
