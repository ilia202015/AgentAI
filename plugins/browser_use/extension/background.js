const SERVER_URL = 'http://localhost:8080';

async function register() {
    try {
        const response = await fetch(`${SERVER_URL}/api/browser/register`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status: 'ready' })
        });
        const data = await response.json();
        console.log('✅ Registered:', data);
    } catch (error) {
        console.error('❌ Registration failed:', error);
        setTimeout(register, 5000);
    }
}

async function poll() {
    try {
        const response = await fetch(`${SERVER_URL}/api/browser/poll`);
        const command = await response.json();
        
        if (command && command.type !== 'noop') {
            console.log('📥 Received command:', command);
            handleCommand(command);
        }
    } catch (error) {
        // console.error('❌ Polling error:', error);
        await new Promise(r => setTimeout(r, 5000));
    }
    poll(); // Continue loop
}

async function handleCommand(command) {
    let result = { request_id: command.request_id, status: 'error', message: 'Unknown command' };
    
    try {
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
        
        if (command.type === 'get_tabs') {
            const tabs = await chrome.tabs.query({});
            result = { 
                request_id: command.request_id, 
                status: 'success', 
                data: tabs.map(t => ({ id: t.id, url: t.url, title: t.title })) 
            };
        } else if (command.type === 'open_url') {
            const url = command.params.url;
            await chrome.tabs.create({ url: url });
            result = { request_id: command.request_id, status: 'success', data: { message: `Opened ${url}` } };
        } else if (command.type === 'get_state') {
            if (!tab) throw new Error("No active tab found");
            const response = await chrome.tabs.sendMessage(tab.id, { action: "getPageData" });
            result = { request_id: command.request_id, status: 'success', data: response };
        } else if (command.type === 'execute_batch') {
            if (!tab) throw new Error("No active tab found");
            const response = await chrome.tabs.sendMessage(tab.id, { 
                action: "execute_batch", 
                commands: command.params.commands 
            });
            result = { request_id: command.request_id, status: 'success', data: response };
        } else if (command.type === 'get_raw_html') {
             if (!tab) throw new Error("No active tab found");
             const response = await chrome.scripting.executeScript({
                target: { tabId: tab.id },
                func: (selector) => {
                    if (selector) {
                        const el = document.querySelector(selector);
                        return el ? el.outerHTML : "Element not found";
                    }
                    return document.documentElement.outerHTML;
                },
                args: [command.params.selector]
             });
             result = { request_id: command.request_id, status: 'success', data: { html: response[0].result } };
        }
    } catch (e) {
        result = { request_id: command.request_id, status: 'error', message: e.toString() };
    }

    sendResponse(result);
}

async function sendResponse(data) {
    try {
        await fetch(`${SERVER_URL}/api/browser/respond`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        console.log('📤 Response sent');
    } catch (error) {
        console.error('❌ Failed to send response:', error);
    }
}

// Start
register();
poll();