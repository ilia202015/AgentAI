import { createApp, defineComponent } from 'vue';
import { store } from './store.js';
import Sidebar from './components/Sidebar.js';
import ChatArea from './components/ChatArea.js';

// --- Toast Component (Global) ---
const ToastContainer = defineComponent({
    setup() { return { store } },
    template: `
        <div class="fixed top-4 right-4 z-[100] flex flex-col gap-2 pointer-events-none">
            <div v-for="toast in store.toasts" :key="toast.id" 
                 class="px-4 py-3 rounded-xl shadow-2xl backdrop-blur-xl border border-white/10 text-sm font-medium animate-fade-in-up pointer-events-auto flex items-center gap-3 transition-all duration-300"
                 :class="{
                    'bg-emerald-500/20 text-emerald-200 border-emerald-500/20': toast.type === 'success',
                    'bg-red-500/20 text-red-200 border-red-500/20': toast.type === 'error',
                    'bg-blue-500/20 text-blue-200 border-blue-500/20': toast.type === 'info'
                 }">
                 <i v-if="toast.type === 'success'" class="ph-bold ph-check-circle text-lg"></i>
                 <i v-if="toast.type === 'error'" class="ph-bold ph-warning-circle text-lg"></i>
                 <i v-if="toast.type === 'info'" class="ph-bold ph-info text-lg"></i>
                 <span>{{ toast.message }}</span>
            </div>
        </div>
    `
});

const App = {
    components: { Sidebar, ChatArea, ToastContainer },
    template: `
        <div class="flex w-full h-full font-sans antialiased bg-gray-950 text-gray-200">
            <ToastContainer />
            <Sidebar />
            <ChatArea />
        </div>
    `,
    setup() {
        const initSSE = () => {
            console.log("Connecting to SSE...");
            const eventSource = new EventSource('/stream');
            
            eventSource.onopen = () => { console.log("SSE Connected"); };

            eventSource.onmessage = (event) => {
                try {
                    const payload = JSON.parse(event.data);
                    
                    // --- Parallel Chat Logic ---
                    // Payload now has { type, chatId, data }
                    
                    if (payload && payload.chatId) {
                        // Only process events for the currently open chat
                        if (store.currentChatId === payload.chatId) {
                            if (payload.type === 'finish') {
                                store.isThinking = false;
                            } else {
                                store.appendChunk(payload);
                            }
                        }
                    }
                } catch (e) { console.error("SSE Parse Error:", e); }
            };

            eventSource.onerror = (e) => {
                console.error("SSE Error/Disconnect:", e);
                eventSource.close();
                store.isThinking = false;
                setTimeout(initSSE, 3000);
            };
        };

        initSSE();
        
        setTimeout(() => store.addToast('Агент готов к работе (Parallel Mode)', 'success'), 1000);

        return { store };
    }
};

createApp(App).mount('#app');
