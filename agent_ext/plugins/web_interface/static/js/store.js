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

        // Ensure we have a message to append to
        if (this.messages.length === 0) {
             this.messages.push({ role: 'assistant', content: '', thoughts: '', tools: [] });
        }
        
        let lastMsg = this.messages[this.messages.length - 1];
        
        // If last message is user, create new assistant message
        if (lastMsg.role === 'user') {
             this.messages.push({ role: 'assistant', content: '', thoughts: '', tools: [] });
             lastMsg = this.messages[this.messages.length - 1];
        }

        if (type === 'text') {
            if (typeof data === 'string') lastMsg.content += data;
        } 
        else if (type === 'thought') {
            if (typeof data === 'string') lastMsg.thoughts = (lastMsg.thoughts || '') + data;
        }
        else if (type === 'tool') {
            // Force reactivity update by reassigning the array
            const currentTools = lastMsg.tools || [];
            lastMsg.tools = [...currentTools, data];
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
