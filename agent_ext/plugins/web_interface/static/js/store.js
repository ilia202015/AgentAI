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
        this.messages = (msgs || []).map(m => ({
            ...m,
            thoughts: m.thoughts || '',
            tools: m.tools || []
        }));
    },
    
    appendChunk(payload) {
        const type = payload.type;
        const data = payload.data;

        if (this.messages.length === 0 || this.messages[this.messages.length - 1].role === 'user') {
            this.messages.push({ role: 'assistant', content: '', thoughts: '', tools: [] });
        }
        
        const lastMsg = this.messages[this.messages.length - 1];

        if (type === 'text') {
            if (typeof data === 'string') lastMsg.content += data;
        } 
        else if (type === 'thought') {
            if (typeof data === 'string') lastMsg.thoughts = (lastMsg.thoughts || '') + data;
        }
        else if (type === 'tool') {
            if (!lastMsg.tools) lastMsg.tools = [];
            lastMsg.tools.push(data);
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
