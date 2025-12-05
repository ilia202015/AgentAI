import { store } from '../store.js';
import * as api from '../api.js';
import { nextTick, ref, watch, onMounted, computed } from 'vue';

export default {
    template: `
        <div class="flex-1 flex flex-col h-full relative bg-gray-950">
            <!-- Messages -->
            <div class="flex-1 overflow-y-auto p-4 space-y-6 scroll-smooth" ref="messagesContainer">
                <div v-if="filteredMessages.length === 0" class="h-full flex flex-col items-center justify-center text-gray-600">
                    <i class="ph ph-chat-circle-dots text-5xl mb-4 opacity-20"></i>
                    <p>Select a chat or start a new conversation</p>
                </div>
                
                <div v-for="(msg, idx) in filteredMessages" :key="idx" 
                    class="group flex flex-col max-w-4xl mx-auto w-full animate-in fade-in slide-in-from-bottom-2 duration-300"
                    :class="msg.role === 'user' ? 'items-end' : 'items-start'">
                    
                    <div class="flex items-center gap-2 mb-1 px-1">
                        <span class="text-[10px] font-bold uppercase tracking-wider opacity-40 select-none" 
                              :class="msg.role === 'user' ? 'text-blue-400' : 'text-emerald-400'">
                            {{ msg.role }}
                        </span>
                    </div>

                    <div class="rounded-lg px-5 py-3 shadow-sm max-w-full overflow-hidden transition-all"
                         :class="[
                            msg.role === 'user' 
                                ? 'bg-blue-600/10 border border-blue-500/20 text-gray-100 rounded-tr-sm' 
                                : 'bg-gray-900 border border-gray-800 w-full rounded-tl-sm'
                         ]">
                         <div class="prose prose-invert prose-sm break-words" v-html="renderMarkdown(msg.content)"></div>
                    </div>
                </div>

                <div v-if="store.isThinking" class="max-w-4xl mx-auto w-full py-4 px-5">
                   <div class="flex gap-1 animate-pulse">
                       <div class="w-2 h-2 bg-gray-500 rounded-full"></div>
                       <div class="w-2 h-2 bg-gray-500 rounded-full animation-delay-200"></div>
                       <div class="w-2 h-2 bg-gray-500 rounded-full animation-delay-400"></div>
                   </div>
                </div>
                <div class="h-4"></div>
            </div>

            <!-- Input -->
            <div class="border-t border-gray-800 p-4 bg-gray-950/80 backdrop-blur z-10">
                <div class="max-w-4xl mx-auto relative flex gap-2 items-end">
                    <textarea 
                        v-model="inputText"
                        @keydown.enter.exact.prevent="send"
                        placeholder="Type a message..."
                        rows="1"
                        ref="textarea"
                        @input="resizeTextarea"
                        class="w-full bg-gray-800 border border-gray-700 text-gray-100 rounded-lg px-4 py-3 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 resize-none max-h-48 overflow-y-auto"
                    ></textarea>
                    <button @click="send" :disabled="!inputText.trim() || store.isThinking"
                        class="mb-0.5 p-3 bg-blue-600 hover:bg-blue-500 text-white rounded-lg disabled:opacity-50 disabled:cursor-not-allowed transition shadow-lg shadow-blue-900/20">
                        <i class="ph ph-paper-plane-right text-lg"></i>
                    </button>
                </div>
            </div>
        </div>
    `,
    setup() {
        const inputText = ref('');
        const messagesContainer = ref(null);
        const textarea = ref(null);
        
        const filteredMessages = computed(() => store.messages.filter(m => m.role !== 'system'));
        
        const scrollToBottom = async () => {
            await nextTick();
            if (messagesContainer.value) {
                // Smooth scroll only if close to bottom? No, just force scroll for now
                messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight;
            }
        };
        
        const resizeTextarea = () => {
            if (textarea.value) {
                textarea.value.style.height = 'auto';
                textarea.value.style.height = textarea.value.scrollHeight + 'px';
            }
        }

        watch(() => store.messages.length, scrollToBottom);
        // Watch for content changes in the last message (streaming)
        watch(() => store.messages[store.messages.length - 1]?.content, () => {
             // Throttling scroll could be good here, but direct call is smoother for eyes usually
             scrollToBottom(); 
        });

        const send = async () => {
            if (!inputText.value.trim()) return;
            
            const text = inputText.value;
            inputText.value = '';
            resizeTextarea(); // Reset height
            
            store.messages.push({ role: 'user', content: text });
            store.isThinking = true;
            await scrollToBottom();
            
            try {
                await api.sendMessage(text);
            } catch (e) {
                console.error(e);
                store.messages.push({ role: 'system', content: 'Error sending message' });
                store.isThinking = false;
            }
        };

        const renderMarkdown = (text) => {
            if (!text) return '';
            try {
                // DOMPurify is recommended but we trust the agent output for now
                // Also marked can handle HTML
                return marked.parse(text);
            } catch (e) {
                return text;
            }
        };

        onMounted(() => {
            marked.setOptions({
                highlight: function(code, lang) {
                    const language = highlight.getLanguage(lang) ? lang : 'plaintext';
                    return highlight.highlight(code, { language }).value;
                },
                langPrefix: 'hljs language-'
            });
        });

        return { store, inputText, send, filteredMessages, messagesContainer, renderMarkdown, textarea, resizeTextarea };
    }
}
