import { store } from '../store.js';
import * as api from '../api.js';
import { onMounted, ref, watch } from 'vue';

export default {
    template: `
        <div>
            <!-- Mobile Backdrop (Fixed instructions) -->
            <Teleport to="body">
                <div v-if="store.isPromptPanelOpen" 
                     class="fixed inset-0 bg-black/40 backdrop-blur-md z-[60] md:hidden transition-all duration-300"
                     @click="store.isPromptPanelOpen = false"></div>
            </Teleport>

            <!-- Panel Container -->
            <div class="fixed md:relative inset-y-0 right-0 h-full bg-gray-950/60 backdrop-blur-xl border-l border-white/5 flex flex-col flex-shrink-0 z-[70] transition-all duration-300 ease-in-out overflow-hidden"
                 :class="store.isPromptPanelOpen ? 'w-[320px] translate-x-0 opacity-100' : 'w-0 translate-x-full md:translate-x-0 opacity-0 border-none'">
                
                <div class="flex flex-col h-full w-[320px]">
                    <!-- Header -->
                    <div class="p-5 flex items-center justify-between border-b border-white/5 bg-white/5">
                        <div class="flex items-center gap-2">
                            <i class="ph-bold ph-terminal-window text-blue-400"></i>
                            <span class="font-bold text-gray-100 text-xs uppercase tracking-wider">Инструкции</span>
                        </div>
                    </div>

                    <!-- List of Presets -->
                    <div class="p-4 space-y-2 overflow-y-auto custom-scrollbar border-b border-white/5 bg-black/20">
                        <div class="flex items-center justify-between mb-2 px-1">
                            <label class="text-[10px] font-bold text-gray-500 uppercase tracking-widest">Пресеты</label>
                            <button @click="createNewPrompt" class="text-[10px] font-bold text-blue-400 hover:text-blue-300 uppercase tracking-widest">+ Новый</button>
                        </div>
                        <div class="flex flex-wrap gap-2">
                            <button v-for="(p, id) in store.finalPrompts" :key="id" 
                                @click="selectForEdit(id, p)"
                                class="px-3 py-1.5 rounded-lg text-xs transition-all border flex items-center gap-2"
                                :class="editPromptId === id ? 'bg-blue-600/20 text-blue-300 border-blue-500/50' : 'bg-white/5 text-gray-500 border-transparent hover:bg-white/10'">
                                <span class="truncate max-w-[100px]">{{ p.name }}</span>
                                <i v-if="store.activePromptId === id" class="ph-fill ph-check-circle text-emerald-500"></i>
                            </button>
                        </div>
                    </div>

                    <!-- Editor -->
                    <div class="flex-1 flex flex-col p-4 gap-4 overflow-hidden">
                        <div v-if="editPromptId || isCreating" class="flex flex-col h-full gap-4">
                            <div class="space-y-1">
                                <label class="text-[10px] font-bold text-gray-500 uppercase tracking-widest px-1">Название</label>
                                <input v-model="editPromptData.name" class="w-full bg-gray-900 border border-white/5 rounded-xl px-3 py-2 focus:outline-none focus:border-blue-500/50 text-xs text-gray-200">
                            </div>
                            <div class="flex-1 flex flex-col space-y-1 overflow-hidden">
                                <label class="text-[10px] font-bold text-gray-500 uppercase tracking-widest px-1">Текст промпта</label>
                                <textarea v-model="editPromptData.text" 
                                    class="flex-1 w-full bg-gray-900 border border-white/5 rounded-xl px-3 py-3 focus:outline-none focus:border-blue-500/50 text-xs font-mono resize-none text-gray-400 custom-scrollbar"></textarea>
                            </div>
                            <div class="flex justify-between items-center gap-2">
                                <button v-if="editPromptId" @click="deletePrompt(editPromptId)" class="p-2 text-red-500/60 hover:text-red-400 hover:bg-red-500/10 rounded-lg transition-colors">
                                    <i class="ph-bold ph-trash"></i>
                                </button>
                                <div v-else></div>
                                <div class="flex gap-2">
                                    <button v-if="editPromptId && store.activePromptId !== editPromptId" @click="setActivePrompt(editPromptId)" class="px-3 py-2 bg-emerald-500/10 text-emerald-400 rounded-lg text-[10px] font-bold uppercase border border-emerald-500/20">Выбрать</button>
                                    <button @click="savePrompt" class="px-5 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-[10px] font-bold uppercase shadow-lg shadow-blue-500/20">Сохранить</button>
                                </div>
                            </div>
                        </div>
                        <div v-else class="h-full flex flex-col items-center justify-center opacity-30 text-center p-6">
                            <i class="ph-bold ph-terminal-window text-5xl mb-4"></i>
                            <p class="text-xs">Выберите пресет для редактирования</p>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `,
    setup() {
        const editPromptId = ref(null);
        const editPromptData = ref({name: '', text: ''});
        const isCreating = ref(false);

        const refresh = async () => {
            const config = await api.fetchFinalPrompts();
            store.finalPrompts = config.prompts || {};
            store.activePromptId = config.active_id;
        };

        const selectForEdit = (id, p) => {
            isCreating.value = false;
            editPromptId.value = id;
            editPromptData.value = {...p};
        };

        const createNewPrompt = () => {
            editPromptId.value = null;
            isCreating.value = true;
            editPromptData.value = {name: 'Новый вариант', text: ''};
        };

        const savePrompt = async () => {
            const res = await api.saveFinalPrompt(editPromptId.value, editPromptData.value.name, editPromptData.value.text);
            if (res.status === 'ok') {
                store.addToast('Сохранено', 'success');
                await refresh();
                editPromptId.value = res.id;
                isCreating.value = false;
            }
        };

        const setActivePrompt = async (id) => {
            const res = await api.selectFinalPrompt(id);
            if (res.status === 'ok') {
                store.activePromptId = id;
                store.addToast('Активный промпт изменен', 'success');
            }
        };

        const deletePrompt = async (id) => {
            if (confirm('Удалить?')) {
                const res = await api.deleteFinalPrompt(id);
                if (res.status === 'deleted') {
                    await refresh();
                    editPromptId.value = null;
                    store.addToast('Удалено', 'info');
                }
            }
        };

        onMounted(refresh);
        watch(() => store.isPromptPanelOpen, (val) => { if(val) refresh(); });

        return { store, editPromptId, editPromptData, isCreating, createNewPrompt, savePrompt, setActivePrompt, deletePrompt, selectForEdit };
    }
}
