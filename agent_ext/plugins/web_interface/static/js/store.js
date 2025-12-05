import { reactive } from 'vue';

export const store = reactive({
    currentChatId: null,
    chats: [],
    messages: [],
    isThinking: false,
    
    setMessages(msgs) {
        this.messages = msgs || [];
    },
    
    appendChunk(chunk) {
        // Если сообщений нет вообще, создаем новое от ассистента
        if (this.messages.length === 0) {
            this.messages.push({ role: 'assistant', content: chunk });
            return;
        }
        
        const lastMsg = this.messages[this.messages.length - 1];
        
        // Если последнее сообщение от пользователя, создаем новое от ассистента
        if (lastMsg.role === 'user') {
             this.messages.push({ role: 'assistant', content: chunk });
             return;
        }

        // Если последнее сообщение от ассистента, дописываем в него
        if (lastMsg.role === 'assistant') {
            lastMsg.content += chunk;
        } 
    }
});
