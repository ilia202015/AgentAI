import { store } from '../store.js';
import * as api from '../api.js';
import { onMounted, ref, computed, nextTick } from 'vue';

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
                    title="Новый чат">
                    <i class="ph-bold ph-plus"></i>
                </button>
            </div>

            <!-- Search -->
            <div class="px-4 mb-2">
                <div class="relative group">
                    <i class="ph ph-magnifying-glass absolute left-3 top-2.5 text-gray-500 group-focus-within:text-blue-400 transition-colors"></i>
                    <input type="text" placeholder="Поиск чатов..." v-model="searchQuery"
                        class="w-full bg-gray-900/50 border border-white/5 rounded-lg py-2 pl-9 pr-3 text-xs text-gray-300 placeholder-gray-600 focus:outline-none focus:border-blue-500/50 focus:bg-gray-900 transition-all">
                </div>
            </div>

            <!-- List -->
            <div class="flex-1 overflow-y-auto px-3 py-2 space-y-1 custom-scrollbar">
                <div v-if="filteredChats.length === 0" class="text-center py-10 opacity-30">
                    <i class="ph ph-chat-teardrop-text text-3xl mb-2"></i>
                    <p class="text-xs">Чаты не найдены</p>
                </div>
                
                <div v-for="chat in filteredChats" :key="chat.id"
                    @click="selectChat(chat.id)"
                    class="group relative p-3 rounded-xl cursor-pointer transition-all duration-200 border border-transparent"
                    :class="chat.id === store.currentChatId 
                        ? 'bg-white/10 border-white/5 shadow-sm' 
                        : 'hover:bg-white/5 text-gray-400 hover:text-gray-200'"
                >
                    <!-- Title / Edit Mode -->
                    <div v-if="editingId === chat.id" class="mb-1">
                        <input 
                            ref="editInput"
                            v-model="editName"
                            @click.stop
                            @keydown.enter="saveRename(chat)"
                            @blur="saveRename(chat)"
                            @keydown.esc="cancelRename"
                            class="w-full bg-gray-950 text-white text-sm px-1 py-0.5 rounded border border-blue-500/50 focus:outline-none"
                        >
                    </div>
                    <div v-else class="font-medium truncate text-sm mb-0.5 pr-6" 
                         :class="chat.id === store.currentChatId ? 'text-white' : ''">
                        {{ chat.name || 'Новый чат' }}
                    </div>
                    
                    <div class="text-[11px] truncate opacity-50 leading-relaxed font-light">
                        {{ chat.preview }}
                    </div>
                    
                    <!-- Actions (Hover only) -->
                    <div class="absolute right-2 top-1/2 -translate-y-1/2 opacity-0 group-hover:opacity-100 transition-opacity flex gap-1 bg-gray-900/80 backdrop-blur rounded-lg p-1 shadow-xl border border-white/10"
                         :class="editingId === chat.id ? 'hidden' : ''">
                        
                        <button @click.stop="startRename(chat)" 
                            class="p-1.5 hover:text-blue-400 hover:bg-white/10 rounded-md transition-colors" title="Переименовать">
                            <i class="ph ph-pencil-simple"></i>
                        </button>
                        
                        <button @click.stop="deleteChat(chat.id)" 
                            class="p-1.5 hover:text-red-400 hover:bg-white/10 rounded-md transition-colors" title="Удалить">
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
                        <span class="text-xs font-medium text-gray-300">Агент онлайн</span>
                        <span class="text-[10px] text-gray-600">v1.3.1 • {{ store.chats.length }} чатов</span>
                    </div>
                </div>
            </div>
        </div>
    `,
    setup() {
        const searchQuery = ref('');
        const editingId = ref(null);
        const editName = ref('');
        const editInput = ref(null);

        const filteredChats = computed(() => {
            if (!searchQuery.value) return store.chats;
            const q = searchQuery.value.toLowerCase();
            return store.chats.filter(c => 
                (c.name || '').toLowerCase().includes(q) || 
                (c.preview || '').toLowerCase().includes(q)
            );
        });

        const createNew = async () => {
            const chat = await api.createChat();
            await refreshList();
            await selectChat(chat.id);
        };
        
        const deleteChat = async (id) => {
            if (confirm('Вы уверены, что хотите удалить этот чат?')) {
                await api.deleteChat(id);
                if (store.currentChatId === id) {
                    store.currentChatId = null;
                    store.setMessages([]);
                }
                await refreshList();
            }
        };
        
        const selectChat = async (id) => {
            if (editingId.value) return; 
            store.currentChatId = id;
            try {
                const data = await api.loadChat(id);
                store.setMessages(data.chat.messages);
            } catch (e) {
                console.error("Failed to load chat", e);
            }
        };

        const startRename = async (chat) => {
            editingId.value = chat.id;
            editName.value = chat.name;
            await nextTick();
            const el = document.querySelector('input[class*="bg-gray-950"]'); 
            if (el) el.focus();
        };

        const saveRename = async (chat) => {
            if (!editingId.value) return;
            const newName = editName.value.trim();
            if (newName && newName !== chat.name) {
                await api.renameChat(chat.id, newName);
                await refreshList();
            }
            editingId.value = null;
        };
        
        const cancelRename = () => {
            editingId.value = null;
        }

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
        
        return { 
            store, createNew, deleteChat, selectChat, 
            connected: true, searchQuery, filteredChats,
            editingId, editName, startRename, saveRename, cancelRename, editInput
        };
    }
}
