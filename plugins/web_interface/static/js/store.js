
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
    
    setMessages(msgs) {
        if (!msgs) {
            this.messages = [];
            return;
        }
        
        this.messages = msgs.map(m => {
            if (m.items && Array.isArray(m.items)) return m;

            const items = [];
            
            if (m.thoughts) items.push({ type: 'thought', content: m.thoughts });
            
            if (m.tools && Array.isArray(m.tools)) {
                m.tools.forEach(t => items.push({ type: 'tool', ...t }));
            }
            
            if (m.parts && Array.isArray(m.parts)) {
                m.parts.forEach(p => {
                    if (p.text) {
                        const last = items.length > 0 ? items[items.length - 1] : null;
                        if (last && last.type === 'text') last.content += p.text;
                        else items.push({ type: 'text', content: p.text });
                    } else if (p.image_url) {
                        items.push({ type: 'images', content: [p.image_url] });
                    } else if (p.function_call) {
                         items.push({ 
                            type: 'tool', 
                            title: `Запрос ${p.function_call.name}`, 
                            content: typeof p.function_call.args === 'string' ? p.function_call.args : JSON.stringify(p.function_call.args, null, 2)
                        });
                    } else if (p.function_response) {
                        items.push({ 
                            type: 'tool', 
                            title: `Результат ${p.function_response.name}`, 
                            content: typeof p.function_response.response === 'string' ? p.function_response.response : JSON.stringify(p.function_response.response, null, 2)
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

            return { ...m, items: items };
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
