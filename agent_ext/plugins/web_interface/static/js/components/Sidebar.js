import { store } from '../store.js';
import * as api from '../api.js';
import { onMounted } from 'vue';

export default {
    template: `
        <div class="w-[280px] bg-gray-950/80 backdrop-blur-xl border-r border-white/5 flex flex-col h-full flex-shrink-0 z-20">
            <!-- Header -->
            <div class="p-5 flex justify-between items-center">
                <div class="flex items-center gap-3">
                    <div class="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-600 to-indigo-600 flex items-center justify-center shadow-lg shadow-blue-500/20">
                        <i class="ph-bold ph-robot text-white text-lg"></i>
                    </div>
                    <span class="font-bold text-gray-100 tracking-tight">Agent AI</span>
                </div>
                <button @click="createNew" 
                    class="w-8 h-8 flex items-center justify-center rounded-lg border border-white/10 text-gray-400 hover:text-white hover:bg-white/5 hover:border-white/20 transition-all duration-200" 
                    title="New Chat">
                    <i class="ph-bold ph-plus"></i>
                </button>
            </div>

            <!-- Search (Visual only for now) -->
            <div class="px-4 mb-2">
                <div class="relative group">
                    <i class="ph ph-magnifying-glass absolute left-3 top-2.5 text-gray-500 group-focus-within:text-blue-400 transition-colors"></i>
                    <input type="text" placeholder="Search chats..." 
                        class="w-full bg-gray-900/50 border border-white/5 rounded-lg py-2 pl-9 pr-3 text-xs text-gray-300 placeholder-gray-600 focus:outline-none focus:border-blue-500/50 focus:bg-gray-900 transition-all">
                </div>
            </div>

            <!-- List -->
            <div class="flex-1 overflow-y-auto px-3 py-2 space-y-1 custom-scrollbar">
                <div v-if="store.chats.length === 0" class="text-center py-10 opacity-30">
                    <i class="ph ph-chat-teardrop-text text-3xl mb-2"></i>
                    <p class="text-xs">No chats yet</p>
                </div>
                
                <div v-for="chat in store.chats" :key="chat.id"
                    @click="selectChat(chat.id)"
                    class="group relative p-3 rounded-xl cursor-pointer transition-all duration-200 border border-transparent"
                    :class="chat.id === store.currentChatId 
                        ? 'bg-white/10 border-white/5 shadow-sm' 
                        : 'hover:bg-white/5 text-gray-400 hover:text-gray-200'"
                >
                    <div class="font-medium truncate text-sm mb-0.5" 
                         :class="chat.id === store.currentChatId ? 'text-white' : ''">
                        {{ chat.name || 'New Chat' }}
                    </div>
                    <div class="text-[11px] truncate opacity-50 leading-relaxed font-light">
                        {{ chat.preview }}
                    </div>
                    
                    <!-- Actions (Hover only) -->
                    <div class="absolute right-2 top-1/2 -translate-y-1/2 opacity-0 group-hover:opacity-100 transition-opacity flex gap-1 bg-gray-900/80 backdrop-blur rounded-lg p-1 shadow-xl border border-white/10">
                        <button @click.stop="deleteChat(chat.id)" 
                            class="p-1.5 hover:text-red-400 hover:bg-white/10 rounded-md transition-colors">
                            <i class="ph ph-trash"></i>
                        </button>
                    </div>
                </div>
            </div>
            
            <!-- Footer -->
            <div class="p-4 border-t border-white/5 bg-black/20 backdrop-blur-sm">
                <div class="flex items-center gap-3">
                    <div class="w-2 h-2 rounded-full animate-pulse" 
                         :class="connected ? 'bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)]' : 'bg-red-500'"></div>
                    <div class="flex flex-col">
                        <span class="text-xs font-medium text-gray-300">Agent Online</span>
                        <span class="text-[10px] text-gray-600">v1.2.0 • {{ store.chats.length }} chats</span>
                    </div>
                </div>
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
            if (confirm('Are you sure you want to delete this chat?')) {
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
            await checkCurrent();
        });
        
        return { store, createNew, deleteChat, selectChat, connected: true };
    }
}
