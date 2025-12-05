const API_BASE = '/api';

export async function fetchChats() {
    try {
        const res = await fetch(`${API_BASE}/chats`);
        return await res.json();
    } catch (e) { console.error(e); return []; }
}

export async function loadChat(id) {
    const res = await fetch(`${API_BASE}/chats/${id}/load`, { method: 'POST' });
    return res.json();
}

export async function fetchCurrentChat() {
    try {
        const res = await fetch(`${API_BASE}/current`);
        return await res.json();
    } catch (e) { return null; }
}

export async function createChat() {
    const res = await fetch(`${API_BASE}/chats`, { method: 'POST' });
    return res.json();
}

export async function deleteChat(id) {
    const res = await fetch(`${API_BASE}/chats/${id}`, { method: 'DELETE' });
    return res.json();
}

export async function sendMessage(text) {
    const res = await fetch(`${API_BASE}/send`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text })
    });
    return res.json();
}
