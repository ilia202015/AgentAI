
import { reactive } from 'vue';

export const store = reactive({
    currentChatId: null,
    chats: [],
    messages: [],
    isThinking: false,
    models: [],
    allTools: [],
    currentModel: '',
    
    // UI State
    isSidebarOpenMobile: false, 
    isSidebarVisibleDesktop: true,
    isPromptPanelOpen: false,
    isBgEnabled: localStorage.getItem('agent_bg_enabled') === 'true',
    presets: {}, 
    activePresetId: 'default', defaultPresetId: 'default',
    
    toasts: [],
    finalPrompts: {},
    activePromptId: null,
    active_parameters: [], 
    
    
    // Computed Metrics
    get totalInputTokens() {
        return this.messages.reduce((maxVal, msg) => Math.max(maxVal, msg.metrics?.total_context || 0), 0);
    },
    get totalCachedTokens() {
        return this.messages.reduce((sum, msg) => sum + (msg.metrics?.cached_tokens || 0), 0);
    },
    get totalUncachedTokens() {
        return this.messages.reduce((sum, msg) => sum + (msg.metrics?.uncached_tokens || 0), 0);
    },
    get totalInputTime() {
        return this.messages.reduce((sum, msg) => sum + (msg.metrics?.input_time || 0), 0);
    },
    get totalOutputTokens() {
        return this.messages.reduce((sum, msg) => sum + (msg.metrics?.output_tokens || 0), 0);
    },
    get totalOutputTime() {
        return this.messages.reduce((sum, msg) => sum + (msg.metrics?.output_time || 0), 0);
    },
    get currentContextTokens() {
        if (this.messages.length === 0) return 0;
        
        let lastUserContext = 0;
        for (let i = this.messages.length - 1; i >= 0; i--) {
            if (this.messages[i].role === 'user' && this.messages[i].metrics?.total_context) {
                lastUserContext = this.messages[i].metrics.total_context;
                break;
            }
        }
        
        let lastModelOutput = 0;
        for (let i = this.messages.length - 1; i >= 0; i--) {
            if (this.messages[i].role === 'model' || this.messages[i].role === 'assistant') {
                if (this.messages[i].metrics?.output_tokens) {
                    lastModelOutput = this.messages[i].metrics.output_tokens;
                }
                break;
            } else if (this.messages[i].role === 'user') {
                break;
            }
        }
        
        return lastUserContext + lastModelOutput;
    },
    setMessages(msgs) {
        if (!msgs) {
            this.messages = [];
            return;
        }
        
        this.messages = msgs.map(m => {
            if (m.items && Array.isArray(m.items)) return m;

            const items = [];
            
            if (m.thoughts) items.push({ type: 'thought', content: m.thoughts });
            

            
            if (m.parts && Array.isArray(m.parts)) {
                m.parts.forEach(p => {
                    if (p.text) {
                        const last = items.length > 0 ? items[items.length - 1] : null;
                        if (last && last.type === 'text') last.content += p.text;
                        else items.push({ type: 'text', content: p.text });
                    } else if (p.image_url) {
                        items.push({ type: 'images', content: [p.image_url] });
                    } else if (p.function_call || p.functionCall) {
                        const call = p.function_call || p.functionCall;
                        let reqContent = call.args;
                        if (typeof reqContent === 'object' && reqContent !== null) {
                            // Если это python и там есть code, показываем чистый код, а не JSON
                            if (call.name === 'python' && reqContent.code) {
                                reqContent = reqContent.code;
                            } else if (call.name === 'shell' && reqContent.input) {
                                reqContent = reqContent.input;
                            } else {
                                reqContent = JSON.stringify(reqContent, null, 2);
                            }
                        }
                         items.push({ 
                            type: 'tool', 
                            title: `Запрос ${call.name}`, 
                            content: reqContent,
                            _msgMetrics: m.metrics
                        });
                    } else if (p.function_response || p.functionResponse) {
                        const resp = p.function_response || p.functionResponse;
                        let resContent = resp.response;
                        
                        // Извлекаем обертку {"result": ...} от agent.py
                        if (resContent && typeof resContent === 'object' && 'result' in resContent) {
                            resContent = resContent.result;
                        }
                        
                        // Если внутри лежит JSON-строка (как от shell_tool), парсим её для красивого отображения
                        if (typeof resContent === 'string') {
                            try { resContent = JSON.stringify(JSON.parse(resContent), null, 2); } catch(e) {}
                        } else if (typeof resContent === 'object') {
                            resContent = JSON.stringify(resContent, null, 2);
                        } else {
                            resContent = String(resContent);
                        }

                        items.push({ 
                            type: 'tool', 
                            title: `Результат ${resp.name}`, 
                            content: resContent,
                            _msgMetrics: m.metrics
                        });
                    }
                });
            } else if (m.content) {
                 items.push({ type: 'text', content: m.content });
            }
            
            if (items.length === 0 && m.content) items.push({ type: 'text', content: m.content });
            
            if (m.images && Array.isArray(m.images) && m.images.length > 0) {
                 const hasImages = items.some(i => i.type === 'images');
                 if (!hasImages) items.push({ type: 'images', content: m.images });
            }

            return { ...m, items: items, metrics: m.metrics || null };
        });
    },
    
    appendChunk(payload) {
        const type = payload.type;
        const data = payload.data;

        if (this.messages.length === 0) this.messages.push({ role: 'assistant', items: [] });
        
        let lastMsg = this.messages[this.messages.length - 1];
        
        if (lastMsg.role === 'user') {
             this.messages.push({ role: 'assistant', items: [] });
             lastMsg = this.messages[this.messages.length - 1];
        }
        
        if (!lastMsg.items) lastMsg.items = [];
        const items = lastMsg.items;
        const lastItem = items.length > 0 ? items[items.length - 1] : null;

        if (type === 'text') {
            if (lastItem && lastItem.type === 'text') lastItem.content += data;
            else items.push({ type: 'text', content: data });
        } 
        else if (type === 'thought') {
            if (lastItem && lastItem.type === 'thought') lastItem.content += data;
            else items.push({ type: 'thought', content: data });
        }
        else if (type === 'tool') {
            items.push({ type: 'tool', ...data });
        }
    },

    toggleSidebarMobile() { this.isSidebarOpenMobile = !this.isSidebarOpenMobile; },
    toggleSidebarDesktop() { this.isSidebarVisibleDesktop = !this.isSidebarVisibleDesktop; },
    closeSidebarMobile() { this.isSidebarOpenMobile = false; },

    
    async toggleParameter(id) {
        const api = await import('./api.js');
        const res = await api.toggleParameter(id, this.currentChatId);
        if (res.status === 'ok') {
            this.active_parameters = res.active_parameters;
        }
    },
    addToast(message, type = 'info') {
        const id = Date.now();
        this.toasts.push({ id, message, type });
        setTimeout(() => {
            this.toasts = this.toasts.filter(t => t.id !== id);
        }, 3000);
    },
    
    toggleBg() {
        this.isBgEnabled = !this.isBgEnabled;
        localStorage.setItem('agent_bg_enabled', this.isBgEnabled);
    }
});
