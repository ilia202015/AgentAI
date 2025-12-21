import { reactive } from 'vue';

export const store = reactive({
    currentChatId: null,
    chats: [],
    messages: [],
    isThinking: false,
    
    // UI State
    isSidebarOpenMobile: false, 
    isSidebarVisibleDesktop: true,
    
    toasts: [], 
    
    setMessages(msgs) {
        this.messages = (msgs || []).map(m => {
            if (m.items && Array.isArray(m.items)) {
                return m;
            }

            const items = [];
            
            if (m.thoughts) {
                items.push({ type: 'thought', content: m.thoughts });
            }
            
            if (m.tools && Array.isArray(m.tools)) {
                m.tools.forEach(t => items.push({ type: 'tool', ...t }));
            }
            
            let textContent = '';
            if (m.content) textContent = m.content;
            else if (m.parts && Array.isArray(m.parts)) {
                textContent = m.parts.map(p => p.text || '').join('');
            }
            
            if (textContent.trim()) {
                items.push({ type: 'text', content: textContent });
            }
            
            // Если сообщение от пользователя и нет items, создаем текстовый item
            if (m.role === 'user' && items.length === 0 && textContent) {
                 items.push({ type: 'text', content: textContent });
            }

            return {
                ...m,
                items: items
            };
        });
    },
    
    appendChunk(payload) {
        const type = payload.type;
        const data = payload.data;

        if (this.messages.length === 0) {
             this.messages.push({ role: 'assistant', items: [] });
        }
        
        let lastMsg = this.messages[this.messages.length - 1];
        
        if (lastMsg.role === 'user') {
             this.messages.push({ role: 'assistant', items: [] });
             lastMsg = this.messages[this.messages.length - 1];
        }
        
        if (!lastMsg.items) lastMsg.items = [];
        const items = lastMsg.items;
        const lastItem = items.length > 0 ? items[items.length - 1] : null;

        if (type === 'text') {
            if (lastItem && lastItem.type === 'text') {
                lastItem.content += data;
            } else {
                items.push({ type: 'text', content: data });
            }
        } 
        else if (type === 'thought') {
            if (lastItem && lastItem.type === 'thought') {
                lastItem.content += data;
            } else {
                items.push({ type: 'thought', content: data });
            }
        }
        else if (type === 'tool') {
            items.push({ type: 'tool', ...data });
        }
    },

    toggleSidebarMobile() {
        this.isSidebarOpenMobile = !this.isSidebarOpenMobile;
    },
    
    toggleSidebarDesktop() {
        this.isSidebarVisibleDesktop = !this.isSidebarVisibleDesktop;
    },

    closeSidebarMobile() {
        this.isSidebarOpenMobile = false;
    },

    addToast(message, type = 'info') {
        const id = Date.now();
        this.toasts.push({ id, message, type });
        setTimeout(() => {
            this.toasts = this.toasts.filter(t => t.id !== id);
        }, 3000);
    }
});
