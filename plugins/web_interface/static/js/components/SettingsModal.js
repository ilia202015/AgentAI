import { store } from '../store.js';
import { defineComponent } from 'vue';

export default defineComponent({
    setup() {
        return { store };
    },
    template: `
        <Teleport to="body">
            <div v-if="store.isSettingsModalOpen" class="fixed inset-0 z-[100] flex items-center justify-center p-4">
                <!-- Backdrop -->
                <div class="absolute inset-0 bg-black/60 backdrop-blur-sm transition-opacity" @click="store.toggleSettingsModal()"></div>
                
                <!-- Modal -->
                <div class="relative bg-gray-900 border border-white/10 rounded-2xl shadow-2xl w-full max-w-md overflow-hidden animate-fade-in-up">
                    <div class="p-5 border-b border-white/5 flex justify-between items-center bg-white/[0.02]">
                        <div class="flex items-center gap-3">
                            <div class="w-8 h-8 rounded-lg bg-blue-500/20 flex items-center justify-center text-blue-400">
                                <i class="ph-bold ph-sliders"></i>
                            </div>
                            <h2 class="text-lg font-bold text-gray-100 tracking-tight">Параметры интерфейса</h2>
                        </div>
                        <button @click="store.toggleSettingsModal()" class="text-gray-500 hover:text-white transition-colors p-1 rounded-lg hover:bg-white/10">
                            <i class="ph-bold ph-x text-xl"></i>
                        </button>
                    </div>
                    
                    <div class="p-6 space-y-6">
                        <!-- Фон -->
                        <div class="space-y-3">
                            <label class="text-[10px] font-bold text-gray-500 uppercase tracking-widest">Анимированный фон</label>
                            <div class="grid grid-cols-2 gap-2">
                                <button v-for="bg in [{id:'none', name:'Тёмный (Откл)'}, {id:'neon', name:'Неоновые сферы'}, {id:'grid', name:'Кибер-сетка'}, {id:'stars', name:'Звездный поток'}]" 
                                        :key="bg.id"
                                        @click="store.updateUISettings({bgType: bg.id})"
                                        class="p-3 rounded-xl border transition-all text-xs text-left"
                                        :class="store.bgType === bg.id ? 'bg-blue-600/20 border-blue-500/50 text-blue-400 shadow-inner' : 'bg-white/5 border-transparent text-gray-400 hover:bg-white/10 hover:text-gray-200'">
                                    {{ bg.name }}
                                </button>
                            </div>
                        </div>

                        <!-- Размытие -->
                        <div class="space-y-3">
                            <label class="text-[10px] font-bold text-gray-500 uppercase tracking-widest">Размытие интерфейса (Blur)</label>
                            <div class="flex gap-2">
                                <button v-for="blur in ['none', 'sm', 'md', 'lg', 'xl', '2xl', '3xl']" 
                                        :key="blur"
                                        @click="store.updateUISettings({uiBlurLevel: blur})"
                                        class="flex-1 py-2 rounded-lg border transition-all text-[10px] uppercase font-bold"
                                        :class="store.uiBlurLevel === blur ? 'bg-indigo-600/20 border-indigo-500/50 text-indigo-400' : 'bg-white/5 border-transparent text-gray-500 hover:bg-white/10 hover:text-gray-300'">
                                    {{ blur === 'none' ? '0' : blur }}
                                </button>
                            </div>
                        </div>

                        <!-- Затемнение -->
                        <div class="space-y-3">
                            <div class="flex justify-between items-end">
                                <label class="text-[10px] font-bold text-gray-500 uppercase tracking-widest">Затемнение подложек</label>
                                <span class="text-xs font-mono text-gray-400">{{ store.uiDimmingPercent }}%</span>
                            </div>
                            <input type="range" min="0" max="100" step="5" 
                                   :value="store.uiDimmingPercent"
                                   @input="e => store.updateUISettings({uiDimmingPercent: parseInt(e.target.value)})"
                                   class="w-full h-2 bg-white/10 rounded-lg appearance-none cursor-pointer accent-blue-500">
                        </div>
                    </div>
                </div>
            </div>
        </Teleport>
    `
});
