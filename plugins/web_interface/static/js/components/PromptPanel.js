import { store } from '../store.js';
import * as api from '../api.js';
import { onMounted, ref, watch, computed } from 'vue';

export default {
    template: `
        <div>
            <!-- Mobile Backdrop -->
            <Teleport to="body">
                <div v-if="store.isPromptPanelOpen" 
                     class="fixed inset-0 bg-black/60 backdrop-blur-md z-[60] md:hidden transition-all duration-300"
                     @click="store.isPromptPanelOpen = false"></div>
            </Teleport>

            <!-- Panel Container -->
            <div class="fixed md:relative inset-y-0 right-0 h-full bg-gray-950/95 backdrop-blur-2xl border-l border-white/5 flex flex-col flex-shrink-0 z-[70] transition-all duration-300 ease-in-out shadow-2xl"
                 :class="[
                    !store.isPromptPanelOpen ? 'w-0 translate-x-full opacity-0 border-none pointer-events-none' : 
                    (isExpanded ? 'w-full md:w-[700px] translate-x-0 opacity-100' : 'w-[360px] translate-x-0 opacity-100')
                 ]">
                
                <div class="flex flex-col h-full w-full overflow-hidden">
                    <!-- Header -->
                    <div class="p-5 flex items-center justify-between border-b border-white/5 bg-white/5">
                        <div class="flex items-center gap-3">
                            <div class="w-8 h-8 rounded-lg bg-blue-500/20 flex items-center justify-center">
                                <i class="ph-bold ph-terminal-window text-blue-400"></i>
                            </div>
                            <span class="font-bold text-gray-100 text-xs uppercase tracking-widest">Центр управления</span>
                        </div>
                        <button v-if="editPromptId || isCreating" @click="closeEditor" class="text-gray-500 hover:text-white transition-colors">
                            <i class="ph-bold ph-x text-lg"></i>
                        </button>
                    </div>

                    <!-- Dashboard Mode -->
                    <div v-if="!editPromptId && !isCreating" class="flex-1 overflow-y-auto custom-scrollbar p-5 space-y-8">
                        <div class="flex justify-between items-center px-1">
                             <h3 class="text-[10px] font-bold text-gray-500 uppercase tracking-[0.2em]">Ваши промпты</h3>
                             <button @click="createNewPrompt" class="text-[10px] font-bold text-blue-400 hover:text-blue-300 transition-colors bg-blue-500/10 px-3 py-1.5 rounded-lg uppercase tracking-wider">+ Создать</button>
                        </div>

                        <!-- Categorized List -->
                        <div v-for="type in ['system', 'parameter', 'command']" :key="type" class="space-y-4">
                            <div class="flex items-center gap-2 px-1">
                                <i :class="getTypeIcon(type)" class="text-xs text-blue-400/50"></i>
                                <span class="text-[10px] font-bold text-gray-500 uppercase tracking-widest">{{ getTypeName(type) }}</span>
                            </div>
                            
                            <div class="grid grid-cols-1 gap-3">
                                <div v-for="(p, id) in getPromptsByType(type)" :key="id" 
                                     class="group relative bg-white/[0.03] border border-white/5 hover:border-blue-500/30 rounded-2xl p-4 transition-all duration-300 hover:bg-white/[0.06] shadow-sm">
                                    <div class="flex items-center justify-between gap-3">
                                        <div class="flex items-center gap-4 min-w-0">
                                            <div class="w-12 h-12 rounded-xl bg-gray-900 border border-white/5 flex items-center justify-center text-2xl shadow-inner group-hover:scale-110 transition-transform">
                                                <i :class="['ph-bold', p.icon || 'ph-app-window']" class="text-blue-400/80"></i>
                                            </div>
                                            <div class="truncate">
                                                <div class="text-sm font-semibold text-gray-100 truncate mb-0.5">{{ p.name }}</div>
                                                <div class="text-[10px] text-gray-500 truncate opacity-60 font-mono">{{ p.text.substring(0, 45) }}...</div>
                                            </div>
                                        </div>
                                        
                                        <div class="flex items-center gap-2">
                                            <div v-if="type === 'system' && store.activePromptId === id" class="w-2 h-2 rounded-full bg-blue-500 shadow-[0_0_8px_#3b82f6]"></div>
                                            
                                            <div v-if="type === 'parameter'" 
                                                 @click.stop="store.toggleParameter(id)"
                                                 class="w-10 h-5 rounded-full relative cursor-pointer transition-all duration-300"
                                                 :class="store.active_parameters.includes(id) ? 'bg-blue-600' : 'bg-white/10'">
                                                <div class="absolute top-1 left-1 w-3 h-3 rounded-full bg-white transition-all shadow-md"
                                                     :class="store.active_parameters.includes(id) ? 'translate-x-5' : 'translate-x-0'"></div>
                                            </div>

                                            <button @click.stop="selectForEdit(id, p)" class="p-2 text-gray-500 hover:text-white hover:bg-white/10 rounded-lg transition-all opacity-0 group-hover:opacity-100">
                                                <i class="ph-bold ph-pencil-simple"></i>
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- Editor Mode -->
                    <div v-else class="flex-1 flex flex-col p-6 gap-6 animate-fade-in relative">
                        <div class="flex items-center justify-between">
                            <div class="flex items-center gap-3">
                                <span class="px-2 py-1 rounded bg-blue-500/20 text-blue-400 text-[9px] font-bold uppercase tracking-widest">{{ getTypeName(editPromptData.type) }}</span>
                                <h2 class="text-sm font-bold text-white uppercase tracking-widest">{{ isCreating ? 'Новый промпт' : 'Настройка' }}</h2>
                            </div>
                            <button @click="isExpanded = !isExpanded" class="p-2 text-gray-400 hover:text-white bg-white/5 rounded-lg transition-all" :title="isExpanded ? 'Свернуть' : 'На весь экран'">
                                <i class="ph-bold" :class="isExpanded ? 'ph-corners-in' : 'ph-corners-out'"></i>
                            </button>
                        </div>

                        <div class="flex flex-col flex-1 gap-5 overflow-y-auto custom-scrollbar pr-2">
                            <div class="space-y-2">
                                <label class="text-[10px] font-bold text-gray-500 uppercase tracking-widest px-1">Тип промпта</label>
                                <div class="grid grid-cols-3 gap-2">
                                    <button v-for="t in ['system', 'parameter', 'command']" :key="t"
                                        @click="editPromptData.type = t"
                                        class="py-2.5 rounded-xl text-[10px] font-bold uppercase transition-all border"
                                        :class="editPromptData.type === t ? 'bg-blue-600 border-blue-400 text-white shadow-lg shadow-blue-500/20' : 'bg-white/5 border-transparent text-gray-500 hover:bg-white/10'">
                                        {{ getTypeName(t) }}
                                    </button>
                                </div>
                            </div>

                            <div class="flex gap-4">
                                <div class="flex-1 space-y-2">
                                    <label class="text-[10px] font-bold text-gray-500 uppercase tracking-widest px-1">Название</label>
                                    <input v-model="editPromptData.name" class="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 focus:outline-none focus:border-blue-500/50 text-xs text-gray-200 transition-all">
                                </div>
                                <div class="w-20 space-y-2">
                                    <label class="text-[10px] font-bold text-gray-500 uppercase tracking-widest px-1">Иконка</label>
                                    <div class="relative">
                                        <button @click="isIconPickerOpen = !isIconPickerOpen" class="w-full h-[46px] bg-white/5 border border-white/10 rounded-xl flex items-center justify-center text-2xl hover:bg-white/10 text-blue-400 transition-colors">
                                            <i :class="['ph-bold', editPromptData.icon || 'ph-app-window']"></i>
                                        </button>
                                        <div v-if="isIconPickerOpen" class="absolute bottom-full right-0 mb-3 bg-gray-900 border border-white/10 p-3 rounded-2xl grid grid-cols-4 gap-2 z-[100] w-48 shadow-2xl animate-fade-in-up">
                                            <button v-for="ic in commonIcons" :key="ic" @click="selectIcon(ic)" class="w-10 h-10 flex items-center justify-center hover:bg-blue-600 rounded-xl text-xl transition-all hover:scale-110">
                                                <i :class="['ph-bold', ic]"></i>
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            </div>

                            <div class="flex-1 flex flex-col space-y-2">
                                <label class="text-[10px] font-bold text-gray-500 uppercase tracking-widest px-1">Инструкция (Промпт)</label>
                                <textarea v-model="editPromptData.text" 
                                    class="flex-1 w-full min-h-[250px] bg-white/5 border border-white/10 rounded-2xl px-4 py-4 focus:outline-none focus:border-blue-500/50 text-xs font-mono resize-none text-gray-300 custom-scrollbar leading-relaxed"></textarea>
                            </div>
                        </div>

                        <div class="flex justify-between items-center pt-5 border-t border-white/5 bg-gray-950/50">
                            <button v-if="editPromptId" @click="deletePrompt(editPromptId)" class="p-3 text-red-500/60 hover:text-red-400 hover:bg-red-500/10 rounded-xl transition-all">
                                <i class="ph-bold ph-trash text-lg"></i>
                            </button>
                            <div v-else></div>
                            <div class="flex gap-3">
                                <button v-if="editPromptId && editPromptData.type === 'system' && store.activePromptId !== editPromptId" @click="setActivePrompt(editPromptId)" class="px-5 py-2.5 bg-emerald-500/10 text-emerald-400 rounded-xl text-[10px] font-bold uppercase border border-emerald-500/20 hover:bg-emerald-500/20 transition-all">Использовать как систему</button>
                                <button @click="savePrompt" class="px-10 py-3 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-[10px] font-bold uppercase shadow-xl shadow-blue-600/30 transition-all active:scale-95">Сохранить</button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `,
    setup() {
        const editPromptId = ref(null);
        const editPromptData = ref({name: '', text: '', type: 'system', icon: 'ph-app-window'});
        const isCreating = ref(false);
        const isExpanded = ref(false);
        const isIconPickerOpen = ref(false);

        const commonIcons = ['ph-robot', 'ph-strategy', 'ph-test-tube', 'ph-code', 'ph-bug', 'ph-terminal', 'ph-lightning', 'ph-sparkle', 'ph-brain', 'ph-wrench', 'ph-shield', 'ph-globe', 'ph-database', 'ph-gear', 'ph-file-code', 'ph-magic-wand', 'ph-cpu'];

        const refresh = async () => {
            const config = await api.fetchFinalPrompts();
            store.finalPrompts = config.prompts || {};
            store.activePromptId = config.active_id;
            store.active_parameters = config.active_parameters || [];
        };

        const getPromptsByType = (type) => {
            const res = {};
            for (const [id, p] of Object.entries(store.finalPrompts)) {
                if (p.type === type || (!p.type && type === 'system')) res[id] = p;
            }
            return res;
        };

        const getTypeName = (t) => ({system: 'Система', parameter: 'Режим', command: 'Команда'}[t]);
        const getTypeIcon = (t) => ({system: 'ph-fill ph-monitor', parameter: 'ph-fill ph-toggle-left', command: 'ph-fill ph-terminal'}[t]);

        const selectForEdit = (id, p) => {
            isCreating.value = false;
            editPromptId.value = id;
            editPromptData.value = { 
                name: p.name, 
                text: p.text, 
                type: p.type || 'system', 
                icon: p.icon || 'ph-app-window' 
            };
        };

        const createNewPrompt = () => {
            editPromptId.value = null;
            isCreating.value = true;
            editPromptData.value = {name: 'Новый промпт', text: '', type: 'system', icon: 'ph-robot'};
        };

        const selectIcon = (icon) => {
            editPromptData.value.icon = icon;
            isIconPickerOpen.value = false;
        };

        const savePrompt = async () => {
            const res = await api.saveFinalPrompt(
                editPromptId.value, 
                editPromptData.value.name, 
                editPromptData.value.text,
                editPromptData.value.type,
                editPromptData.value.icon
            );
            if (res.status === 'ok') {
                store.addToast('Сохранено', 'success');
                await refresh();
                closeEditor();
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
            if (confirm('Удалить этот промпт?')) {
                const res = await api.deleteFinalPrompt(id);
                if (res.status === 'deleted') {
                    await refresh();
                    closeEditor();
                    store.addToast('Удалено', 'info');
                }
            }
        };

        const closeEditor = () => {
            editPromptId.value = null;
            isCreating.value = false;
            isExpanded.value = false;
            isIconPickerOpen.value = false;
        };

        onMounted(refresh);
        watch(() => store.isPromptPanelOpen, (val) => { if(val) refresh(); });

        return { store, editPromptId, editPromptData, isCreating, isExpanded, isIconPickerOpen, commonIcons, createNewPrompt, selectIcon, savePrompt, setActivePrompt, deletePrompt, selectForEdit, closeEditor, getPromptsByType, getTypeName, getTypeIcon };
    }
}
