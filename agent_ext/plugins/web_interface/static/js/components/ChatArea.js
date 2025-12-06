import { store } from '../store.js';
import * as api from '../api.js';
import { nextTick, ref, watch, onMounted, computed, defineComponent } from 'vue';

// --- Global Configuration for Marked ---
if (typeof marked !== 'undefined') {
    const renderer = new marked.Renderer();
    
    renderer.code = function(code, language) {
        let validLang = 'plaintext';
        let highlighted = code;

        if (typeof window.hljs !== 'undefined') {
            if (language) {
                const cleanLang = language.split(':')[0].split(' ')[0].toLowerCase();
                if (window.hljs.getLanguage(cleanLang)) {
                    validLang = cleanLang;
                    try {
                        highlighted = window.hljs.highlight(code, { language: validLang }).value;
                    } catch (e) {}
                }
            }
            // Auto-detect fallback
            if (validLang === 'plaintext') {
                try {
                    const res = window.hljs.highlightAuto(code);
                    highlighted = res.value;
                    validLang = res.language || 'plaintext';
                } catch (e) {}
            }
        }

        // Return HTML string (NOT DOM Element)
        return `<div class="code-block-wrapper my-4 rounded-lg border border-white/10 bg-[#282c34] overflow-hidden relative">
                    <div class="flex items-center justify-between px-3 py-1.5 bg-white/5 border-b border-white/5">
                        <span class="text-xs font-mono text-gray-400">${validLang}</span>
                        <button onclick="window.copyCode(this)" class="flex items-center gap-1.5 text-[10px] text-gray-500 hover:text-white transition-colors cursor-pointer z-10">
                            <i class="ph ph-copy"></i>
                            <span>Копировать</span>
                        </button>
                    </div>
                    <div class="overflow-x-auto p-3">
                        <pre><code class="hljs language-${validLang}" style="background: transparent; padding: 0;">${highlighted}</code></pre>
                    </div>
                </div>`;
    };

    marked.setOptions({ renderer });
}

