import { store } from '../store.js';
import * as api from '../api.js';
import { onMounted, onUnmounted, ref, computed, nextTick, watch } from 'vue';

export default {
    template: `
        <div>
            <!-- Mobile Overlay (Backdrop) -->
            <Teleport to="body">
                <div v-if="store.isSidebarOpenMobile" 
                     class="fixed inset-0 bg-black/40 backdrop-blur-md z-[60] md:hidden transition-all duration-300"
                     @click="store.closeSidebarMobile()"></div>
            </Teleport>

            <!-- Sidebar Container -->
            <div class="fixed md:relative inset-y-0 left-0 bg-gray-900/40 backdrop-blur-xl border-r border-white/5 flex flex-col h-full flex-shrink-0 z-[70] transition-all duration-300 ease-in-out overflow-hidden"
                 :class="[
                    store.isSidebarOpenMobile ? 'translate-x-0 w-[280px]' : '-translate-x-full md:translate-x-0',
                    store.isSidebarVisibleDesktop ? 'md:w-[280px] opacity-100' : 'md:w-0 opacity-0 md:border-none'
                 ]">
                
                <div class="flex flex-col h-full w-[280px]"> 
                    
                    <!-- Header -->
                    <div class="p-5 flex justify-between items-center text-gray-100">
                        <div class="flex items-center gap-3">
                            <div class="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-600 to-indigo-600 flex items-center justify-center shadow-lg shadow-blue-500/20 text-white">
                                <i class="ph-bold ph-robot text-lg"></i>
                            </div>
                            <span class="font-bold tracking-tight">Agent AI</span>
                        </div>
                        <button @click="store.toggleBg()" class="p-1.5 rounded-lg hover:bg-white/10 transition-colors" 
                            :class="store.isBgEnabled ? 'text-purple-400 bg-purple-500/10' : 'text-gray-500'" 
                            title="Динамический фон">
                            <i class="ph-bold ph-sparkle"></i>
                        </button>
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
                                class="w-full bg-white/5 border border-white/10 rounded-lg py-2 pl-9 pr-3 text-xs text-gray-300 placeholder-gray-600 focus:outline-none focus:border-blue-500/50 focus:bg-gray-900/60 transition-all">
                        </div>
                    </div>

                    <!-- List -->
                    <div class="flex-1 overflow-y-auto px-3 py-2 space-y-1 custom-scrollbar">
                        <div v-if="filteredChats.length === 0" class="text-center py-10 opacity-30">
                            <i class="ph ph-chat-teardrop-text text-3xl mb-2"></i>
                            <p class="text-xs">Чаты не найдены</p>
                        </div>
                        
                        <div v-for="(chat, index) in filteredChats" :key="chat.id"
                            @click="selectChat(chat.id)"
                            class="group relative p-3 rounded-xl cursor-pointer transition-all duration-200 border border-transparent"
                            :class="chat.id === store.currentChatId 
                                ? 'bg-white/10 border-white/5 shadow-sm backdrop-blur-md' 
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
                                <button @click.stop="togglePresetMenu(chat.id)" 
                                        class="p-1.5 hover:text-indigo-400 hover:bg-white/10 rounded-md transition-colors" 
                                        :class="activePresetMenuId === chat.id ? 'text-indigo-400 bg-white/10' : ''"
                                        title="Сменить пресет">
                                    <i class="ph ph-layout"></i>
                                </button>
                                <button @click.stop="clearContext(chat.id)" class="p-1.5 hover:text-amber-400 hover:bg-white/10 rounded-md transition-colors" title="Очистить контекст (удалить PKL)"><i class="ph ph-eraser"></i></button>
                                <button @click.stop="startRename(chat)" class="p-1.5 hover:text-blue-400 hover:bg-white/10 rounded-md transition-colors" title="Переименовать"><i class="ph ph-pencil-simple"></i></button>
                                <button @click.stop="deleteChat(chat.id)" class="p-1.5 hover:text-red-400 hover:bg-white/10 rounded-md transition-colors" title="Удалить"><i class="ph ph-trash"></i></button>

                                <!-- Меню пресетов (выровнено по правому краю контейнера) -->
                                <div v-if="activePresetMenuId === chat.id" 
                                     class="absolute right-0 w-48 bg-gray-900/95 backdrop-blur-xl border border-white/10 rounded-xl shadow-2xl z-[100] p-1 animate-fade-in-up origin-top-right"
                                     :class="index < 3 ? 'top-full mt-2' : 'bottom-full mb-2'">
                                    <div class="text-[9px] font-bold text-gray-500 uppercase p-2 tracking-widest border-b border-white/5 mb-1">Выбор пресета</div>
                                    <div class="max-h-48 overflow-y-auto custom-scrollbar">
                                        <button v-for="(p, pid) in store.presets" :key="pid" @click.stop="selectPreset(chat.id, pid)"
                                                class="w-full text-left px-3 py-2 rounded-lg text-xs flex items-center justify-between group transition-all"
                                                :class="((chat.id === store.currentChatId && store.activePresetId === pid) || (chat.id !== store.currentChatId && chat.active_preset_id === pid)) ? 'bg-indigo-600/20 text-indigo-400' : 'text-gray-400 hover:bg-white/5 hover:text-gray-200'">
                                            <span class="truncate">{{ p.name }}</span>
                                            <i v-if="(chat.id === store.currentChatId && store.activePresetId === pid) || (chat.id !== store.currentChatId && chat.active_preset_id === pid)" class="ph-bold ph-check"></i>
                                        </button>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Footer -->
                    <div class="p-4 border-t border-white/5 bg-black/20 backdrop-blur-sm space-y-3 relative">
                        <div v-if="store.currentChatId" class="relative" ref="modelMenuRef">
                             <div class="flex items-center justify-between mb-1.5 px-1">
                                <label class="text-[10px] font-bold text-gray-500 uppercase tracking-wider">Модель</label>
                             </div>
                             
                             <button @click="isModelMenuOpen = !isModelMenuOpen" 
                                class="w-full bg-white/5 border border-white/10 rounded-xl py-2 px-3 flex items-center justify-between text-xs text-gray-200 hover:bg-gray-800/60 hover:border-white/20 transition-all duration-200 group">
                                <div class="flex items-center gap-2 truncate pr-2">
                                    <div class="w-5 h-5 rounded bg-blue-500/10 flex items-center justify-center flex-shrink-0">
                                        <i class="ph-fill ph-lightning text-blue-400 text-xs"></i>
                                    </div>
                                    <span class="truncate font-medium">{{ selectedModel || 'Загрузка...' }}</span>
                                </div>
                                <i class="ph-bold ph-caret-down text-gray-500 group-hover:text-gray-300 transition-transform duration-200" :class="isModelMenuOpen ? 'rotate-180' : ''"></i>
                            </button>
                            
                            <div v-if="isModelMenuOpen" 
                                class="absolute bottom-full left-0 right-0 mb-2 bg-gray-900/95 backdrop-blur-xl border border-white/10 rounded-xl shadow-2xl overflow-hidden z-[60] animate-fade-in-up origin-bottom">
                                <div class="p-1 max-h-48 overflow-y-auto custom-scrollbar">
                                    <button v-for="m in store.models" :key="m[0]" @click="selectModel(m[0])"
                                        class="w-full text-left px-3 py-2 rounded-lg text-xs flex items-center justify-between group transition-all duration-150"
                                        :class="selectedModel === m[0] ? 'bg-blue-600/10 text-blue-400' : 'text-gray-400 hover:bg-white/5 hover:text-gray-200'">
                                        <span class="font-medium truncate">{{ m[0] }}</span>
                                        <i v-if="selectedModel === m[0]" class="ph-bold ph-check text-blue-500"></i>
                                        <span v-else class="text-[9px] opacity-0 group-hover:opacity-50 bg-white/10 px-1.5 py-0.5 rounded transition-opacity">{{ m[1] }} RPM</span>
                                    </button>
                                </div>
                            </div>
                        </div>

                        <button @click="startTemp" class="w-full flex items-center gap-3 p-2 rounded-lg transition-all duration-200 group relative z-10" :class="store.currentChatId === 'temp' ? 'bg-purple-500/20 text-purple-200 border border-purple-500/30' : 'hover:bg-white/5 text-gray-400 border border-transparent'">
                            <div class="w-6 h-6 rounded flex items-center justify-center bg-purple-500/20 group-hover:scale-110 transition-transform"><i class="ph-bold ph-ghost text-purple-400"></i></div>
                            <div class="flex flex-col items-start"><span class="text-xs font-medium">Временный чат</span><span class="text-[9px] opacity-60">Без сохранения истории</span></div>
                        </button>
                        
                        <div class="flex items-center gap-3 pt-1 px-1 relative z-10">
                            <div class="relative flex h-2 w-2">
                              <span v-if="connected" class="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                              <span class="relative inline-flex rounded-full h-2 w-2" :class="connected ? 'bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)]' : 'bg-red-500'"></span>
                            </div>
                            <div class="flex flex-col"><span class="text-xs font-medium text-gray-300">Агент онлайн</span><span class="text-[10px] text-gray-600">v1.6.5 • {{ store.chats.length }} чатов</span></div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `,
    setup() {
        const searchQuery = ref('');
        const selectedModel = ref('');
        const isModelMenuOpen = ref(false);
        const modelMenuRef = ref(null);
        const editingId = ref(null);
        const editName = ref('');
        const editInput = ref(null);
        const activePresetMenuId = ref(null);

        const refreshModels = async () => {
            const res = await api.fetchModels();
            if (Array.isArray(res)) {
                store.models = res;
            }
        };

        const selectModel = async (modelName) => {
            selectedModel.value = modelName;
            isModelMenuOpen.value = false;
            await updateModel();
        }

        const updateModel = async () => {
            if (store.currentChatId && selectedModel.value) {
                const res = await api.changeModel(store.currentChatId, selectedModel.value);
                if (res.status === 'model_changed') store.addToast('Модель изменена', 'success');
            }
        };

        const handleClickOutside = (event) => {
            if (modelMenuRef.value && !modelMenuRef.value.contains(event.target)) {
                isModelMenuOpen.value = false;
            }
            if (activePresetMenuId.value) {
                 const isBtn = event.target.closest('button[title="Сменить пресет"]');
                 const isMenu = event.target.closest('.absolute.bottom-full.right-0');
                 if (!isBtn && !isMenu) activePresetMenuId.value = null;
            }
        };

        const clearContext = async (id) => {
            if (confirm('Это удалит переменные и окружение Python, но сохранит историю. Продолжить?')) {
                const res = await api.clearContext(id);
                if (res.status === 'context_cleared') {
                    store.addToast('Контекст очищен', 'success');
                    if (store.currentChatId === id) {
                         const data = await api.loadChat(id);
                         store.setMessages(data.chat.messages);
                    }
                }
            }
        };

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
            if (store.currentChatId === id) return;

            try {
                const data = await api.loadChat(id);
                if (data.error) {
                    store.addToast(data.error, 'error');
                    return; 
                }
                store.currentChatId = id;
                store.activePresetId = data.chat.active_preset_id || 'default';
                store.setMessages(data.chat.messages);
                
                if (data.chat.model) {
                    selectedModel.value = data.chat.model;
                } else {
                    if (store.models.length > 0 && !selectedModel.value) selectedModel.value = store.models[1][0]; 
                }

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
        
        const togglePresetMenu = (id) => {
            activePresetMenuId.value = activePresetMenuId.value === id ? null : id;
        };
        const selectPreset = async (chatId, presetId) => {
            const res = await api.changeChatPreset(chatId, presetId);
            if (res.status === 'ok') {
                if (store.currentChatId === chatId) store.activePresetId = presetId;
                store.addToast('Пресет изменен', 'success');
            }
            activePresetMenuId.value = null;
        };

        onMounted(async () => {
             document.addEventListener('click', handleClickOutside);
             await refreshModels();
             await refreshList();
             if (!selectedModel.value && store.models.length > 0) {
                 selectedModel.value = store.models[1][0]; 
             }
        });
        
        onUnmounted(() => {
            document.removeEventListener('click', handleClickOutside);
        });
        
        return { 
            store, 
            selectedModel, 
            updateModel, 
            isModelMenuOpen,
            selectModel,
            modelMenuRef,
            clearContext, 
            createNew, 
            deleteChat, 
            selectChat, 
            startTemp, 
            connected: true, 
            searchQuery, 
            filteredChats, 
            editingId, 
            editName, 
            startRename, 
            saveRename, 
            cancelRename, 
            editInput, activePresetMenuId, togglePresetMenu, selectPreset
        };
    }
}