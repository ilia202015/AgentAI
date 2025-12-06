import { reactive } from 'vue';

export const store = reactive({
    currentChatId: null,
    chats: [],
    messages: [],
    isThinking: false,
    
    setMessages(msgs) {
        this.messages = (msgs || []).map(m => ({
            ...m,
            thoughts: m.thoughts || '',
            tools: m.tools || []
        }));
    },
    
    appendChunk(payload) {
        // payload: { type: 'text'|'thought'|'tool', data: '...' }
        const type = payload.type;
        const data = payload.data;

        // Инициализация первого сообщения
        if (this.messages.length === 0 || this.messages[this.messages.length - 1].role === 'user') {
            this.messages.push({ 
                role: 'assistant', 
                content: '', 
                thoughts: '', 
                tools: [] 
            });
        }
        
        const lastMsg = this.messages[this.messages.length - 1];

        if (type === 'text') {
            // Защита от [object Object]
            if (typeof data === 'string') {
                lastMsg.content += data;
            } else {
                console.warn("Received non-string data for text type:", data);
            }
        } 
        else if (type === 'thought') {
            if (typeof data === 'string') {
                lastMsg.thoughts = (lastMsg.thoughts || '') + data;
            }
        }
        else if (type === 'tool') {
            if (!lastMsg.tools) lastMsg.tools = [];
            // Проверяем, не дубликат ли это (иногда stream может глючить)
            // Но для простоты пока просто пушим
            lastMsg.tools.push(data);
        }
    }
});
