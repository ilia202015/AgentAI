import { store } from '../store.js';
import * as api from '../api.js';
import { nextTick, ref, watch, onMounted, computed, defineComponent } from 'vue';

// --- GLOBAL UTILS ---
if (!window.copyCode) {
    window.copyCode = function(btn) {
        const pre = btn.closest('.code-block-wrapper').querySelector('pre code');
        if (pre) {
            navigator.clipboard.writeText(pre.innerText);
            const originalHtml = btn.innerHTML;
            btn.innerHTML = '<i class="ph-bold ph-check text-green-400"></i><span class="text-green-400">Скопировано</span>';
            btn.classList.remove('opacity-0');
            btn.classList.add('opacity-100');
            setTimeout(() => {
                btn.innerHTML = originalHtml;
                btn.classList.remove('opacity-100');
                btn.classList.add('opacity-0');
            }, 2000);
        }
    };
}

// --- STYLE INJECTION ---
const style = document.createElement('style');
style.textContent = `
    .prose-fix {
        white-space: pre-wrap;       
        word-wrap: break-word;       
        overflow-wrap: break-word;   
        font-variant-ligatures: none; 
    }
    
    /* Typography & Spacing Updates */
    .markdown-content h1 { font-size: 1.6em; font-weight: 700; margin-top: 0.8em; margin-bottom: 0.4em; line-height: 1.3; color: #f3f4f6; }
    .markdown-content h2 { font-size: 1.4em; font-weight: 600; margin-top: 0.8em; margin-bottom: 0.4em; line-height: 1.3; color: #e5e7eb; border-bottom: 1px solid #374151; padding-bottom: 0.2em; }
    .markdown-content h3 { font-size: 1.2em; font-weight: 600; margin-top: 0.6em; margin-bottom: 0.3em; line-height: 1.3; color: #d1d5db; }
    .markdown-content h4 { font-size: 1.1em; font-weight: 600; margin-top: 0.5em; margin-bottom: 0.2em; }
    
    .markdown-content p { margin-bottom: 0.5em; line-height: 1.5; }
    
    .markdown-content ul { list-style-type: disc; padding-left: 1.2em; margin-bottom: 0.5em; }
    .markdown-content ol { list-style-type: decimal; padding-left: 1.2em; margin-bottom: 0.5em; }
    .markdown-content li { margin-bottom: 0.1em; }
    .markdown-content li > p { margin-bottom: 0.1em; } 
    
    .markdown-content a { color: #60a5fa; text-decoration: none; border-bottom: 1px solid transparent; transition: border-color 0.2s; }
    .markdown-content a:hover { border-bottom-color: #60a5fa; }
    
    .markdown-content blockquote { border-left: 3px solid #4b5563; padding-left: 0.8em; color: #9ca3af; margin: 0.5em 0; font-style: italic; }
    
    .markdown-content code { background-color: rgba(99, 110, 123, 0.2); padding: 0.1em 0.3em; border-radius: 0.2em; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size: 0.85em; color: #e5e7eb; }
    .markdown-content pre code { background-color: transparent; padding: 0; color: inherit; }
    
    /* Tables */
    .markdown-content table { border-collapse: collapse; width: 100%; display: table; }
    .markdown-content th, .markdown-content td { border: 1px solid #374151; padding: 0.4em 0.8em; text-align: left; font-size: 0.9em; }
    .markdown-content th { background-color: #1f2937; font-weight: 600; }
    .markdown-content tr:nth-child(even) { background-color: rgba(255, 255, 255, 0.02); }
    
    .markdown-content hr { border-color: #374151; margin: 1em 0; }
    .markdown-content img { max-width: 100%; border-radius: 0.5em; margin: 0.5em 0; }

    .no-ligatures { font-variant-ligatures: none; }
    .katex-display { margin: 0.5em 0; overflow-x: auto; overflow-y: hidden; }
    
    /* Code Block Wrapper Spacing */
    .code-block-wrapper { margin: 0.6em 0 !important; }
`;
document.head.appendChild(style);

const renderer = new marked.Renderer();

