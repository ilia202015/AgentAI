import { store } from '../store.js';
import * as api from '../api.js';
import { onMounted } from 'vue';

export default {
    template: `
        <div class="w-64 bg-gray-900 border-r border-gray-800 flex flex-col h-full flex-shrink-0">
            <div class="p-4 border-b border-gray-800 flex justify-between items-center">
                <h1 class="font-bold text-gray-100 flex items-center gap-2">
                    <i class="ph ph-robot text-blue-500"></i> Agent AI
                </h1>
                <button @click="createNew" class="p-1 hover:bg-gray-800 rounded text-gray-400 hover:text-white transition" title="New Chat">
                    <i class="ph ph-plus"></i>
                </button>
            </div>
            <div class="flex-1 overflow-y-auto p-2 space-y-1">
                <div v-for="chat in store.chats" :key="chat.id"
                    @click="selectChat(chat.id)"
                    class="p-2 rounded cursor-pointer group relative transition-colors duration-200"
                    :class="chat.id === store.currentChatId ? 'bg-gray-800 text-white' : 'text-gray-400 hover:bg-gray-850 hover:text-gray-200'"
                >
                    <div class="font-medium truncate text-sm pr-6">{{ chat.name || 'New Chat' }}</div>
                    <div class="text-xs opacity-50 truncate">{{ chat.preview }}</div>
                    
                    <button @click.stop="deleteChat(chat.id)" 
                        class="absolute right-1 top-1.5 opacity-0 group-hover:opacity-100 p-1 hover:bg-red-900/50 hover:text-red-400 rounded transition-opacity">
                        <i class="ph ph-trash"></i>
                    </button>
                </div>
            </div>
            
            <div class="p-4 border-t border-gray-800 text-xs text-gray-600 flex justify-between">
                <span>v1.0.0</span>
                <span class="w-2 h-2 rounded-full" :class="connected ? 'bg-emerald-500' : 'bg-red-500'"></span>
            </div>
        </div>
    `,
    setup() {
        const createNew = async () => {
            const chat = await api.createChat();
            await refreshList();
            await selectChat(chat.id);
        };
        
        const deleteChat = async (id) => {
            if (confirm('Delete chat?')) {
                await api.deleteChat(id);
                if (store.currentChatId === id) {
                    store.currentChatId = null;
                    store.setMessages([]);
                }
                await refreshList();
            }
        };
        
        const selectChat = async (id) => {
            store.currentChatId = id;
            try {
                const data = await api.loadChat(id);
                store.setMessages(data.chat.messages);
            } catch (e) {
                console.error("Failed to load chat", e);
            }
        };

        const refreshList = async () => {
            store.chats = await api.fetchChats();
        };

        const checkCurrent = async () => {
             const current = await api.fetchCurrentChat();
             if (current && current.id) {
                 store.currentChatId = current.id;
                 store.setMessages(current.messages);
             }
        }
        
        onMounted(async () => {
            await refreshList();
            // Try to load current active chat from server
            await checkCurrent();
        });
        
        return { store, createNew, deleteChat, selectChat, connected: true };
    }
}
