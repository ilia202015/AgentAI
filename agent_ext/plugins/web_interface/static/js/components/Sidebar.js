
import { store } from '../store.js';
import * as api from '../api.js';
import { onMounted, ref, computed, nextTick } from 'vue';

export default {
    template: `
        <div>
            <!-- Mobile Overlay -->
            <div v-if="store.isSidebarOpenMobile" @click="store.closeSidebarMobile()" 
                 class="fixed inset-0 bg-black/50 backdrop-blur-sm z-30 md:hidden transition-opacity"></div>

            <!-- Sidebar Container -->
            <div class="fixed inset-y-0 left-0 w-[280px] bg-gray-950/95 backdrop-blur-xl border-r border-white/5 flex flex-col h-full flex-shrink-0 z-40 transition-transform duration-300 transform"
                 :class="[
                    store.isSidebarOpenMobile ? 'translate-x-0' : '-translate-x-full',
                    'md:relative md:translate-x-0', 
                    store.isSidebarVisibleDesktop ? 'md:w-[280px]' : 'md:w-0 md:border-none md:overflow-hidden'
                 ]">
                
                <div class="flex flex-col h-full w-[280px]"> <!-- Inner container fixed width to prevent content squishing -->
                    
                    <!-- Header -->
                    <div class="p-5 flex justify-between items-center">
                        <div class="flex items-center gap-3">
                            <div class="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-600 to-indigo-600 flex items-center justify-center shadow-lg shadow-blue-500/20">
                                <i class="ph-bold ph-robot text-white text-lg"></i>
                            </div>
                            <span class="font-bold text-gray-100 tracking-tight">Agent AI</span>
                        </div>
                    </div>
                    
                    <!-- New Chat Button -->
                    <div class="px-4 mb-3">
                         <button @click="createNew" 
                            class="w-full py-2.5 px-4 flex items-center justify-center gap-2 rounded-xl bg-white/5 hover:bg-white/10 border border-white/5 hover:border-white/10 text-gray-200 hover:text-white transition-all duration-200 shadow-sm group">
                            <i class="ph-bold ph-plus text-blue-400 group-hover:text-blue-300"></i>
                            <span class="text-sm font-medium">Новый чат</span>
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
                            <div v-if="editingId === chat.id" class="mb-1">
                                <input ref="editInput" v-model="editName" @click.stop @keydown.enter="saveRename(chat)" @blur="saveRename(chat)" @keydown.esc="cancelRename" class="w-full bg-gray-950 text-white text-sm px-1 py-0.5 rounded border border-blue-500/50 focus:outline-none">
                            </div>
                            <div v-else class="font-medium truncate text-sm mb-0.5 pr-6" :class="chat.id === store.currentChatId ? 'text-white' : ''">
                                {{ chat.name || 'Новый чат' }}
                            </div>
                            <div class="text-[11px] truncate opacity-50 leading-relaxed font-light">{{ chat.preview }}</div>
                            
                            <div class="absolute right-2 top-1/2 -translate-y-1/2 opacity-0 group-hover:opacity-100 transition-opacity flex gap-1 bg-gray-900/80 backdrop-blur rounded-lg p-1 shadow-xl border border-white/10" :class="editingId === chat.id ? 'hidden' : ''">
                                <button @click.stop="startRename(chat)" class="p-1.5 hover:text-blue-400 hover:bg-white/10 rounded-md transition-colors" title="Переименовать"><i class="ph ph-pencil-simple"></i></button>
                                <button @click.stop="deleteChat(chat.id)" class="p-1.5 hover:text-red-400 hover:bg-white/10 rounded-md transition-colors" title="Удалить"><i class="ph ph-trash"></i></button>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Footer -->
                    <div class="p-4 border-t border-white/5 bg-black/20 backdrop-blur-sm space-y-3">
                        <button @click="startTemp" class="w-full flex items-center gap-3 p-2 rounded-lg transition-all duration-200" :class="store.currentChatId === 'temp' ? 'bg-purple-500/20 text-purple-200 border border-purple-500/30' : 'hover:bg-white/5 text-gray-400 border border-transparent'">
                            <div class="w-6 h-6 rounded flex items-center justify-center bg-purple-500/20"><i class="ph-bold ph-ghost text-purple-400"></i></div>
                            <div class="flex flex-col items-start"><span class="text-xs font-medium">Временный чат</span><span class="text-[9px] opacity-60">Без сохранения истории</span></div>
                        </button>
                        <div class="flex items-center gap-3 pt-1">
                            <div class="w-2 h-2 rounded-full animate-pulse" :class="connected ? 'bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)]' : 'bg-red-500'"></div>
                            <div class="flex flex-col"><span class="text-xs font-medium text-gray-300">Агент онлайн</span><span class="text-[10px] text-gray-600">v1.6.2 • {{ store.chats.length }} чатов</span></div>
                        </div>
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
            return store.chats.filter(c => (c.name || '').toLowerCase().includes(q) || (c.preview || '').toLowerCase().includes(q));
        });

        const createNew = async () => {
            const chat = await api.createChat();
            if (chat.error) {
                store.addToast(chat.error, 'error');
                return;
            }
            await refreshList();
            await selectChat(chat.id);
            if (window.innerWidth < 768) store.closeSidebarMobile();
        };

        const startTemp = async () => {
            const res = await api.startTempChat();
            if (res.error) {
                store.addToast(res.error, 'error');
                return;
            }
            store.currentChatId = 'temp';
            store.setMessages([]);
            if (window.innerWidth < 768) store.closeSidebarMobile();
        };
        
        const deleteChat = async (id) => {
            if (confirm('Вы уверены?')) {
                const res = await api.deleteChat(id);
                if (res.error) {
                    store.addToast(res.error, 'error');
                    return;
                }
                if (store.currentChatId === id) { store.currentChatId = null; store.setMessages([]); }
                await refreshList();
            }
        };
        
        const selectChat = async (id) => {
            if (editingId.value) return; 
            
            // Если уже выбран этот чат, ничего не делаем
            if (store.currentChatId === id) return;

            try {
                const data = await api.loadChat(id);
                if (data.error) {
                    store.addToast(data.error, 'error');
                    return; 
                }
                store.currentChatId = id;
                store.setMessages(data.chat.messages);
            } catch (e) { 
                console.error(e); 
                store.addToast("Ошибка соединения", 'error'); 
            }
            if (window.innerWidth < 768) store.closeSidebarMobile();
        };

        const startRename = async (chat) => {
            editingId.value = chat.id; editName.value = chat.name;
            await nextTick(); const el = document.querySelector('input[class*="bg-gray-950"]'); if (el) el.focus();
        };

        const saveRename = async (chat) => {
            if (!editingId.value) return;
            const newName = editName.value.trim();
            if (newName && newName !== chat.name) {
                const res = await api.renameChat(chat.id, newName);
                if (res.error) {
                    store.addToast(res.error, 'error');
                } else {
                    await refreshList();
                }
            }
            editingId.value = null;
        };
        const cancelRename = () => { editingId.value = null; }
        const refreshList = async () => { 
            const res = await api.fetchChats(); 
            if (Array.isArray(res)) store.chats = res;
        };
        
        const checkCurrent = async () => {
             const current = await api.fetchCurrentChat();
             if (current && current.id) { store.currentChatId = current.id; store.setMessages(current.messages); }
        }
        
        onMounted(async () => { await refreshList(); await checkCurrent(); });
        
        return { store, createNew, deleteChat, selectChat, startTemp, connected: true, searchQuery, filteredChats, editingId, editName, startRename, saveRename, cancelRename, editInput };
    }
}