renderer.code = function(code, language) {
    try {
        const safeCode = String(code || '');
        let highlighted = safeCode;
        let langDisplay = (language || 'text').toLowerCase();

        if (window.hljs) {
            const validLang = !!(language && hljs.getLanguage(language));
            if (validLang) {
                highlighted = hljs.highlight(safeCode, { language: language }).value;
            } else {
                const auto = hljs.highlightAuto(safeCode);
                highlighted = auto.value;
                if (auto.language) langDisplay = auto.language;
            }
        } else {
            highlighted = safeCode.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
        }
        
        return `
            <div class="code-block-wrapper my-2 rounded-lg border border-white/10 bg-[#282c34] overflow-hidden relative group/code">
                <div class="flex items-center justify-between px-3 py-1.5 bg-white/5 border-b border-white/5">
                    <span class="text-xs font-mono text-gray-400">${langDisplay}</span>
                    <button onclick="window.copyCode(this)" class="flex items-center gap-1.5 text-[10px] text-gray-500 hover:text-white transition-colors cursor-pointer z-10 opacity-0 group-hover/code:opacity-100">
                        <i class="ph-bold ph-copy"></i>
                        <span>Копировать</span>
                    </button>
                </div>
                <div class="overflow-x-auto p-3">
                    <pre><code class="hljs language-${langDisplay} no-ligatures text-sm" style="background: transparent; padding: 0;">${highlighted}</code></pre>
                </div>
            </div>
        `;
    } catch (e) {
        console.error("Renderer error:", e);
        return `<pre class="text-red-400 text-xs">Code Render Error</pre>`;
    }
};

renderer.link = function(href, title, text) {
    return `<a href="${href}" target="_blank" rel="noopener noreferrer" title="${title || ''}">${text}</a>`;
};

renderer.table = function(header, body) {
    if (body) body = '<tbody>' + body + '</tbody>';
    return '<div style="overflow-x: auto; margin: 0.6em 0;"><table class="min-w-full">\n'
        + '<thead>\n' + header + '</thead>\n'
        + body + '</table></div>\n';
};

marked.setOptions({
    renderer: renderer,
    pedantic: false,
    gfm: true,
    breaks: true,
});

const MarkdownContent = defineComponent({
    props: ['content'],
    template: `<div ref="root" class="markdown-content prose-fix text-gray-200 text-sm leading-relaxed" v-html="rendered"></div>`,
    setup(props) {
        const root = ref(null);
        
        const rendered = computed(() => {
            if (!props.content) return '';
            const text = typeof props.content === 'object' ? JSON.stringify(props.content, null, 2) : String(props.content || '');
            
            try { 
                return marked.parse(text); 
            } catch (e) { 
                console.error("Markdown parse error:", e);
                const safeText = text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
                return `<div class="text-red-400 text-xs mb-2">Markdown Error: ${e.message}</div><pre class="whitespace-pre-wrap font-mono text-xs">${safeText}</pre>`; 
            }
        });

        const updateMath = () => {
            if (!root.value || typeof renderMathInElement === 'undefined') return;
            try {
                renderMathInElement(root.value, {
                    delimiters: [ {left: '$$', right: '$$', display: true}, {left: '$', right: '$', display: false}, {left: '\\(', right: '\\)', display: false}, {left: '\\[', right: '\\]', display: true} ],
                    ignoredTags: ["script", "noscript", "style", "textarea", "pre", "code", "option"],
                    throwOnError: false
                });
            } catch(e) {}
        };

        watch(rendered, async () => { await nextTick(); updateMath(); });
        onMounted(async () => { await nextTick(); updateMath(); });

        return { root, rendered };
    }
});

