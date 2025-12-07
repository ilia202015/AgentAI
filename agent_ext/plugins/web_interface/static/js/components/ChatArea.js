import { store } from '../store.js';
import * as api from '../api.js';
import { nextTick, ref, watch, onMounted, computed, defineComponent } from 'vue';

// --- Global Configuration for Marked ---
let isMarkedConfigured = false;
function ensureMarkedConfig() {
    if (typeof marked === 'undefined' || isMarkedConfigured) return;
    marked.setOptions({ highlight: null, langPrefix: 'language-' });
    isMarkedConfigured = true;
}

// --- Message Component ---
const MessageBubble = defineComponent({
    props: ['msg', 'index'],
    emits: ['edit'],
    template: `
        <div ref="root" class="group flex flex-col w-[95%] mx-auto animate-fade-in-up"
            :class="msg.role === 'user' ? 'items-end' : 'items-start'">
            
            <div class="flex items-center gap-2 mb-1.5 px-1 opacity-60 text-xs font-medium tracking-wide">
                <span v-if="msg.role === 'assistant'" class="flex items-center gap-1.5 text-blue-400">
                        <i class="ph-fill ph-robot"></i> Агент
                </span>
                <span v-else class="text-gray-400 flex items-center gap-2">
                    <span>Вы</span>
                    <button @click="startEdit" v-if="!isEditing" class="opacity-0 group-hover:opacity-100 transition-opacity hover:text-white" title="Редактировать"><i class="ph-bold ph-pencil-simple"></i></button>
                </span>
            </div>

            <!-- Assistant: Thoughts (Classic Style) -->
            <div v-if="msg.role === 'assistant'" class="w-full mb-2 space-y-2">
                <details v-if="msg.thoughts" class="group/thought">
                    <summary class="list-none cursor-pointer flex items-center gap-2 text-xs text-gray-500 hover:text-gray-300 transition-colors py-1 select-none">
                        <i class="ph ph-brain text-purple-400 group-open/thought:rotate-180 transition-transform"></i>
                        <span>Процесс мышления</span>
                        <span class="opacity-50 text-[10px] ml-auto">Развернуть</span>
                    </summary>
                    <div class="mt-2 pl-3 border-l-2 border-purple-500/20 text-gray-400 text-xs leading-relaxed whitespace-pre-wrap font-mono bg-black/20 p-3 rounded-r-lg">
                        {{ msg.thoughts }}
                    </div>
                </details>
            </div>

            <!-- Main Bubble / Edit Mode -->
            <div class="relative max-w-full overflow-hidden transition-all shadow-lg w-full"
                    :class="[
                    msg.role === 'user' 
                        ? (isEditing ? 'w-full' : 'bg-gradient-to-br from-blue-600 to-indigo-600 text-white rounded-2xl rounded-tr-sm px-5 py-3.5 border border-white/10 w-auto')
                        : 'bg-gray-800/40 backdrop-blur-md border border-white/5 text-gray-100 rounded-2xl rounded-tl-sm px-6 py-5'
                    ]">
                    
                    <div v-if="isEditing" class="w-full bg-gray-900 border border-white/10 rounded-xl p-3">
                        <textarea v-model="editContent" rows="3" class="w-full bg-transparent text-sm focus:outline-none resize-none mb-2"></textarea>
                        <div class="flex justify-end gap-2">
                            <button @click="cancelEdit" class="px-3 py-1.5 rounded text-xs hover:bg-white/5 text-gray-400">Отмена</button>
                            <button @click="saveEdit" class="px-3 py-1.5 rounded bg-blue-600 text-white text-xs hover:bg-blue-500">Сохранить</button>
                        </div>
                    </div>

                    <div v-else>
                        <div class="prose prose-invert prose-sm break-words leading-relaxed max-w-none" 
                            :class="msg.role === 'user' ? 'text-white/95' : ''"
                            v-html="renderedContent"></div>
                        <div v-if="msg.role === 'assistant'" class="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity flex gap-1">
                            <button @click="copyToClipboard(msg.content)" class="p-1.5 text-gray-500 hover:text-white hover:bg-white/10 rounded transition" title="Копировать"><i class="ph ph-copy"></i></button>
                        </div>
                    </div>
            </div>

            <!-- Assistant: Tools -->
            <div v-if="msg.role === 'assistant' && msg.tools && msg.tools.length > 0" class="w-full mt-2">
                <details class="group/tools">
                    <summary class="list-none cursor-pointer flex items-center gap-2 text-xs text-gray-500 hover:text-gray-300 transition-colors py-1 select-none">
                        <i class="ph ph-wrench text-emerald-500 group-open/tools:rotate-180 transition-transform"></i>
                        <span>Использованные инструменты ({{ Math.ceil(msg.tools.length / 2) }})</span>
                        <span class="opacity-50 text-[10px] ml-auto">Развернуть</span>
                    </summary>
                    <div class="space-y-2 mt-2 pt-2 border-t border-white/5">
                        <div v-for="(tool, tIdx) in msg.tools" :key="tIdx" class="code-block-wrapper rounded-lg border border-white/5 bg-gray-900 overflow-hidden relative group/code">
                            <div class="px-3 py-1.5 bg-white/5 flex items-center justify-between text-xs text-gray-300 font-mono border-b border-white/5">
                                <div class="flex items-center gap-2"><i class="ph ph-terminal-window text-emerald-400"></i><span>{{ tool.title }}</span></div>
                                <button onclick="window.copyCode(this)" class="flex items-center gap-1.5 text-[10px] text-gray-500 hover:text-white transition-colors cursor-pointer opacity-0 group-hover/code:opacity-100"><i class="ph ph-copy"></i><span>Копировать</span></button>
                            </div>
                            <div class="p-0 overflow-x-auto bg-[#282c34]"><pre class="text-xs font-mono m-0 p-3 whitespace-pre-wrap"><code class="hljs" style="background: transparent; padding: 0;">{{ tool.content }}</code></pre></div>
                        </div>
                    </div>
                </details>
            </div>
        </div>
    `,
    setup(props, { emit }) {
        const root = ref(null);
        const isEditing = ref(false);
        const editContent = ref('');
        ensureMarkedConfig();

        const renderedContent = computed(() => {
            if (!props.msg.content) return '';
            try { return marked.parse(props.msg.content); } catch (e) { return props.msg.content; }
        });

        const processContent = () => {
            if (!root.value) return;
            const blocks = root.value.querySelectorAll('pre code:not([data-highlighted])');
            blocks.forEach((block) => {
                if (typeof window.hljs !== 'undefined') { window.hljs.highlightElement(block); block.setAttribute('data-highlighted', 'yes'); }
            });
            if (typeof renderMathInElement !== 'undefined') {
                renderMathInElement(root.value, {
                    delimiters: [ {left: '$$', right: '$$', display: true}, {left: '$', right: '$', display: false}, {left: '\\(', right: '\\)', display: false}, {left: '\\[', right: '\\]', display: true} ],
                    throwOnError: false
                });
            }
            const preElements = root.value.querySelectorAll('.prose pre:not(.processed)');
            preElements.forEach(pre => {
                const code = pre.querySelector('code');
                let lang = 'plaintext';
                if (code) { code.classList.forEach(cls => { if (cls.startsWith('language-')) lang = cls.replace('language-', ''); }); }
                const wrapper = document.createElement('div');
                wrapper.className = 'code-block-wrapper my-4 rounded-lg border border-white/10 bg-[#282c34] overflow-hidden relative group/code';
                const header = document.createElement('div');
                header.className = 'flex items-center justify-between px-3 py-1.5 bg-white/5 border-b border-white/5';
                header.innerHTML = `<span class="text-xs font-mono text-gray-400">${lang}</span><button onclick="window.copyCode(this)" class="flex items-center gap-1.5 text-[10px] text-gray-500 hover:text-white transition-colors cursor-pointer z-10 opacity-0 group-hover/code:opacity-100"><i class="ph ph-copy"></i><span>Копировать</span></button>`;
                pre.parentNode.insertBefore(wrapper, pre);
                const contentDiv = document.createElement('div');
                contentDiv.className = 'overflow-x-auto p-3';
                contentDiv.appendChild(pre);
                wrapper.appendChild(header);
                wrapper.appendChild(contentDiv);
                pre.classList.add('processed');
            });
        };

        watch(renderedContent, async () => { await nextTick(); processContent(); });
        onMounted(async () => { await nextTick(); processContent(); });
        watch(() => props.msg.tools, async () => { await nextTick(); processContent(); }, { deep: true });

        const startEdit = () => { editContent.value = props.msg.content; isEditing.value = true; };
        const cancelEdit = () => { isEditing.value = false; };
        const saveEdit = () => { if (editContent.value.trim() !== props.msg.content) { emit('edit', props.index, editContent.value); } isEditing.value = false; };
        const copyToClipboard = (text) => { navigator.clipboard.writeText(text); store.addToast("Текст скопирован", "success"); };

        return { renderedContent, copyToClipboard, root, isEditing, editContent, startEdit, cancelEdit, saveEdit };
    }
});