// --- Message Component ---
const MessageBubble = defineComponent({
    props: ['msg'],
    template: `
        <div class="group flex flex-col max-w-3xl mx-auto w-full animate-fade-in-up"
            :class="msg.role === 'user' ? 'items-end' : 'items-start'">
            
            <div class="flex items-center gap-2 mb-1.5 px-1 opacity-60 text-xs font-medium tracking-wide">
                <span v-if="msg.role === 'assistant'" class="flex items-center gap-1.5 text-blue-400">
                        <i class="ph-fill ph-robot"></i> Агент
                </span>
                <span v-else class="text-gray-400">Вы</span>
            </div>

            <!-- Pre-content: Thoughts -->
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
            </div>

            <!-- Post-content: Tools -->
            <div v-if="msg.role === 'assistant' && msg.tools && msg.tools.length > 0" class="w-full mt-2">
                <details class="group/tools">
                    <summary class="list-none cursor-pointer flex items-center gap-2 text-xs text-gray-500 hover:text-gray-300 transition-colors py-1 select-none">
                        <i class="ph ph-wrench text-emerald-500 group-open/tools:rotate-180 transition-transform"></i>
                        <span>Использованные инструменты ({{ Math.ceil(msg.tools.length / 2) }})</span>
                        <span class="opacity-50 text-[10px] ml-auto">Развернуть</span>
                    </summary>
                    
                    <div class="space-y-2 mt-2 pt-2 border-t border-white/5">
                        <div v-for="(tool, tIdx) in msg.tools" :key="tIdx" 
                                class="code-block-wrapper rounded-lg border border-white/5 bg-gray-900 overflow-hidden">
                            <div class="px-3 py-1.5 bg-white/5 flex items-center justify-between text-xs text-gray-300 font-mono border-b border-white/5">
                                <div class="flex items-center gap-2">
                                    <i class="ph ph-terminal-window text-emerald-400"></i>
                                    <span>{{ tool.title }}</span>
                                </div>
                                <button onclick="window.copyCode(this)" class="flex items-center gap-1.5 text-[10px] text-gray-500 hover:text-white transition-colors cursor-pointer">
                                    <i class="ph ph-copy"></i>
                                    <span>Копировать</span>
                                </button>
                            </div>
                            <div class="p-0 overflow-x-auto bg-[#282c34]">
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
        const renderedContent = computed(() => {
            if (!props.msg.content) return '';
            try { return marked.parse(props.msg.content); } catch (e) { return props.msg.content; }
        });

        const manualHighlight = (code, lang) => {
            if (typeof window.hljs === 'undefined') return code;
            let highlighted = code;
            try {
                if (lang && window.hljs.getLanguage(lang.split(' ')[0].toLowerCase())) {
                    highlighted = window.hljs.highlight(code, { language: lang.split(' ')[0].toLowerCase() }).value;
                } else {
                    highlighted = window.hljs.highlightAuto(code).value;
                }
            } catch (e) {}
            return `<code class="hljs" style="background: transparent; padding: 0;">${highlighted}</code>`;
        };

        return { renderedContent, manualHighlight };
    }
});

// --- Main Component ---
export default {
    components: { MessageBubble },
    template: `
        <div class="flex-1 flex flex-col h-full relative z-10">
            
            <!-- Scroll Button (Moved up and z-index increased) -->
            <div class="absolute bottom-32 right-8 z-40 transition-all duration-300"
                 :class="showScrollButton ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-4 pointer-events-none'">
                <button @click="scrollToBottom(true)" 
                    class="w-10 h-10 rounded-full bg-gray-800 border border-white/10 shadow-xl flex items-center justify-center text-gray-400 hover:text-white hover:bg-gray-700 transition-colors cursor-pointer">
                    <i class="ph-bold ph-arrow-down"></i>
                </button>
            </div>

            <!-- Messages Area (Padding bottom added to avoid overlap) -->
            <div class="flex-1 overflow-y-auto px-4 sm:px-8 pt-6 pb-48 space-y-8 scroll-smooth custom-scrollbar" 
                 ref="messagesContainer"
                 @scroll="handleScroll">
                
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
            </div>

            <!-- Input Area (Reduced z-index to allow scrolling behind/above if needed, but keeping it fixed) -->
            <div class="absolute bottom-0 left-0 w-full p-4 sm:p-6 bg-gradient-to-t from-gray-950 via-gray-950/90 to-transparent z-20 pointer-events-none">
                <div class="max-w-3xl mx-auto relative group pointer-events-auto">
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
        const showScrollButton = ref(false);
        const filteredMessages = computed(() => store.messages.filter(m => m.role !== 'system' && m.role !== 'tool'));
        
        const scrollToBottom = async (force = false) => { 
            await nextTick(); 
            if (messagesContainer.value) {
                const { scrollTop, scrollHeight, clientHeight } = messagesContainer.value;
                // Autoscroll logic adjusted for larger padding
                if (force || (scrollHeight - scrollTop - clientHeight) < 250) {
                    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight;
                }
            }
        };
        
        const resizeTextarea = () => { if (textarea.value) { textarea.value.style.height = 'auto'; textarea.value.style.height = Math.min(textarea.value.scrollHeight, 200) + 'px'; }};
        
        const handleScroll = () => {
            if (!messagesContainer.value) return;
            const { scrollTop, scrollHeight, clientHeight } = messagesContainer.value;
            showScrollButton.value = (scrollHeight - scrollTop - clientHeight) > 250;
        };

        watch(() => store.messages.length, () => scrollToBottom());
        watch(() => store.messages[store.messages.length - 1]?.content, () => scrollToBottom());
        
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

        return { store, inputText, send, stop, filteredMessages, messagesContainer, textarea, resizeTextarea, showScrollButton, scrollToBottom, handleScroll };
    }
}
