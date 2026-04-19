const SERVER_URL = "http://127.0.0.1:8085";
let targetTabId = null;

async function sendCDP(tabId, method, params = {}) {
    return new Promise((resolve, reject) => {
        chrome.debugger.sendCommand({ tabId }, method, params, (res) => {
            if (chrome.runtime.lastError) {
                reject(new Error(chrome.runtime.lastError.message));
            } else {
                resolve(res);
            }
        });
    });
}

async function attachDebugger(tabId) {
    return new Promise((resolve) => {
        chrome.debugger.getTargets((targets) => {
            let target = targets.find(t => t.tabId === tabId);
            if (target && target.attached) {
                resolve();
            } else {
                chrome.debugger.attach({ tabId }, "1.3", () => {
                    if (chrome.runtime.lastError) console.error(chrome.runtime.lastError);
                    resolve();
                });
            }
        });
    });
}

async function detachDebugger(tabId) {
    return new Promise((resolve) => {
        chrome.debugger.detach({ tabId }, () => {
            resolve();
        });
    });
}

async function executeAction(tabId, action) {
    let result = null;
    if (action.action === "click") {
        let exp = `
            (() => {
                let el = null;
                const sel = "${action.selector}";
                if (sel.startsWith("//")) {
                    el = document.evaluate(sel, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
                } else {
                    el = document.querySelector(sel);
                }
                if (!el) return null;
                el.scrollIntoView({block: 'center', behavior: 'instant'});
                let rect = el.getBoundingClientRect();
                return { x: rect.left + rect.width/2, y: rect.top + rect.height/2 };
            })()
        `;
        let evalRes = await sendCDP(tabId, "Runtime.evaluate", { expression: exp, returnByValue: true });
        if (!evalRes.result || !evalRes.result.value) throw new Error("Element not found: " + action.selector);
        let coords = evalRes.result.value;
        await sendCDP(tabId, "Input.dispatchMouseEvent", { type: "mouseMoved", x: coords.x, y: coords.y });
        await sendCDP(tabId, "Input.dispatchMouseEvent", { type: "mousePressed", x: coords.x, y: coords.y, button: "left", clickCount: 1 });
        await sendCDP(tabId, "Input.dispatchMouseEvent", { type: "mouseReleased", x: coords.x, y: coords.y, button: "left", clickCount: 1 });
    } else if (action.action === "type") {
        if (action.selector) await executeAction(tabId, { action: "click", selector: action.selector });
        await new Promise(r => setTimeout(r, 100));
        for (let char of action.text) await sendCDP(tabId, "Input.dispatchKeyEvent", { type: "char", text: char });
    } else if (action.action === "press") {
         await sendCDP(tabId, "Input.dispatchKeyEvent", { type: "keyDown", commands: [action.key] });
         await sendCDP(tabId, "Input.dispatchKeyEvent", { type: "keyUp", commands: [action.key] });
    } else if (action.action === "search") {
        let query = action.query || action.selector;
        let exp = `
            (() => {
                const results = [];
                const selector = "${query}";
                const elements = document.querySelectorAll(selector);
                elements.forEach(el => {
                    results.push({
                        tag: el.tagName.toLowerCase(),
                        id: el.id,
                        class: el.className,
                        text: el.innerText.substring(0, 100),
                        html: el.outerHTML.substring(0, 200)
                    });
                });
                return results;
            })()
        `;
        let evalRes = await sendCDP(tabId, "Runtime.evaluate", { expression: exp, returnByValue: true });
        result = evalRes.result ? evalRes.result.value : [];
    } else if (action.action === "read") {
        let exp = `
            (() => {
                let el = document.querySelector("${action.selector}");
                return el ? el.innerText : "Element not found";
            })()
        `;
        let evalRes = await sendCDP(tabId, "Runtime.evaluate", { expression: exp, returnByValue: true });
        result = evalRes.result ? evalRes.result.value : "Error reading";
    }
    await new Promise(r => setTimeout(r, 300));
    return result;
}

async function handleCommand(commandData) {
    let msgId = commandData.message_id;
    let result = { status: "success" };
    try {
        if (!targetTabId) {
            let tabs = await chrome.tabs.query({ active: true, currentWindow: true });
            if (!tabs.length) throw new Error("No active tab found");
            targetTabId = tabs[0].id;
        } else {
            try { await chrome.tabs.get(targetTabId); } catch(e) {
                let tabs = await chrome.tabs.query({ active: true, currentWindow: true });
                if (!tabs.length) throw new Error("No active tab");
                targetTabId = tabs[0].id;
            }
        }

        if (commandData.action === "navigate") {
            await chrome.tabs.update(targetTabId, { url: commandData.url, active: true });
            await new Promise(r => {
                let l = (id, info) => { if (id === targetTabId && info.status === 'complete') { chrome.tabs.onUpdated.removeListener(l); r(); } };
                chrome.tabs.onUpdated.addListener(l);
                setTimeout(() => { chrome.tabs.onUpdated.removeListener(l); r(); }, 15000);
            });
            result.message = "Navigated";
        } else if (commandData.action === "execute_actions") {
            await attachDebugger(targetTabId);
            try {
                let results = [];
                for (let a of commandData.actions) {
                    let actionRes = await executeAction(targetTabId, a);
                    results.push(actionRes);
                }
                result.message = "Done";
                result.results = results;
            } finally { await detachDebugger(targetTabId); }
        } else if (commandData.action === "get_dom") {
            let injection = await chrome.scripting.executeScript({
                target: { tabId: targetTabId },
                func: () => {
                    const getDeepText = (root) => {
                        let text = root.body ? root.body.innerText : "";
                        try {
                            const iframes = root.querySelectorAll('iframe');
                            for (let f of iframes) {
                                try {
                                    if (f.contentDocument && f.contentDocument.body) {
                                        text += "\n--- IFRAME: " + (f.id || f.name || "unnamed") + " ---\n" + getDeepText(f.contentDocument);
                                    }
                                } catch(e) { text += "\n[Blocked Iframe: " + f.src + "]"; }
                            }
                        } catch(e) {}
                        return text;
                    };
                    
                    const getInteractive = () => {
                        const els = document.querySelectorAll('button, a, input, select, textarea, [role="button"]');
                        return Array.from(els).map(el => {
                            const rect = el.getBoundingClientRect();
                            return {
                                tag: el.tagName.toLowerCase(),
                                text: (el.innerText || el.value || el.getAttribute('aria-label') || "").trim().substring(0, 100),
                                id: el.id,
                                class: el.className,
                                visible: rect.width > 0 && rect.height > 0
                            };
                        }).filter(e => e.visible);
                    };

                    return {
                        title: document.title,
                        url: window.location.href,
                        fullText: getDeepText(document),
                        interactive: getInteractive()
                    };
                }
            });
            if (injection && injection[0] && injection[0].result) {
                result.data = injection[0].result;
                result.message = "DOM captured";
            } else {
                throw new Error("Injection failed");
            }
        }
    } catch (e) { result = { status: "error", message: e.message }; }
    result.message_id = msgId;
    fetch(SERVER_URL, { method: "POST", body: JSON.stringify(result) }).catch(e => console.error(e));
}

async function pollServer() {
    while (true) {
        try {
            let res = await fetch(SERVER_URL);
            if (res.ok) {
                let d = await res.json();
                if (d.status === "command") await handleCommand(d.data);
            }
        } catch (e) {}
        await new Promise(r => setTimeout(r, 1000));
    }
}
pollServer();