// --- Main Component ---
export default {
    components: { MessageBubble },
    template: `
        <div class="flex-1 flex flex-col h-full relative z-10 min-w-0">
            
            <!-- Desktop Sidebar Toggle -->
            <div class="hidden md:block absolute top-4 left-2 z-50">
                <button @click="store.toggleSidebarDesktop()" class="p-2 rounded-lg bg-gray-900/50 backdrop-blur border border-white/10 text-gray-400 hover:text-white transition-colors shadow-sm">
                    <i class="ph-bold" :class="store.isSidebarVisibleDesktop ? 'ph-caret-left' : 'ph-caret-right'"></i>
                </button>
            </div>

            <!-- Mobile Sidebar Toggle -->
            <div class="md:hidden absolute top-4 left-4 z-50">
                <button @click="store.toggleSidebarMobile()" class="p-2 rounded-lg bg-gray-900/80 backdrop-blur border border-white/10 text-gray-300">
                    <i class="ph-bold ph-list"></i>
                </button>
            </div>
            
            <!-- Scroll Button -->
            <div class="absolute bottom-32 right-8 z-40 transition-all duration-300"
                 :class="showScrollButton ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-4 pointer-events-none'">
                <button @click="scrollToBottom(true)" 
                    class="w-10 h-10 rounded-full bg-gray-800 border border-white/10 shadow-xl flex items-center justify-center text-gray-400 hover:text-white hover:bg-gray-700 transition-colors cursor-pointer">
                    <i class="ph-bold ph-arrow-down"></i>
                </button>
            </div>

            <!-- Messages Area -->
            <div class="flex-1 overflow-y-auto px-2 md:px-0 pt-16 md:pt-6 pb-48 space-y-8 scroll-smooth custom-scrollbar" 
                 ref="messagesContainer"
                 @scroll="handleScroll">
                
                <div v-if="filteredMessages.length === 0" class="h-full flex flex-col items-center justify-center text-center opacity-0 animate-fade-in-up" style="animation-delay: 0.1s; opacity: 1">
                    <div class="w-16 h-16 rounded-2xl bg-gradient-to-tr from-gray-800 to-gray-700 flex items-center justify-center mb-6 shadow-2xl border border-white/5">
                        <i class="ph-duotone ph-sparkle text-3xl text-blue-400"></i>
                    </div>
                    <h2 class="text-2xl font-bold text-white mb-2 tracking-tight">Чем я могу помочь?</h2>
                    <p class="text-gray-500 max-w-md text-sm leading-relaxed">Я могу писать код, анализировать данные и помогать с творческими задачами.</p>
                </div>
                
                <MessageBubble 
                    v-for="(msg, idx) in filteredMessages" 
                    :key="idx" 
                    :index="idx"
                    :msg="msg" 
                    @edit="handleEdit"
                />

                <div v-if="store.isThinking" class="w-[95%] mx-auto w-full py-2">
                   <div class="flex items-center gap-3 px-4">
                       <div class="w-6 h-6 rounded-full bg-blue-500/10 flex items-center justify-center">
                            <i class="ph-duotone ph-spinner animate-spin text-blue-500 text-xs"></i>
                       </div>
                       <span class="text-xs text-blue-400/80 font-medium animate-pulse">Думаю...</span>
                   </div>
                </div>
            </div>

            <!-- Input Area -->
            <div class="absolute bottom-0 left-0 w-full pb-6 pt-12 bg-gradient-to-t from-gray-950 via-gray-950/90 to-transparent z-20 pointer-events-none">
                <div class="w-[95%] mx-auto relative group pointer-events-auto">
                    <div class="absolute inset-0 bg-gradient-to-r from-blue-500/20 to-purple-500/20 rounded-xl blur-lg opacity-0 group-focus-within:opacity-100 transition-opacity duration-500"></div>
                    <div class="relative bg-gray-900/80 backdrop-blur-xl border border-white/10 rounded-xl shadow-2xl overflow-hidden flex flex-col transition-all group-focus-within:border-blue-500/30 group-focus-within:bg-gray-900/90">
                        <div v-if="editingIndex !== null" class="bg-blue-500/10 border-b border-white/5 px-4 py-1 text-xs text-blue-300 flex justify-between items-center">
                            <span>Редактирование сообщения...</span>
                            <button @click="cancelEdit" class="hover:text-white"><i class="ph-bold ph-x"></i></button>
                        </div>

                        <textarea 
                            v-model="inputText" 
                            @keydown.enter.exact.prevent="send" 
                            :placeholder="editingIndex !== null ? 'Измените сообщение...' : 'Отправить сообщение...'"
                            rows="1" ref="textarea" @input="resizeTextarea" 
                            class="w-full bg-transparent text-gray-100 px-4 py-4 focus:outline-none resize-none max-h-48 overflow-y-auto placeholder-gray-500 text-sm leading-relaxed"
                        ></textarea>
                        
                        <div class="flex justify-between items-center px-2 pb-2">
                            <div class="flex gap-1 px-2"></div>
                            <button v-if="store.isThinking" @click="stop" class="p-2 rounded-lg bg-red-500/10 text-red-500 hover:bg-red-500/20 transition-all duration-200 flex items-center justify-center gap-2 border border-red-500/20" title="Остановить генерацию"><i class="ph-fill ph-stop text-lg"></i></button>
                            <button v-else @click="send" :disabled="!inputText.trim()" 
                                class="p-2 rounded-lg transition-all duration-200 flex items-center justify-center gap-2" 
                                :class="inputText.trim() ? 'bg-blue-600 text-white shadow-lg shadow-blue-500/25 hover:bg-blue-500' : 'bg-white/5 text-gray-600 cursor-not-allowed'">
                                <i :class="editingIndex !== null ? 'ph-fill ph-check' : 'ph-fill ph-paper-plane-right'" class="text-lg"></i>
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `,
    setup() {
        const inputText = ref('');
        const messagesContainer = ref(null);
        const textarea = ref(null);
        const showScrollButton = ref(false);
        const editingIndex = ref(null);
        const filteredMessages = computed(() => store.messages.filter(m => m.role !== 'system' && m.role !== 'tool'));
        
        const scrollToBottom = async (force = false) => { 
            await nextTick(); 
            if (messagesContainer.value) {
                const { scrollTop, scrollHeight, clientHeight } = messagesContainer.value;
                if (force || (scrollHeight - scrollTop - clientHeight) < 250) {
                    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight;
                }
            }
        };
        
        const resizeTextarea = () => { if (textarea.value) { textarea.value.style.height = 'auto'; textarea.value.style.height = Math.min(textarea.value.scrollHeight, 200) + 'px'; }};
        
        const handleScroll = () => {
            if (!messagesContainer.value) return;
            const { scrollTop, scrollHeight, clientHeight } = messagesContainer.value;
            showScrollButton.value = (scrollHeight - scrollTop - clientHeight) > 300;
        };

        watch(() => store.messages.length, async () => { await scrollToBottom(true); });
        watch(() => store.messages[store.messages.length - 1]?.content, () => scrollToBottom());
        
        const handleEdit = async (index, newText) => {
            store.isThinking = true;
            try {
                await api.editMessage(index, newText);
                store.addToast("Сообщение обновлено", "success");
            } catch (e) {
                store.isThinking = false;
                store.addToast("Ошибка редактирования", "error");
            }
        };

        const startEditing = (idx, content) => {
            editingIndex.value = idx;
            inputText.value = content;
            if (textarea.value) { textarea.value.focus(); resizeTextarea(); }
        };

        const cancelEdit = () => { editingIndex.value = null; inputText.value = ''; resizeTextarea(); };

        const send = async () => {
            if (!inputText.value.trim()) return;
            const text = inputText.value; 
            if (textarea.value) textarea.value.style.height = 'auto';
            store.isThinking = true;

            if (editingIndex.value !== null) {
                const idx = editingIndex.value;
                inputText.value = '';
                editingIndex.value = null;
                handleEdit(idx, text);
            } else {
                inputText.value = '';
                store.messages.push({ role: 'user', content: text });
                await scrollToBottom(true);
                try { await api.sendMessage(text); } 
                catch (e) { store.isThinking = false; store.addToast("Ошибка отправки", "error"); }
            }
        };
        const stop = async () => { await api.stopGeneration(); store.isThinking = false; store.addToast("Генерация остановлена", "info"); };

        onMounted(() => scrollToBottom(true));

        return { store, inputText, send, stop, filteredMessages, messagesContainer, textarea, resizeTextarea, showScrollButton, scrollToBottom, handleScroll, handleEdit, startEditing, editingIndex, cancelEdit };
    }
}
