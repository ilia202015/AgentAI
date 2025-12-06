import { store } from '../store.js';
import * as api from '../api.js';
import { nextTick, ref, watch, onMounted, computed, defineComponent } from 'vue';

// --- Configure Marked (Minimal) ---
if (typeof marked !== 'undefined') {
    marked.setOptions({
        highlight: null,
        langPrefix: 'language-' 
    });
}

// --- Sub-component ---
const MessageBubble = defineComponent({
    props: ['msg'],
    template: `
        <div ref="root" class="group flex flex-col max-w-3xl mx-auto w-full animate-fade-in-up"
            :class="msg.role === 'user' ? 'items-end' : 'items-start'">
            
            <!-- Role Label -->
            <div class="flex items-center gap-2 mb-1.5 px-1 opacity-60 text-xs font-medium tracking-wide">
                <span v-if="msg.role === 'assistant'" class="flex items-center gap-1.5 text-blue-400">
                        <i class="ph-fill ph-robot"></i> Агент
                </span>
                <span v-else class="text-gray-400">Вы</span>
            </div>

            <!-- Pre-content: Thoughts only -->
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

            <!-- Main Bubble -->
            <div class="relative max-w-full overflow-hidden transition-all shadow-lg"
                    :class="[
                    msg.role === 'user' 
                        ? 'bg-gradient-to-br from-blue-600 to-indigo-600 text-white rounded-2xl rounded-tr-sm px-5 py-3.5 border border-white/10' 
                        : 'bg-gray-800/40 backdrop-blur-md border border-white/5 text-gray-100 rounded-2xl rounded-tl-sm px-6 py-5 w-full'
                    ]">
                    
                    <div class="prose prose-invert prose-sm break-words leading-relaxed" 
                        :class="msg.role === 'user' ? 'text-white/95' : ''"
                        v-html="renderedContent"></div>
                    
                    <div v-if="msg.role === 'assistant'" class="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity flex gap-1">
                    <button @click="copyToClipboard(msg.content)" class="p-1.5 text-gray-500 hover:text-white hover:bg-white/10 rounded transition" title="Копировать">
                        <i class="ph ph-copy"></i>
                    </button>
                    </div>
            </div>

            <!-- Post-content: Tools (Collapsible) -->
            <div v-if="msg.role === 'assistant' && msg.tools && msg.tools.length > 0" class="w-full mt-2">
                <details class="group/tools">
                    <summary class="list-none cursor-pointer flex items-center gap-2 text-xs text-gray-500 hover:text-gray-300 transition-colors py-1 select-none">
                        <i class="ph ph-wrench text-emerald-500 group-open/tools:rotate-180 transition-transform"></i>
                        <span>Использованные инструменты ({{ msg.tools.length }})</span>
                        <span class="opacity-50 text-[10px] ml-auto">Развернуть</span>
                    </summary>
                    
                    <div class="space-y-2 mt-2 pt-2 border-t border-white/5">
                        <div v-for="(tool, tIdx) in msg.tools" :key="tIdx" 
                                class="rounded-lg border border-white/5 bg-gray-900 overflow-hidden">
                            <div class="px-3 py-2 bg-white/5 flex items-center justify-between text-xs text-gray-300 font-mono border-b border-white/5">
                                <div class="flex items-center gap-2">
                                    <i class="ph ph-terminal-window text-emerald-400"></i>
                                    <span>{{ tool.title }}</span>
                                </div>
                            </div>
                            <div class="p-0 overflow-x-auto bg-[#282c34]">
                                <!-- Manual highlight call for tools -->
                                <pre class="text-xs font-mono m-0 p-3 whitespace-pre-wrap" 
                                        v-html="manualHighlight(tool.content, tool.title)"></pre>
                            </div>
                        </div>
                    </div>
                </details>
            </div>

        </div>
    `,
    setup(props) {
        const root = ref(null);

        const renderedContent = computed(() => {
            if (!props.msg.content) return '';
            try { 
                return marked.parse(props.msg.content); 
            } catch (e) { return props.msg.content; }
        });

        const manualHighlight = (code, lang) => {
            if (typeof window.hljs === 'undefined') return code;
            try {
                if (lang) {
                    const cleanLang = lang.split(':')[0].split(' ')[0].toLowerCase();
                    if (window.hljs.getLanguage(cleanLang)) {
                        return window.hljs.highlight(code, { language: cleanLang }).value;
                    }
                }
                return window.hljs.highlightAuto(code).value;
            } catch (e) { return code; }
        };

        const highlightBlock = () => {
            if (!root.value || typeof window.hljs === 'undefined') return;
            root.value.querySelectorAll('pre code').forEach((block) => {
                if (!block.dataset.highlighted) {
                    window.hljs.highlightElement(block);
                    block.dataset.highlighted = "yes";
                }
            });
        };

        onMounted(highlightBlock);
        
        watch(renderedContent, async () => {
            await nextTick();
            highlightBlock();
        });

        const copyToClipboard = (text) => navigator.clipboard.writeText(text);

        return { renderedContent, manualHighlight, copyToClipboard, root };
    }
});

