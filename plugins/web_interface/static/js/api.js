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
    return null; 
}

export async function createChat() {
    const res = await fetch(`${API_BASE}/chats`, { method: 'POST' });
    return res.json();
}

export async function deleteChat(id) {
    const res = await fetch(`${API_BASE}/chats/${id}`, { method: 'DELETE' });
    return res.json();
}

export async function renameChat(id, name) {
    const res = await fetch(`${API_BASE}/chats/${id}/rename`, { 
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name }) 
    });
    return res.json();
}

export async function sendMessage(chatId, text, images = []) {
    const res = await fetch(`${API_BASE}/send`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ chatId: chatId, message: text, images: images })
    });
    return res.json();
}

export async function editMessage(chatId, index, text) {
    const res = await fetch(`${API_BASE}/edit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ chatId: chatId, index: index, new_content: text })
    });
    return res.json();
}

export async function stopGeneration(chatId) {
    try {
        const res = await fetch(`${API_BASE}/stop`, { 
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ chatId: chatId }) 
        });
        return await res.json();
    } catch (e) { return { status: 'error' }; }
}

export async function startTempChat() {
    const res = await fetch(`${API_BASE}/temp`, { method: 'POST' });
    return res.json();
}

export async function fetchModels() {
    const res = await fetch(`${API_BASE}/models`);
    return await res.json();
}

export async function changeModel(chatId, modelName) {
    const res = await fetch(`${API_BASE}/chats/${chatId}/model`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model: modelName })
    });
    return await res.json();
}

export async function clearContext(chatId) {
    const res = await fetch(`${API_BASE}/chats/${chatId}/clear-context`, { method: 'POST' });
    return await res.json();
}

export async function fetchFinalPrompts() {
    const res = await fetch(`${API_BASE}/final-prompts`);
    return await res.json();
}

export async function saveFinalPrompt(id, name, text, type = 'system', icon = 'ph-app-window', gather_script = '', makeActive = false, fs_permissions = null, exec_script = '') {
    const res = await fetch(`${API_BASE}/final-prompts`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id, name, text, type, icon, gather_script, make_active: makeActive, fs_permissions, exec_script })
    });
    return await res.json();
}

export async function selectFinalPrompt(id) {
    const res = await fetch(`${API_BASE}/final-prompts/select`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id, chatId })
    });
    return await res.json();
}

export async function deleteFinalPrompt(id) {
    const res = await fetch(`${API_BASE}/final-prompts/${id}`, { method: 'DELETE' });
    return await res.json();
}

export async function toggleParameter(id, chatId = null) {
    const res = await fetch(`${API_BASE}/final-prompts/toggle-parameter`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id, chatId })
    });
    return await res.json();
}

export async function savePreset(id, name, prompt_ids, modes, commands, blocked, settings, fs_permissions) {
    const res = await fetch(`${API_BASE}/presets`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id, name, prompt_ids, modes, commands, blocked, settings, fs_permissions })
    });
    return await res.json();
}

export async function deletePreset(id) {
    const res = await fetch(`${API_BASE}/presets/${id}`, { method: 'DELETE' });
    return await res.json();
}

export async function changeChatPreset(chatId, presetId) {
    const res = await fetch(`${API_BASE}/chats/${chatId}/preset`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ preset_id: presetId })
    });
    return await res.json();
}

export async function setDefaultPreset(presetId) {
    const res = await fetch(`${API_BASE}/presets/default`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id: presetId })
    });
    return await res.json();
}

export async function fetchTools() {
    const res = await fetch(`${API_BASE}/tools`);
    return await res.json();
}

export async function execCommandScript(chatId, promptId) {
    const res = await fetch(`${API_BASE}/final-prompts/exec`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ chatId, promptId })
    });
    return await res.json();
}

export async function fetchActiveModes(chatId) {
    const res = await fetch(`${API_BASE}/chats/${chatId}/modes`);
    return await res.json();
}