const MessageBubble = defineComponent({
    components: { MarkdownContent },
    props: ['msg', 'index'],
    emits: ['edit'],
    template: `
        <div class="group flex flex-col w-[95%] mx-auto animate-fade-in-up"
            :class="msg.role === 'user' ? 'items-end' : 'items-start'">
            
            <div class="flex items-center gap-2 mb-1 px-1 opacity-60 text-xs font-medium tracking-wide">
                <span v-if="msg.role === 'assistant' || msg.role === 'model'" class="flex items-center gap-1.5 text-blue-400">
                        <i class="ph-fill ph-robot"></i> Агент
                </span>
                <span v-else class="text-gray-400 flex items-center gap-2">
                    <span>Вы</span>
                    <button @click="startEdit" v-if="!isEditing" class="opacity-0 group-hover:opacity-100 transition-opacity hover:text-white" title="Редактировать"><i class="ph-bold ph-pencil-simple"></i></button>
                </span>
            </div>

            <div v-if="isEditing && msg.role === 'user'" class="w-full bg-gray-900 border border-white/10 rounded-xl p-3 relative max-w-full shadow-lg">
                <textarea v-model="editContent" rows="3" class="w-full bg-transparent text-sm focus:outline-none resize-none mb-2"></textarea>
                <div class="flex justify-end gap-2">
                    <button @click="cancelEdit" class="px-3 py-1.5 rounded text-xs hover:bg-white/5 text-gray-400">Отмена</button>
                    <button @click="saveEdit" class="px-3 py-1.5 rounded bg-blue-600 text-white text-xs hover:bg-blue-500">Сохранить</button>
                </div>
            </div>

            <div v-else class="flex flex-col w-full gap-1">
                <div v-for="(item, idx) in processedTimeline" :key="idx" class="w-full flex flex-col" 
                     :class="msg.role === 'user' ? 'items-end' : 'items-start'">
                    
                    <div v-if="item.type === 'thought'" class="w-full">
                        <details class="group/thought">
                            <summary class="list-none cursor-pointer flex items-center gap-2 text-xs text-gray-500 hover:text-gray-300 transition-colors py-1 select-none">
                                <i class="ph ph-brain text-purple-400 group-open/thought:rotate-180 transition-transform"></i>
                                <span>Процесс мышления</span>
                                <span class="opacity-50 text-[10px] ml-auto">Развернуть</span>
                            </summary>
                            <div class="mt-2 pl-3 border-l-2 border-purple-500/20 text-gray-400 text-xs leading-relaxed font-mono bg-gray-900/50 p-4 border border-white/5 rounded-r-lg relative group/content">
                                 <button @click="copyToClipboard(item.content, $event)" class="absolute top-2 right-2 opacity-0 group-hover/content:opacity-100 transition-opacity p-1 text-gray-500 hover:text-white" title="Копировать">
                                    <i class="ph ph-copy"></i>
                                 </button>
                                 <div class="font-bold text-purple-400 mb-1">Thought Process:</div>
                                 <MarkdownContent :content="item.content" />
                            </div>
                        </details>
                    </div>

                    <div v-else-if="item.type === 'pair'" class="w-full my-1">
                        <details class="group/tools">
                            <summary class="list-none cursor-pointer flex items-center gap-2 text-xs text-gray-500 hover:text-gray-300 transition-colors py-1 select-none">
                                <i class="ph ph-wrench text-emerald-500 group-open/tools:rotate-180 transition-transform"></i>
                                <span>Использован инструмент: {{ item.request.title ? item.request.title.replace('Запрос ', '') : 'Unknown' }}</span>
                                <span class="opacity-50 text-[10px] ml-auto">Развернуть</span>
                            </summary>
                            <div class="mt-2 pt-2 border-t border-white/5">
                                <div class="rounded-t-lg border border-white/10 bg-[#1e222a] overflow-hidden relative group/req">
                                    <div class="px-3 py-1.5 bg-white/5 border-b border-white/5 text-xs text-emerald-400 font-mono flex justify-between items-center">
                                        <span>{{ item.request.title }}</span>
                                        <button @click="copyToClipboard(item.request.content, $event)" class="text-gray-500 hover:text-white opacity-0 group-hover/req:opacity-100 transition-opacity"><i class="ph ph-copy"></i></button>
                                    </div>
                                    <div class="p-3 overflow-x-auto font-mono text-xs text-gray-300 whitespace-pre-wrap no-ligatures">{{ item.request.content }}</div>
                                </div>
                                <div class="rounded-b-lg border-x border-b border-white/10 bg-[#1e222a] overflow-hidden relative group/res">
                                     <div class="px-3 py-1.5 bg-white/5 border-y border-white/5 text-xs text-blue-400 font-mono flex justify-between items-center">
                                        <span>Результат</span>
                                        <button @click="copyToClipboard(item.result.content, $event)" class="text-gray-500 hover:text-white opacity-0 group-hover/res:opacity-100 transition-opacity"><i class="ph ph-copy"></i></button>
                                    </div>
                                    <div class="p-3 overflow-x-auto font-mono text-xs text-gray-400 whitespace-pre-wrap no-ligatures">{{ item.result.content }}</div>
                                </div>
                            </div>
                        </details>
                    </div>

                    <div v-else-if="item.type === 'tool'" class="w-full my-1">
                        <details class="group/tools">
                            <summary class="list-none cursor-pointer flex items-center gap-2 text-xs text-gray-500 hover:text-gray-300 transition-colors py-1 select-none">
                                <i class="ph ph-wrench text-emerald-500 group-open/tools:rotate-180 transition-transform"></i>
                                <span>Инструмент: {{ item.title }}</span>
                                <span class="opacity-50 text-[10px] ml-auto">Развернуть</span>
                            </summary>
                            <div class="mt-2 pt-2 border-t border-white/5">
                                <div class="rounded-lg border border-white/10 bg-[#1e222a] overflow-hidden relative group/tool">
                                    <div class="px-3 py-1.5 bg-white/5 border-b border-white/5 text-xs text-emerald-400 font-mono flex justify-between items-center">
                                        <span>{{ item.title }}</span>
                                        <button @click="copyToClipboard(item.content, $event)" class="text-gray-500 hover:text-white opacity-0 group-hover/tool:opacity-100 transition-opacity"><i class="ph ph-copy"></i></button>
                                    </div>
                                    <div class="p-3 overflow-x-auto font-mono text-xs text-gray-300 whitespace-pre-wrap no-ligatures">{{ item.content }}</div>
                                </div>
                            </div>
                        </details>
                    </div>

                    <!-- Images -->
                    <div v-else-if="item.type === 'images'" class="flex flex-wrap gap-2 my-1" :class="msg.role === 'user' ? 'justify-end' : 'justify-start'">
                        <div v-for="(img, idx) in item.content" :key="idx" class="relative group/image">
                            <img :src="img" class="max-w-[300px] max-h-[300px] rounded-lg border border-white/10 object-cover" />
                        </div>
                    </div>

                    <div v-else-if="item.type === 'text' && (item.content.trim() || isEditing)" class="relative max-w-full overflow-hidden transition-all shadow-lg w-full group/text"
                        :class="[
                        msg.role === 'user' 
                            ? 'bg-gradient-to-br from-blue-600 to-indigo-600 text-white rounded-2xl rounded-tr-sm px-5 py-3.5 border border-white/10 w-auto self-end'
                            : 'bg-gray-800/40 backdrop-blur-md border border-white/5 text-gray-100 rounded-2xl rounded-tl-sm px-6 py-5'
                        ]">
                        <div v-if="msg.role === 'user'" class="whitespace-pre-wrap font-sans text-sm leading-relaxed">{{ item.content }}</div>
                        <MarkdownContent v-else :content="item.content" />
                        
                        <div v-if="msg.role === 'assistant' || msg.role === 'model'" class="absolute top-2 right-2 opacity-0 group-hover/text:opacity-100 transition-opacity flex gap-1">
                            <button @click="copyToClipboard(item.content, $event)" class="p-1.5 text-gray-500 hover:text-white hover:bg-white/10 rounded transition" title="Копировать"><i class="ph ph-copy"></i></button>
                        </div>
                    </div>

                </div>
            </div>
        </div>
    `,
    setup(props, { emit }) {
        const isEditing = ref(false);
        const editContent = ref('');

        const getFullText = () => {
            if (props.msg.items && props.msg.items.length) {
                return props.msg.items.filter(i => i.type === 'text').map(i => i.content).join('\n');
            }
            if (props.msg.parts && props.msg.parts.length) {
                return props.msg.parts.filter(p => p.text).map(p => p.text).join('\n');
            }
            return props.msg.content || '';
        };

        const processedTimeline = computed(() => {
            let rawItems = [];
            if (props.msg.items && props.msg.items.length > 0) {
                rawItems = props.msg.items;
            } else {
                if (props.msg.thoughts) rawItems.push({ type: 'thought', content: props.msg.thoughts });
                if (props.msg.parts && Array.isArray(props.msg.parts)) {
                    props.msg.parts.forEach(part => {
                        if (part.text) rawItems.push({ type: 'text', content: part.text });
                        else if (part.image_url) rawItems.push({ type: 'images', content: [part.image_url] });
                        else if (part.function_call) rawItems.push({ 
                            type: 'tool', title: `Запрос ${part.function_call.name}`, 
                            content: typeof part.function_call.args === 'string' ? part.function_call.args : JSON.stringify(part.function_call.args, null, 2)
                        });
                        else if (part.function_response) rawItems.push({ 
                            type: 'tool', title: `Результат ${part.function_response.name}`, 
                            content: typeof part.function_response.response === 'string' ? part.function_response.response : JSON.stringify(part.function_response.response, null, 2)
                        });
                    });
                }
                if (rawItems.length === 0 && props.msg.content) rawItems.push({ type: 'text', content: props.msg.content });
                
                // Images from old format if any (though usually items are preferred)
                if (props.msg.images) {
                    rawItems.push({ type: 'images', content: props.msg.images });
                }
            }

            const res = [];
            for (let i = 0; i < rawItems.length; i++) {
                const item = rawItems[i];
                if (item.type === 'tool') {
                    if (item.title && item.title.startsWith("Запрос") && i + 1 < rawItems.length) {
                        const next = rawItems[i+1];
                        if (next.type === 'tool') {
                            const toolName = item.title.substring(7).trim();
                            if (next.title && (next.title === `Результат ${toolName}` || next.title.startsWith('Результат'))) {
                                res.push({ type: 'pair', request: item, result: next });
                                i++; continue;
                            }
                        }
                    }
                }
                res.push(item);
            }
            return res;
        });

        const startEdit = () => { editContent.value = getFullText(); isEditing.value = true; };
        const cancelEdit = () => { isEditing.value = false; };
        const saveEdit = () => { emit('edit', props.index, editContent.value); isEditing.value = false; };
        const copyToClipboard = (text, event) => {
             navigator.clipboard.writeText(text);
             if (event && event.currentTarget) {
                const btn = event.currentTarget;
                const originalHtml = btn.innerHTML;
                btn.innerHTML = '<i class="ph-bold ph-check text-emerald-400"></i>';
                setTimeout(() => btn.innerHTML = originalHtml, 2000);
             } else {
                 store.addToast("Текст скопирован", "success");
             }
        };

        return { processedTimeline, isEditing, editContent, startEdit, cancelEdit, saveEdit, copyToClipboard };
    }
});