export default {
    components: { MessageBubble },
    template: `
        <div class="flex-1 flex flex-col h-full relative z-10">
            <div class="flex-1 overflow-y-auto px-4 sm:px-8 py-6 space-y-8 scroll-smooth custom-scrollbar" ref="messagesContainer">
                <div v-if="filteredMessages.length === 0" class="h-full flex flex-col items-center justify-center text-center opacity-0 animate-fade-in-up" style="animation-delay: 0.1s; opacity: 1">
                    <div class="w-16 h-16 rounded-2xl bg-gradient-to-tr from-gray-800 to-gray-700 flex items-center justify-center mb-6 shadow-2xl border border-white/5">
                        <i class="ph-duotone ph-sparkle text-3xl text-blue-400"></i>
                    </div>
                    <h2 class="text-2xl font-bold text-white mb-2 tracking-tight">Чем я могу помочь?</h2>
                    <p class="text-gray-500 max-w-md text-sm leading-relaxed">Я могу писать код, анализировать данные и помогать с творческими задачами.</p>
                </div>
                
                <MessageBubble v-for="(msg, idx) in filteredMessages" :key="idx" :msg="msg" />

                <div v-if="store.isThinking" class="max-w-3xl mx-auto w-full py-2">
                   <div class="flex items-center gap-3 px-4">
                       <div class="w-6 h-6 rounded-full bg-blue-500/10 flex items-center justify-center">
                            <i class="ph-duotone ph-spinner animate-spin text-blue-500 text-xs"></i>
                       </div>
                       <span class="text-xs text-blue-400/80 font-medium animate-pulse">Думаю...</span>
                   </div>
                </div>
                <div class="h-24"></div>
            </div>

            <div class="absolute bottom-0 left-0 w-full p-4 sm:p-6 bg-gradient-to-t from-gray-950 via-gray-950/90 to-transparent z-50">
                <div class="max-w-3xl mx-auto relative group">
                    <div class="absolute inset-0 bg-gradient-to-r from-blue-500/20 to-purple-500/20 rounded-xl blur-lg opacity-0 group-focus-within:opacity-100 transition-opacity duration-500"></div>
                    <div class="relative bg-gray-900/80 backdrop-blur-xl border border-white/10 rounded-xl shadow-2xl overflow-hidden flex flex-col transition-all group-focus-within:border-blue-500/30 group-focus-within:bg-gray-900/90">
                        <textarea v-model="inputText" @keydown.enter.exact.prevent="send" placeholder="Отправить сообщение..." rows="1" ref="textarea" @input="resizeTextarea" class="w-full bg-transparent text-gray-100 px-4 py-4 focus:outline-none resize-none max-h-48 overflow-y-auto placeholder-gray-500 text-sm leading-relaxed"></textarea>
                        <div class="flex justify-between items-center px-2 pb-2">
                            <div class="flex gap-1 px-2"></div>
                            <button v-if="store.isThinking" @click="stop" class="p-2 rounded-lg bg-red-500/10 text-red-500 hover:bg-red-500/20 transition-all duration-200 flex items-center justify-center gap-2 border border-red-500/20" title="Остановить генерацию"><i class="ph-fill ph-stop text-lg"></i></button>
                            <button v-else @click="send" :disabled="!inputText.trim()" class="p-2 rounded-lg transition-all duration-200 flex items-center justify-center gap-2" :class="inputText.trim() ? 'bg-blue-600 text-white shadow-lg shadow-blue-500/25 hover:bg-blue-500' : 'bg-white/5 text-gray-600 cursor-not-allowed'"><i class="ph-fill ph-paper-plane-right text-lg"></i></button>
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
        const filteredMessages = computed(() => store.messages.filter(m => m.role !== 'system' && m.role !== 'tool'));
        
        const scrollToBottom = async () => { await nextTick(); if (messagesContainer.value) messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight; };
        const resizeTextarea = () => { if (textarea.value) { textarea.value.style.height = 'auto'; textarea.value.style.height = Math.min(textarea.value.scrollHeight, 200) + 'px'; }};
        
        watch(() => store.messages.length, scrollToBottom);
        watch(() => store.messages[store.messages.length - 1]?.content, scrollToBottom);
        watch(() => store.messages[store.messages.length - 1]?.thoughts, scrollToBottom);

        const send = async () => {
            if (!inputText.value.trim()) return;
            const text = inputText.value; inputText.value = ''; 
            if (textarea.value) textarea.value.style.height = 'auto';
            store.messages.push({ role: 'user', content: text });
            store.isThinking = true;
            await scrollToBottom();
            try { await api.sendMessage(text); } catch (e) { store.isThinking = false; }
        };
        const stop = async () => { await api.stopGeneration(); store.isThinking = false; };

        onMounted(() => scrollToBottom());

        return { store, inputText, send, stop, filteredMessages, messagesContainer, textarea, resizeTextarea };
    }
}
