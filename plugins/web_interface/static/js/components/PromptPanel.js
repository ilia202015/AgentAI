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
            <div class="fixed md:relative inset-y-0 right-0 h-full bg-gray-900/40 backdrop-blur-xl border-l border-white/5 flex flex-col flex-shrink-0 z-[70] transition-all duration-300 ease-in-out shadow-2xl"
                 :class="[
                    !store.isPromptPanelOpen ? 'w-0 translate-x-full opacity-0 border-none pointer-events-none' : 
                    (isExpanded ? 'w-full md:w-[700px] translate-x-0 opacity-100' : 'w-[360px] translate-x-0 opacity-100')
                 ]">
                
                <div class="flex flex-col h-full w-full overflow-hidden">
                    <!-- Header -->
                    <div class="p-4 flex flex-col gap-4 border-b border-white/5 bg-transparent">
                        <div class="flex items-center justify-between">
                            <div class="flex items-center gap-3">
                                <div class="w-8 h-8 rounded-lg bg-blue-500/20 flex items-center justify-center">
                                    <i class="ph-bold ph-terminal-window text-blue-400"></i>
                                </div>
                                <span class="font-bold text-gray-100 text-xs uppercase tracking-widest">Центр управления</span>
                            </div>
                            <button v-if="editPromptId || isCreating || editPresetId || isCreatingPreset" @click="closeEditor" class="text-gray-500 hover:text-white transition-colors">
                                <i class="ph-bold ph-x text-lg"></i>
                            </button>
                        </div>

                        <!-- Tab Switcher -->
                        <div v-if="!editPromptId && !isCreating && !editPresetId && !isCreatingPreset" class="flex p-1 bg-white/5 rounded-xl border border-white/5">
                            <button @click="activeTab = 'prompts'" 
                                class="flex-1 py-2 text-[10px] font-bold uppercase tracking-wider transition-all rounded-lg"
                                :class="activeTab === 'prompts' ? 'bg-blue-600 text-white shadow-lg shadow-blue-500/20' : 'text-gray-500 hover:text-gray-300'">
                                Промпты
                            </button>
                            <button @click="activeTab = 'presets'" 
                                class="flex-1 py-2 text-[10px] font-bold uppercase tracking-wider transition-all rounded-lg"
                                :class="activeTab === 'presets' ? 'bg-blue-600 text-white shadow-lg shadow-blue-500/20' : 'text-gray-500 hover:text-gray-300'">
                                Пресеты
                            </button>
                        </div>
                    </div>

                    <!-- PROMPTS TAB -->
                    <div v-if="activeTab === 'prompts'" class="flex-1 flex flex-col overflow-hidden">
                        <!-- Dashboard Mode -->
                        <div v-if="!editPromptId && !isCreating" class="flex-1 overflow-y-auto custom-scrollbar p-5 space-y-8">
                            <div class="flex justify-between items-center px-1">
                                 <h3 class="text-[10px] font-bold text-gray-500 uppercase tracking-[0.2em]">Ваши промпты</h3>
                                 <button @click="createNewPrompt" class="text-[10px] font-bold text-blue-400 hover:text-blue-300 transition-colors bg-blue-500/10 px-3 py-1.5 rounded-lg uppercase tracking-wider">+ Создать</button>
                            </div>

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
                                                <div class="w-10 h-10 rounded-xl bg-gray-900 border border-white/5 flex items-center justify-center text-xl shadow-inner group-hover:scale-110 transition-transform">
                                                    <i :class="['ph-bold', p.icon || 'ph-app-window']" class="text-blue-400/80"></i>
                                                </div>
                                                <div class="truncate">
                                                    <div class="text-xs font-semibold text-gray-100 truncate mb-0.5">{{ p.name }}</div>
                                                    <div class="text-[9px] text-gray-500 truncate opacity-60 font-mono">{{ p.text.substring(0, 45) }}...</div>
                                                </div>
                                            </div>
                                            <div class="flex items-center gap-2">
                                                <div v-if="type === 'system' && store.activePromptId === id" class="w-2 h-2 rounded-full bg-blue-500 shadow-[0_0_8px_#3b82f6]"></div>
                                                <div v-if="type === 'parameter'" @click.stop="store.toggleParameter(id)"
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

                        <!-- Prompt Editor Mode -->
                        <div v-else class="flex-1 flex flex-col p-6 gap-4 animate-fade-in relative h-full">
                            <div class="flex items-center justify-between">
                                <div class="flex items-center gap-3">
                                    <span class="px-2 py-1 rounded bg-blue-500/20 text-blue-400 text-[9px] font-bold uppercase tracking-widest">{{ getTypeName(editPromptData.type) }}</span>
                                    <h2 class="text-sm font-bold text-white uppercase tracking-widest">{{ isCreating ? 'Новый промпт' : 'Настройка' }}</h2>
                                </div>
                                <button @click="isExpanded = !isExpanded" class="p-2 text-gray-400 hover:text-white bg-white/5 rounded-lg transition-all">
                                    <i class="ph-bold" :class="isExpanded ? 'ph-corners-in' : 'ph-corners-out'"></i>
                                </button>
                            </div>
                            <div class="flex flex-col flex-1 gap-5 overflow-y-auto custom-scrollbar pr-2 pb-10">
                                <div class="space-y-2">
                                    <label class="text-[10px] font-bold text-gray-500 uppercase tracking-widest px-1">Тип промпта</label>
                                    <div class="grid grid-cols-3 gap-2">
                                        <button v-for="t in ['system', 'parameter', 'command']" :key="t"
                                            @click="editPromptData.type = t"
                                            class="py-2 rounded-xl text-[10px] font-bold uppercase transition-all border"
                                            :class="editPromptData.type === t ? 'bg-blue-600 border-blue-400 text-white shadow-lg' : 'bg-white/5 border-transparent text-gray-500 hover:bg-white/10'">
                                            {{ getTypeName(t) }}
                                        </button>
                                    </div>
                                </div>
                                <div class="flex gap-4">
                                    <div class="flex-1 space-y-2">
                                        <label class="text-[10px] font-bold text-gray-500 uppercase tracking-widest px-1">Название</label>
                                        <input v-model="editPromptData.name" class="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 focus:outline-none focus:border-blue-500/50 text-xs text-gray-200">
                                    </div>
                                    <div class="w-20 space-y-2">
                                        <label class="text-[10px] font-bold text-gray-500 uppercase tracking-widest px-1">Иконка</label>
                                        <button @click="isIconPickerOpen = !isIconPickerOpen" class="w-full h-[46px] bg-white/5 border border-white/10 rounded-xl flex items-center justify-center text-2xl hover:bg-white/10 text-blue-400 relative">
                                            <i :class="['ph-bold', editPromptData.icon || 'ph-app-window']"></i>
                                            <div v-if="isIconPickerOpen" class="absolute top-full right-0 mt-2 bg-gray-900 border border-white/10 p-3 rounded-2xl grid grid-cols-4 gap-2 z-[110] w-56 shadow-2xl animate-fade-in-up">
                                                <button v-for="ic in commonIcons" :key="ic" @click.stop="selectIcon(ic)" class="w-10 h-10 flex items-center justify-center hover:bg-blue-600 rounded-xl text-xl transition-all">
                                                    <i :class="['ph-bold', ic]"></i>
                                                </button>
                                            </div>
                                        </button>
                                    </div>
                                </div>
                                <div class="flex-1 flex flex-col space-y-2">
                                    <label class="text-[10px] font-bold text-gray-500 uppercase tracking-widest px-1">Инструкция (Промпт)</label>
                                    <textarea v-model="editPromptData.text" class="flex-1 w-full min-h-[150px] bg-white/5 border border-white/10 rounded-2xl px-4 py-4 focus:outline-none focus:border-blue-500/50 text-xs font-mono resize-none text-gray-300 custom-scrollbar"></textarea>
                                </div>
                                <div v-if="editPromptData.type === 'parameter'" class="space-y-2">
                                    <label class="text-[10px] font-bold text-gray-500 uppercase tracking-widest px-1">Скрипт сбора данных (Gather Script)</label>
                                    <textarea v-model="editPromptData.gather_script" placeholder="Python код. Результат должен быть в переменной result..." class="w-full min-h-[100px] bg-white/5 border border-white/10 rounded-2xl px-4 py-4 focus:outline-none focus:border-blue-500/50 text-xs font-mono resize-none text-blue-300 custom-scrollbar"></textarea>
                                    <p class="text-[9px] text-gray-600 italic px-1 leading-tight">Этот код выполняется агентом каждый раз при отправке сообщения в режиме, если режим активен. Результат выполнения кода добавляется в контекст.</p>
                                </div>

                                                                <div v-if="editPromptData.type === 'command'" class="space-y-2">
                                    <label class="text-[10px] font-bold text-gray-500 uppercase tracking-widest px-1">Скрипт выполнения (Exec Script)</label>
                                    <textarea v-model="editPromptData.exec_script" placeholder="Python код. Результат будет в переменной result..." class="w-full min-h-[100px] bg-white/5 border border-white/10 rounded-2xl px-4 py-4 focus:outline-none focus:border-blue-500/50 text-xs font-mono resize-none text-emerald-400 custom-scrollbar"></textarea>
                                    <p class="text-[9px] text-gray-600 italic px-1 leading-tight">Выполняется при нажатии на кнопку команды. Результат записывается после текста промпта.</p>
                                </div>
                                <!-- Mode FS Permissions Selection -->
                                <div v-if="editPromptData.type === 'parameter'" class="space-y-4">
                                    <label class="text-[10px] font-bold text-gray-500 uppercase tracking-widest px-1">Файловая система (ACL)</label>
                                    <div class="p-4 bg-white/5 rounded-2xl border border-white/5 space-y-4">
                                        <div class="flex items-center justify-between gap-4">
                                            <span class="text-[10px] text-gray-400 font-bold uppercase tracking-tight">Глобальные права:</span>
                                            <input v-model="editPromptData.fs_permissions.global" class="w-24 bg-black/40 border border-white/10 rounded-lg px-2 py-1 text-xs text-blue-400 font-mono text-center focus:border-blue-500/50 outline-none" placeholder="rwxld">
                                        </div>
                                        <div class="space-y-2">
                                            <div v-for="(perms, pth) in editPromptData.fs_permissions.paths" :key="pth" class="flex items-center gap-2 group animate-fade-in">
                                                <div class="flex-1 bg-white/5 border border-white/5 rounded-lg px-3 py-1.5 text-[10px] text-gray-500 font-mono truncate">{{ pth }}</div>
                                                <input v-model="editPromptData.fs_permissions.paths[pth]" class="w-16 bg-black/40 border border-white/10 rounded-lg px-2 py-1.5 text-[10px] text-indigo-400 font-mono text-center focus:border-indigo-500/50 outline-none">
                                                <button @click="delete editPromptData.fs_permissions.paths[pth]" class="p-1.5 text-red-500/40 hover:text-red-400 transition-colors"><i class="ph ph-trash"></i></button>
                                            </div>
                                            <div class="flex gap-2 pt-2">
                                                <input v-model="newPath" @keydown.enter="addPath" placeholder="Путь (н-р: temp/)" class="flex-1 bg-white/5 border border-white/10 rounded-lg px-3 py-1.5 text-[10px] text-gray-300 focus:border-blue-500/50 outline-none">
                                                <button @click="addPath" class="px-4 py-1.5 bg-blue-600/20 text-blue-400 rounded-lg text-[10px] font-bold uppercase hover:bg-blue-600/40 transition-all">Добавить</button>
                                            </div>
                                        </div>
                                        <p class="text-[9px] text-gray-600 italic px-1 leading-tight">Флаги: R, W, X, L, D. Права режима пересекаются с правами пресета, ограничивая их.</p>
                                    </div>
                                </div>
                            </div>
                            <div class="flex justify-between items-center py-4 border-t border-white/10 mt-auto">
                                <button v-if="editPromptId" @click="deletePrompt(editPromptId)" class="p-3 text-red-500/60 hover:text-red-400 hover:bg-red-500/10 rounded-xl transition-all"><i class="ph-bold ph-trash text-lg"></i></button>
                                <div v-else></div>
                                <div class="flex gap-3">
                                    <button v-if="editPromptId && editPromptData.type === 'system' && store.activePromptId !== editPromptId" @click="setActivePrompt(editPromptId)" class="px-5 py-2.5 bg-emerald-500/10 text-emerald-400 rounded-xl text-[10px] font-bold uppercase border border-emerald-500/20">Как система</button>
                                    <button @click="savePrompt" class="px-10 py-3 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-[10px] font-bold uppercase shadow-xl">Сохранить</button>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- PRESETS TAB -->
                    <div v-else-if="activeTab === 'presets'" class="flex-1 flex flex-col overflow-hidden">
                        <!-- Dashboard Mode -->
                        <div v-if="!editPresetId && !isCreatingPreset" class="flex-1 overflow-y-auto custom-scrollbar p-5 space-y-6">
                            <div class="flex justify-between items-center px-1">
                                 <h3 class="text-[10px] font-bold text-gray-500 uppercase tracking-[0.2em]">Пресеты рабочих пространств</h3>
                                 <button @click="createNewPreset" class="text-[10px] font-bold text-blue-400 hover:text-blue-300 transition-colors bg-blue-500/10 px-3 py-1.5 rounded-lg uppercase tracking-wider">+ Создать</button>
                            </div>

                            <div class="grid grid-cols-1 gap-3">
                                <div v-for="(p, id) in store.presets" :key="id" 
                                     class="group relative bg-white/[0.03] border border-white/5 hover:border-blue-500/30 rounded-2xl p-4 transition-all duration-300 hover:bg-white/[0.06] shadow-sm">
                                    <div class="flex items-center justify-between">
                                        <div class="flex items-center gap-4 min-w-0">
                                            <div class="w-10 h-10 rounded-xl bg-gradient-to-br from-gray-800 to-gray-900 border border-white/5 flex items-center justify-center text-xl shadow-inner group-hover:scale-110 transition-transform">
                                                <i class="ph ph-layout text-blue-400"></i>
                                            </div>
                                            <div class="truncate">
                                                <div class="text-xs font-semibold text-gray-100 truncate mb-0.5">{{ p.name }}</div>
                                                <div v-if="store.defaultPresetId === id" class="text-[8px] text-amber-500 font-bold uppercase tracking-tighter">По умолчанию</div>
                                                <div class="flex gap-1">
                                                    <span class="text-[8px] bg-white/5 px-1.5 py-0.5 rounded text-gray-500 uppercase">{{ p.prompt_ids.length }} систем</span>
                                                    <span class="text-[8px] bg-white/5 px-1.5 py-0.5 rounded text-gray-500 uppercase">{{ p.modes.length }} режимов</span>
                                                </div>
                                            </div>
                                        </div>
                                        <div class="flex items-center gap-2">
                                            <div v-if="store.activePresetId === id" class="w-2 h-2 rounded-full bg-emerald-500 shadow-[0_0_8px_#10b981]"></div>
                                            <button v-if="store.defaultPresetId !== id" @click.stop="setAsDefault(id)" class="p-2 text-gray-500 hover:text-amber-400 hover:bg-white/10 rounded-lg transition-all opacity-0 group-hover:opacity-100" title="Сделать по умолчанию"><i class="ph-bold ph-star"></i></button>
                                            <button @click.stop="selectPresetForEdit(id, p)" class="p-2 text-gray-500 hover:text-white hover:bg-white/10 rounded-lg transition-all opacity-0 group-hover:opacity-100">
                                                <i class="ph-bold ph-pencil-simple"></i>
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <!-- Preset Editor Mode -->
                        <div v-else class="flex-1 flex flex-col p-6 gap-6 animate-fade-in relative h-full">
                            <h2 class="text-sm font-bold text-white uppercase tracking-widest">{{ isCreatingPreset ? 'Новый пресет' : 'Настройка пресета' }}</h2>
                            <div class="flex flex-col flex-1 gap-6 overflow-y-auto custom-scrollbar pr-2 pb-10">
                                <div class="space-y-2">
                                    <label class="text-[10px] font-bold text-gray-500 uppercase tracking-widest px-1">Название пресета</label>
                                    <input v-model="editPresetData.name" class="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 focus:outline-none focus:border-blue-500/50 text-xs text-gray-200">
                                </div>

                                <!-- Prompt Selection -->
                                <div class="space-y-3">
                                    <label class="text-[10px] font-bold text-gray-500 uppercase tracking-widest px-1">Системные промпты (База)</label>
                                    <div class="grid grid-cols-1 gap-2">
                                        <div v-for="(p, id) in getPromptsByType('system')" :key="id"
                                            @click="togglePresetPrompt(id)"
                                            class="p-3 rounded-xl border text-xs transition-all cursor-pointer flex items-center justify-between"
                                            :class="editPresetData.prompt_ids.includes(id) ? 'bg-blue-600/10 border-blue-500/50 text-blue-400' : 'bg-white/5 border-transparent text-gray-500 hover:bg-white/10'">
                                            <div class="flex items-center gap-3">
                                                <i :class="['ph-bold', p.icon || 'ph-app-window']"></i>
                                                <span>{{ p.name }}</span>
                                            </div>
                                            <i v-if="editPresetData.prompt_ids.includes(id)" class="ph-bold ph-check"></i>
                                        </div>
                                    </div>
                                </div>

                                <!-- Modes Selection -->
                                <div class="space-y-3">
                                    <label class="text-[10px] font-bold text-gray-500 uppercase tracking-widest px-1">Разрешенные режимы</label>
                                    <div class="grid grid-cols-2 gap-2">
                                        <div v-for="(p, id) in getPromptsByType('parameter')" :key="id"
                                            @click="togglePresetMode(id)"
                                            class="p-3 rounded-xl border text-[10px] transition-all cursor-pointer flex items-center gap-2"
                                            :class="editPresetData.modes.includes(id) ? 'bg-blue-600/10 border-blue-500/50 text-blue-400' : 'bg-white/5 border-transparent text-gray-500 hover:bg-white/10'">
                                            <i :class="['ph-bold', p.icon || 'ph-app-window']"></i>
                                            <span class="truncate">{{ p.name }}</span>
                                        </div>
                                    </div>
                                </div>

                                
                                <!-- FS Permissions Selection -->
                                <div class="space-y-4">
                                    <label class="text-[10px] font-bold text-gray-500 uppercase tracking-widest px-1">Файловая система (ACL)</label>
                                    <div class="p-4 bg-white/5 rounded-2xl border border-white/5 space-y-4">
                                        <div class="flex items-center justify-between gap-4">
                                            <span class="text-[10px] text-gray-400 font-bold uppercase tracking-tight">Глобальные права:</span>
                                            <input v-model="editPresetData.fs_permissions.global" class="w-24 bg-black/40 border border-white/10 rounded-lg px-2 py-1 text-xs text-blue-400 font-mono text-center focus:border-blue-500/50 outline-none" placeholder="rwxld">
                                        </div>
                                        <div class="space-y-2">
                                            <div v-for="(perms, pth) in editPresetData.fs_permissions.paths" :key="pth" class="flex items-center gap-2 group animate-fade-in">
                                                <div class="flex-1 bg-white/5 border border-white/5 rounded-lg px-3 py-1.5 text-[10px] text-gray-500 font-mono truncate">{{ pth }}</div>
                                                <input v-model="editPresetData.fs_permissions.paths[pth]" class="w-16 bg-black/40 border border-white/10 rounded-lg px-2 py-1.5 text-[10px] text-indigo-400 font-mono text-center focus:border-indigo-500/50 outline-none">
                                                <button @click="delete editPresetData.fs_permissions.paths[pth]" class="p-1.5 text-red-500/40 hover:text-red-400 transition-colors"><i class="ph ph-trash"></i></button>
                                            </div>
                                            <div class="flex gap-2 pt-2">
                                                <input v-model="newPath" @keydown.enter="addPath" placeholder="Путь (н-р: temp/)" class="flex-1 bg-white/5 border border-white/10 rounded-lg px-3 py-1.5 text-[10px] text-gray-300 focus:border-blue-500/50 outline-none">
                                                <button @click="addPath" class="px-4 py-1.5 bg-blue-600/20 text-blue-400 rounded-lg text-[10px] font-bold uppercase hover:bg-blue-600/40 transition-all">Добавить</button>
                                            </div>
                                        </div>
                                        <p class="text-[9px] text-gray-600 italic px-1 leading-tight">Флаги: R (Чтение), W (Запись), X (Запуск), L (Список), D (Удаление). Пути наследуют права от родителей.</p>
                                    </div>
                                </div>

                                
                                <!-- Blocked Tools Selection -->
                                <div class="space-y-3">
                                    <label class="text-[10px] font-bold text-gray-500 uppercase tracking-widest px-1">Заблокированные инструменты</label>
                                    <div class="p-4 bg-red-500/5 rounded-2xl border border-red-500/10 space-y-3">
                                        <div class="flex flex-wrap gap-2">
                                            <div v-for="t in store.allTools" :key="t.name"
                                                @click="togglePresetBlockedTool(t.name)"
                                                class="px-3 py-1.5 rounded-lg border text-[10px] transition-all cursor-pointer flex items-center gap-2"
                                                :class="editPresetData.blocked.includes(t.name) ? 'bg-red-500/20 border-red-500/40 text-red-400' : 'bg-white/5 border-transparent text-gray-500 hover:bg-white/10'">
                                                <i class="ph ph-prohibit"></i>
                                                <span class="truncate">{{ t.name }}</span>
                                            </div>
                                        </div>
                                        <p class="text-[9px] text-gray-600 italic px-1 leading-tight">Инструменты, выбранные здесь, будут физически недоступны агенту при использовании этого пресета.</p>
                                    </div>
                                </div>

                                <!-- Commands Selection -->
                                <div class="space-y-3">
                                    <label class="text-[10px] font-bold text-gray-500 uppercase tracking-widest px-1">Доступные команды</label>
                                    <div class="grid grid-cols-2 gap-2">
                                        <div v-for="(p, id) in getPromptsByType('command')" :key="id"
                                            @click="togglePresetCommand(id)"
                                            class="p-3 rounded-xl border text-[10px] transition-all cursor-pointer flex items-center gap-2"
                                            :class="editPresetData.commands.includes(id) ? 'bg-blue-600/10 border-blue-500/50 text-blue-400' : 'bg-white/5 border-transparent text-gray-500 hover:bg-white/10'">
                                            <i :class="['ph-bold', p.icon || 'ph-app-window']"></i>
                                            <span class="truncate">{{ p.name }}</span>
                                        </div>
                                    </div>
                                </div>
                            </div>
                            <div class="flex justify-between items-center py-4 border-t border-white/10 mt-auto">
                                <button v-if="editPresetId && editPresetId !== 'default'" @click="deletePreset(editPresetId)" class="p-3 text-red-500/60 hover:text-red-400 hover:bg-red-500/10 rounded-xl transition-all"><i class="ph-bold ph-trash text-lg"></i></button>
                                <div v-else></div>
                                <div class="flex gap-3">
                                    <button @click="savePreset" class="px-10 py-3 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-[10px] font-bold uppercase shadow-xl shadow-blue-600/30 transition-all">Сохранить пресет</button>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `,
    setup() {
        const activeTab = ref('prompts');
        const editPromptId = ref(null);
        const editPromptData = ref({name: '', text: '', type: 'system', icon: 'ph-app-window', gather_script: '', exec_script: '', fs_permissions: {global: 'rwxld', paths: {}}});
        const isCreating = ref(false);
        const isExpanded = ref(false);
        const isIconPickerOpen = ref(false);
        const newPath = ref('');
        const addPath = () => { 
            if(!newPath.value) return;
            const target = (activeTab.value === 'prompts') ? editPromptData.value : editPresetData.value;
            if(!target.fs_permissions) target.fs_permissions = {global: '', paths: {}};
            target.fs_permissions.paths[newPath.value] = 'rl'; 
            newPath.value = ''; 
        };

        const editPresetId = ref(null);
        const editPresetData = ref({name: '', prompt_ids: [], modes: [], commands: [], blocked: [], settings: {}});
        const isCreatingPreset = ref(false);

        const commonIcons = ['ph-robot', 'ph-strategy', 'ph-test-tube', 'ph-code', 'ph-bug', 'ph-terminal', 'ph-lightning', 'ph-sparkle', 'ph-brain', 'ph-wrench', 'ph-shield', 'ph-globe', 'ph-gear', 'ph-file-code', 'ph-magic-wand', 'ph-cpu'];

        const refresh = async () => {
            const config = await api.fetchFinalPrompts();
            store.finalPrompts = config.prompts || {};
            store.activePromptId = config.active_id;
            store.active_parameters = config.active_parameters || [];
            store.presets = config.presets || {};
            store.defaultPresetId = config.default_preset_id || 'default'; const tools = await api.fetchTools(); if(Array.isArray(tools)) store.allTools = tools;
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
                name: p.name, text: p.text, type: p.type || 'system', 
                icon: p.icon || 'ph-app-window', gather_script: p.gather_script || '', exec_script: p.exec_script || '',
                fs_permissions: p.fs_permissions || {global: 'rwxld', paths: {}}
            };
        };

        const createNewPrompt = () => {
            editPromptId.value = null;
            isCreating.value = true;
            editPromptData.value = {
                name: 'Новый промпт', text: '', type: 'system', icon: 'ph-robot', gather_script: '', exec_script: '',
                fs_permissions: {global: 'rwxld', paths: {}}
            };
        };

        const selectIcon = (icon) => {
            editPromptData.value.icon = icon;
            isIconPickerOpen.value = false;
        };

        const savePrompt = async () => {
            const res = await api.saveFinalPrompt(editPromptId.value, editPromptData.value.name, editPromptData.value.text, editPromptData.value.type, editPromptData.value.icon, editPromptData.value.gather_script, false, editPromptData.value.fs_permissions, editPromptData.value.exec_script);
            if (res.status === 'ok') {
                store.addToast('Сохранено', 'success');
                await refresh();
                closeEditor();
            }
        };

        const setActivePrompt = async (id) => {
            const res = await api.selectFinalPrompt(id);
            if (res.status === 'ok') { store.activePromptId = id; store.addToast('Активный промпт изменен', 'success'); }
        };

        const deletePrompt = async (id) => {
            if (confirm('Удалить этот промпт?')) {
                const res = await api.deleteFinalPrompt(id);
                if (res.status === 'deleted') { await refresh(); closeEditor(); store.addToast('Удалено', 'info'); }
            }
        };

        const closeEditor = () => {
            editPromptId.value = null; editPresetId.value = null;
            isCreating.value = false; isCreatingPreset.value = false;
            isExpanded.value = false; isIconPickerOpen.value = false;
        };

        const createNewPreset = () => {
            editPresetId.value = null; isCreatingPreset.value = true;
            editPresetData.value = {name: 'Новый пресет', prompt_ids: ['default'], modes: [], commands: [], blocked: [], settings: {}, fs_permissions: {global: 'rwxld', paths: {}}};
        };

        const selectPresetForEdit = (id, p) => {
            editPresetId.value = id; isCreatingPreset.value = false;
            editPresetData.value = JSON.parse(JSON.stringify(p));
            const d = editPresetData.value;
            if(!d.fs_permissions) d.fs_permissions = {global: 'rwxld', paths: {}};
            if(!d.blocked) d.blocked = [];
            if(!d.modes) d.modes = [];
            if(!d.commands) d.commands = [];
            if(!d.prompt_ids) d.prompt_ids = [];
        };

        const togglePresetPrompt = (id) => {
            const idx = editPresetData.value.prompt_ids.indexOf(id);
            if (idx > -1) editPresetData.value.prompt_ids.splice(idx, 1);
            else editPresetData.value.prompt_ids.push(id);
        };
        const togglePresetMode = (id) => {
            const idx = editPresetData.value.modes.indexOf(id);
            if (idx > -1) editPresetData.value.modes.splice(idx, 1);
            else editPresetData.value.modes.push(id);
        };
                const togglePresetBlockedTool = (name) => {
            const idx = editPresetData.value.blocked.indexOf(name);
            if (idx > -1) editPresetData.value.blocked.splice(idx, 1);
            else editPresetData.value.blocked.push(name);
        };
        const togglePresetCommand = (id) => {
            const idx = editPresetData.value.commands.indexOf(id);
            if (idx > -1) editPresetData.value.commands.splice(idx, 1);
            else editPresetData.value.commands.push(id);
        };

        const savePreset = async () => {
            const d = editPresetData.value;
            const res = await api.savePreset(editPresetId.value, d.name, d.prompt_ids, d.modes, d.commands, d.blocked, d.settings, d.fs_permissions);
            if (res.status === 'ok') {
                store.addToast('Пресет сохранен', 'success');
                await refresh();
                closeEditor();
            }
        };

        const deletePreset = async (id) => {
            if (confirm('Удалить этот пресет?')) {
                const res = await api.deletePreset(id);
                if (res.status === 'deleted') { await refresh(); closeEditor(); store.addToast('Пресет удален', 'info'); }
            }
        };

        const setAsDefault = async (id) => {
            const res = await api.setDefaultPreset(id);
            if (res.status === 'ok') {
                store.defaultPresetId = id;
                store.addToast('Пресет по умолчанию изменен', 'success');
            }
        };

        onMounted(refresh);
        watch(() => store.isPromptPanelOpen, (val) => { if(val) refresh(); });

                return { 
            store, activeTab, editPromptId, editPromptData, isCreating, isExpanded, isIconPickerOpen, commonIcons, 
            createNewPrompt, selectIcon, savePrompt, setActivePrompt, deletePrompt, selectForEdit, closeEditor, 
            getPromptsByType, getTypeName, getTypeIcon,
            editPresetId, editPresetData, isCreatingPreset, createNewPreset, selectPresetForEdit,
            togglePresetPrompt, togglePresetMode, togglePresetCommand, togglePresetBlockedTool, savePreset, deletePreset, setAsDefault,
            newPath, addPath
        };
    }
}