export default {
    components: { MessageBubble },
    template: `
        <div class="flex-1 flex flex-col h-full relative z-10 min-w-0" @dragover.prevent="onDragOver" @dragenter.prevent="onDragOver">
            <div class="hidden md:block absolute top-4 left-2 z-50">
                <button @click="store.toggleSidebarDesktop()" class="p-2 rounded-lg bg-gray-900/50 backdrop-blur border border-white/10 text-gray-400 hover:text-white transition-colors shadow-sm">
                    <i class="ph-bold" :class="store.isSidebarVisibleDesktop ? 'ph-caret-left' : 'ph-caret-right'"></i>
                </button>
            </div>
            <div class="md:hidden absolute top-4 left-4 z-50">
                <button @click="store.toggleSidebarMobile()" class="p-2 rounded-lg bg-gray-900/80 backdrop-blur border border-white/10 text-gray-300">
                    <i class="ph-bold ph-list"></i>
                </button>
            </div>
            
            <div class="absolute bottom-32 right-8 z-40 transition-all duration-300"
                 :class="showScrollButton ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-4 pointer-events-none'">
                <button @click="scrollToBottom(true)" 
                    class="w-10 h-10 rounded-full bg-gray-800 border border-white/10 shadow-xl flex items-center justify-center text-gray-400 hover:text-white hover:bg-gray-700 transition-colors cursor-pointer">
                    <i class="ph-bold ph-arrow-down"></i>
                </button>
            </div>

            <div class="flex-1 overflow-y-auto px-2 md:px-0 pt-16 md:pt-6 pb-48 space-y-8 scroll-smooth custom-scrollbar" 
                 ref="messagesContainer" @scroll="handleScroll">
                
                <div v-if="filteredMessages.length === 0" class="h-full flex flex-col items-center justify-center text-center opacity-0 animate-fade-in-up" style="animation-delay: 0.1s; opacity: 1">
                    <div class="w-16 h-16 rounded-2xl bg-gradient-to-tr from-gray-800 to-gray-700 flex items-center justify-center mb-6 shadow-2xl border border-white/5">
                        <i class="ph-duotone ph-sparkle text-3xl text-blue-400"></i>
                    </div>
                    <h2 class="text-2xl font-bold text-white mb-2 tracking-tight">Чем я могу помочь?</h2>
                    <p class="text-gray-500 max-w-md text-sm leading-relaxed">Я могу писать код, анализировать данные и помогать с творческими задачами.</p>
                </div>
                
                <MessageBubble v-for="(msg, idx) in filteredMessages" :key="idx" :index="idx" :msg="msg" @edit="handleEdit" />

                <div v-if="store.isThinking" class="w-[95%] mx-auto w-full py-2">
                   <div class="flex items-center gap-3 px-4">
                       <div class="w-6 h-6 rounded-full bg-blue-500/10 flex items-center justify-center">
                            <i class="ph-duotone ph-spinner animate-spin text-blue-500 text-xs"></i>
                       </div>
                       <span class="text-xs text-blue-400/80 font-medium animate-pulse">Думаю...</span>
                   </div>
                </div>
            </div>

            <div class="absolute bottom-0 left-0 w-full pb-6 pt-12 bg-gradient-to-t from-gray-950 via-gray-950/90 to-transparent z-20 pointer-events-none">
                <div class="w-[95%] mx-auto relative group pointer-events-auto">
                    <div class="absolute inset-0 bg-gradient-to-r from-blue-500/20 to-purple-500/20 rounded-xl blur-lg opacity-0 group-focus-within:opacity-100 transition-opacity duration-500"></div>
                    <div class="relative bg-gray-900/80 backdrop-blur-xl border border-white/10 rounded-xl shadow-2xl overflow-hidden flex flex-col transition-all group-focus-within:border-blue-500/30 group-focus-within:bg-gray-900/90">
                        <div v-if="editingIndex !== null" class="bg-blue-500/10 border-b border-white/5 px-4 py-1 text-xs text-blue-300 flex justify-between items-center">
                            <span>Редактирование сообщения...</span>
                            <button @click="cancelEdit" class="hover:text-white"><i class="ph-bold ph-x"></i></button>
                        </div>
                        
                        <!-- Attachments Preview -->
                        <div v-if="attachments.length > 0" class="flex gap-2 p-2 px-4 overflow-x-auto custom-scrollbar border-b border-white/5">
                            <div v-for="(img, idx) in attachments" :key="idx" class="relative group/img flex-shrink-0">
                                <img :src="img" class="h-16 w-16 object-cover rounded-lg border border-white/10">
                                <button @click="removeAttachment(idx)" class="absolute -top-1 -right-1 bg-red-500 text-white rounded-full p-0.5 shadow-md opacity-0 group-hover/img:opacity-100 transition-opacity transform scale-75 hover:scale-100">
                                    <i class="ph-bold ph-x text-xs"></i>
                                </button>
                            </div>
                        </div>

                        <textarea v-model="inputText" @keydown.enter.exact.prevent="send" @paste="handlePaste"
                            :placeholder="editingIndex !== null ? 'Измените сообщение...' : 'Отправить сообщение...'"
                            rows="1" ref="textarea" @input="resizeTextarea" 
                            class="w-full bg-transparent text-gray-100 px-4 py-4 focus:outline-none resize-none max-h-48 overflow-y-auto placeholder-gray-500 text-sm leading-relaxed"></textarea>
                        
                        <div class="flex justify-between items-center px-2 pb-2">
                            <div class="flex gap-1 px-2">
                                <button @click="triggerFileSelect" class="p-2 text-gray-400 hover:text-blue-400 transition-colors rounded-lg hover:bg-white/5" title="Прикрепить изображение">
                                    <i class="ph-bold ph-paperclip"></i>
                                </button>
                                <button @click="captureScreen" class="p-2 text-gray-400 hover:text-blue-400 transition-colors rounded-lg hover:bg-white/5" title="Сделать скриншот экрана">
                                    <i class="ph-bold ph-monitor"></i>
                                </button>
                                <input type="file" ref="fileInput" multiple accept="image/*" class="hidden" @change="handleFileSelect">
                            </div>
                            <button v-if="store.isThinking" @click="stop" class="p-2 rounded-lg bg-red-500/10 text-red-500 hover:bg-red-500/20 transition-all duration-200 flex items-center justify-center gap-2 border border-red-500/20" title="Остановить генерацию"><i class="ph-fill ph-stop text-lg"></i></button>
                            <button v-else @click="send" :disabled="!inputText.trim() && attachments.length === 0" 
                                class="p-2 rounded-lg transition-all duration-200 flex items-center justify-center gap-2" 
                                :class="(inputText.trim() || attachments.length > 0) ? 'bg-blue-600 text-white shadow-lg shadow-blue-500/25 hover:bg-blue-500' : 'bg-white/5 text-gray-600 cursor-not-allowed'">
                                <i :class="editingIndex !== null ? 'ph-fill ph-check' : 'ph-fill ph-paper-plane-right'" class="text-lg"></i>
                            </button>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Drag and Drop Overlay -->
            <div v-if="isDragging" 
                 @dragleave.prevent.stop="isDragging = false" 
                 @drop.prevent.stop="handleDrop" 
                 @dragover.prevent
                 class="absolute inset-0 z-50 bg-gray-900/90 backdrop-blur-sm flex items-center justify-center m-2 rounded-xl border-2 border-dashed border-blue-500">
                <div class="text-center pointer-events-none">
                    <i class="ph-duotone ph-upload-simple text-6xl text-blue-500 mb-4 animate-bounce"></i>
                    <h3 class="text-xl font-bold text-white">Отпустите файлы здесь</h3>
                    <p class="text-gray-400 text-sm mt-2">Поддерживаются изображения</p>
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
        const fileInput = ref(null);
        const attachments = ref([]);
        const isDragging = ref(false);
        
        const filteredMessages = computed(() => {
            const raw = store.messages.filter(m => m.role !== 'system' && m.role !== 'tool');
            const merged = [];
            
            for (const msg of raw) {
                if (msg.role === 'user') {
                    const hasText = msg.content && msg.content.trim();
                    const hasItems = msg.items && msg.items.some(i => i.type === 'text' && i.content.trim());
                    const hasImages = msg.images && msg.images.length > 0;
                    if (!hasText && !hasItems && !hasImages && !(msg.parts && msg.parts.length > 0)) continue;
                }

                const last = merged.length > 0 ? merged[merged.length - 1] : null;
                const isAgent = role => role === 'assistant' || role === 'model';

                if (last && isAgent(last.role) && isAgent(msg.role)) {
                    // Merging logic for agent messages (unchanged)
                    if (msg.items) {
                        if (!last.items) last.items = [];
                        const prevThoughtsStr = (last.items || []).filter(i => i.type === 'thought').map(i => i.content).join('\n');
                        const newThoughtsList = msg.items.filter(i => i.type === 'thought');
                        const newThoughtsStr = newThoughtsList.map(i => i.content).join('\n');
                        
                        let mergedThoughts = false;
                        if (prevThoughtsStr && newThoughtsStr && newThoughtsStr.startsWith(prevThoughtsStr)) {
                             const firstThoughtIdx = last.items.findIndex(i => i.type === 'thought');
                             if (firstThoughtIdx !== -1) {
                                 last.items[firstThoughtIdx].content = newThoughtsStr;
                                 for (let i = last.items.length - 1; i > firstThoughtIdx; i--) {
                                     if (last.items[i].type === 'thought') last.items.splice(i, 1);
                                 }
                                 mergedThoughts = true;
                             }
                        }

                        if (mergedThoughts) {
                             const otherItems = msg.items.filter(i => i.type !== 'thought').map(i => ({...i}));
                             last.items.push(...otherItems);
                        } else {
                             const allNewItems = msg.items.map(i => ({...i}));
                             last.items.push(...allNewItems);
                        }
                    }
                    if (msg.parts) {
                        if (!last.parts) last.parts = [];
                        last.parts = [...last.parts, ...msg.parts];
                    }
                    last.thoughts = (last.items || []).filter(i => i.type === 'thought').map(i => i.content).join('\n');
                    if (msg.content) last.content = (last.content ? last.content + '\n' : '') + msg.content;

                } else {
                    merged.push({ ...msg, items: msg.items ? [...msg.items] : undefined, parts: msg.parts ? [...msg.parts] : undefined, images: msg.images ? [...msg.images] : undefined });
                }
            }
            return merged;
        });
        
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
        watch(() => store.messages[store.messages.length - 1]?.items?.length, () => scrollToBottom());
        
        const handleEdit = async (index, newText) => {
            store.isThinking = true;
            try {
                const res = await api.editMessage(store.currentChatId, index, newText);
                if (res.error) { store.isThinking = false; store.addToast(res.error, "error"); return; }
                store.addToast("Сообщение обновлено", "success");
            } catch (e) {
                store.isThinking = false;
                store.addToast("Ошибка редактирования", "error");
            }
        };

        const startEditing = (idx, content) => { editingIndex.value = idx; inputText.value = content; if (textarea.value) { textarea.value.focus(); resizeTextarea(); } };
        const cancelEdit = () => { editingIndex.value = null; inputText.value = ''; resizeTextarea(); };

        const triggerFileSelect = () => fileInput.value && fileInput.value.click();
        
        const processFiles = (files) => {
            if (!files) return;
            
            for (let i = 0; i < files.length; i++) {
                const file = files[i];
                if (!file.type.startsWith('image/')) continue;
                
                const reader = new FileReader();
                reader.onload = (e) => {
                    attachments.value.push(e.target.result);
                };
                reader.readAsDataURL(file);
            }
        };

        const handleFileSelect = (event) => {
            processFiles(event.target.files);
            event.target.value = ''; // Reset
        };

        const captureScreen = async () => {
            try {
                const stream = await navigator.mediaDevices.getDisplayMedia({ 
                    video: { cursor: "always" }, 
                    audio: false 
                });
                
                // Создаем video элемент для захвата кадра
                const video = document.createElement('video');
                video.srcObject = stream;
                video.play();
                
                // Ждем пока видео будет готово
                await new Promise(resolve => video.onloadedmetadata = resolve);
                // Небольшая задержка для стабилизации
                await new Promise(resolve => setTimeout(resolve, 500));
                
                const canvas = document.createElement('canvas');
                canvas.width = video.videoWidth;
                canvas.height = video.videoHeight;
                
                const ctx = canvas.getContext('2d');
                ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
                
                const dataURL = canvas.toDataURL('image/png');
                attachments.value.push(dataURL);
                
                // Останавливаем поток
                stream.getTracks().forEach(track => track.stop());
                
            } catch (err) {
                console.error("Error capturing screen:", err);
                if (err.name !== 'NotAllowedError') {
                    store.addToast("Ошибка захвата экрана", "error");
                }
            }
        };
        
        const handlePaste = (event) => {
            const items = (event.clipboardData || window.clipboardData).items;
            let hasImages = false;
            const files = [];
            for (let i = 0; i < items.length; i++) {
                if (items[i].kind === 'file' && items[i].type.startsWith('image/')) {
                    files.push(items[i].getAsFile());
                    hasImages = true;
                }
            }
            if (hasImages) {
                processFiles(files);
            }
        };

        const onDragOver = () => { isDragging.value = true; };
        
        const handleDrop = (event) => {
            isDragging.value = false;
            processFiles(event.dataTransfer.files);
        };

        const removeAttachment = (index) => {
            attachments.value.splice(index, 1);
        };

        const send = async () => {
            if (!inputText.value.trim() && attachments.value.length === 0) return;
            
            const text = inputText.value;
            const imgs = [...attachments.value];
            
            inputText.value = '';
            attachments.value = [];
            if (textarea.value) textarea.value.style.height = 'auto';
            store.isThinking = true;

            if (editingIndex.value !== null) {
                const idx = editingIndex.value;
                editingIndex.value = null;
                handleEdit(idx, text);
            } else {
                const msg = { role: 'user', content: text, items: [{type: 'text', content: text}] };
                if (imgs.length > 0) {
                    msg.images = imgs;
                    msg.items.push({ type: 'images', content: imgs });
                }

                store.messages.push(msg);
                await scrollToBottom(true);
                try { 
                    const res = await api.sendMessage(store.currentChatId, text, imgs);
                    if (res.error) { store.isThinking = false; store.addToast(res.error, "error"); }
                } 
                catch (e) { store.isThinking = false; store.addToast("Ошибка отправки", "error"); }
            }
        };
        const stop = async () => { store.isThinking = false; store.addToast("Остановка...", "info"); await api.stopGeneration(store.currentChatId); };

        onMounted(() => scrollToBottom(true));

        return { store, inputText, send, stop, filteredMessages, messagesContainer, textarea, resizeTextarea, showScrollButton, scrollToBottom, handleScroll, handleEdit, startEditing, editingIndex, cancelEdit, fileInput, attachments, triggerFileSelect, handleFileSelect, removeAttachment, handlePaste, onDragOver, handleDrop, isDragging, captureScreen };
    }
}