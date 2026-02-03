/**
 * content.js - Browser Use Plugin (MV3)
 * Provides DOM analysis, interactive element detection, and visual labeling.
 */

(function() {
    let labels = [];

    /**
     * Extracts and cleans the current page HTML.
     */
    function getCleanHTML() {
        try {
            const clone = document.documentElement.cloneNode(true);
            const toRemove = clone.querySelectorAll('script, style, link[rel="stylesheet"], noscript, svg, iframe, object, embed');
            toRemove.forEach(el => el.remove());
            
            function cleanNode(node) {
                if (node.nodeType === Node.TEXT_NODE) {
                    const text = node.textContent.trim();
                    if (text.length > 200) {
                        node.textContent = text.substring(0, 200) + '...';
                    }
                } else if (node.nodeType === Node.ELEMENT_NODE) {
                    const attrs = node.attributes;
                    for (let i = attrs.length - 1; i >= 0; i--) {
                        const attrName = attrs[i].name;
                        if (attrName.startsWith('on') || 
                            ['style', 'srcset', 'crossorigin', 'integrity'].includes(attrName)) {
                            node.removeAttribute(attrName);
                        }
                    }
                    node.childNodes.forEach(cleanNode);
                }
            }
            
            cleanNode(clone);
            return clone.outerHTML;
        } catch (error) {
            console.error('[Browser Use] Error in getCleanHTML:', error);
            return '<html><body>Error parsing page content</body></html>';
        }
    }

    function isVisible(el) {
        try {
            const style = window.getComputedStyle(el);
            const rect = el.getBoundingClientRect();
            return (
                style.display !== 'none' && 
                style.visibility !== 'hidden' && 
                style.opacity !== '0' &&
                rect.width > 0 &&
                rect.height > 0
            );
        } catch (e) {
            return false;
        }
    }

    function getInteractiveElements() {
        const elements = [];
        const selector = 'button, a, input, select, textarea, [role="button"], [onclick], [contenteditable="true"]';
        const rawElements = document.querySelectorAll(selector);
        
        let idCounter = 0;
        rawElements.forEach(el => {
            try {
                if (isVisible(el)) {
                    const rect = el.getBoundingClientRect();
                    const labelId = idCounter++;
                    el.setAttribute('data-browser-id', labelId);

                    elements.push({
                        id: labelId,
                        tagName: el.tagName,
                        text: (el.innerText || el.value || el.placeholder || '').substring(0, 100).trim(),
                        rect: {
                            top: Math.round(rect.top + window.scrollY),
                            left: Math.round(rect.left + window.scrollX),
                            width: Math.round(rect.width),
                            height: Math.round(rect.height)
                        }
                    });
                    drawLabel(el, labelId);
                }
            } catch (err) {
                console.warn('[Browser Use] Could not parse element:', el, err);
            }
        });
        return elements;
    }

    function drawLabel(el, id) {
        const rect = el.getBoundingClientRect();
        const label = document.createElement('div');
        label.className = 'bu-element-label';
        label.innerText = id;

        const styles = {
            'position': 'absolute',
            'top': (rect.top + window.scrollY) + 'px',
            'left': (rect.left + window.scrollX) + 'px',
            'background-color': '#ff0000',
            'color': '#ffffff',
            'font-size': '12px',
            'font-weight': 'bold',
            'padding': '2px 4px',
            'z-index': '2147483647',
            'pointer-events': 'none',
            'border-radius': '3px',
            'border': '1px solid white',
            'line-height': '1',
            'font-family': 'Arial, sans-serif',
            'box-shadow': '0 0 2px black'
        };

        for (const [prop, val] of Object.entries(styles)) {
            label.style.setProperty(prop, val, 'important');
        }
        document.body.appendChild(label);
        labels.push(label);
    }

    function clearLabels() {
        labels.forEach(l => {
            try { l.remove(); } catch (e) {}
        });
        labels = [];
    }

    async function executeActions(actions) {
        const results = [];
        for (const action of actions) {
            try {
                let res = await executeSingleAction(action);
                results.push({ action: action.type, status: 'success', detail: res });
                if (action.type !== 'wait') {
                    await new Promise(r => setTimeout(r, 300));
                }
            } catch (err) {
                results.push({ action: action.type, status: 'error', message: err.toString() });
                break; 
            }
        }
        return results;
    }

    async function executeSingleAction(action) {
        const getEl = () => {
            const el = document.querySelector(`[data-browser-id="${action.id}"]`);
            if (!el) throw new Error(`Element with browser-id ${action.id} not found`);
            return el;
        };

        switch (action.type) {
            case 'click': {
                const el = getEl();
                el.scrollIntoView({ behavior: 'instant', block: 'center' });
                
                // Final QA Improvement: Use pointer events for modern apps
                el.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true, cancelable: true, pointerType: 'mouse' }));
                el.dispatchEvent(new PointerEvent('pointerup', { bubbles: true, cancelable: true, pointerType: 'mouse' }));
                el.click();
                
                return 'Clicked';
            }
            case 'type': {
                const el = getEl();
                el.scrollIntoView({ behavior: 'instant', block: 'center' });
                el.focus();
                
                if (action.text) {
                    // Modern input handling via insertText
                    document.execCommand('insertText', false, action.text);
                    el.dispatchEvent(new Event('input', { bubbles: true }));
                    el.dispatchEvent(new Event('change', { bubbles: true }));
                }

                if (action.enter) {
                    el.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true }));
                    el.dispatchEvent(new KeyboardEvent('keypress', { key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true }));
                    el.dispatchEvent(new KeyboardEvent('keyup', { key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true }));
                }
                return 'Typed: ' + (action.text || '') + (action.enter ? ' + Enter' : '');
            }
            case 'scroll': {
                window.scrollBy({ top: action.y || 0, left: action.x || 0, behavior: 'smooth' });
                return `Scrolled x:${action.x || 0} y:${action.y || 0}`;
            }
            case 'wait': {
                await new Promise(r => setTimeout(r, action.ms || 1000));
                return `Waited ${action.ms || 1000}ms`;
            }
            default:
                throw new Error(`Unknown action type: ${action.type}`);
        }
    }

    chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
        if (request.action === "getPageData") {
            clearLabels();
            const elements = getInteractiveElements();
            const html = getCleanHTML();
            sendResponse({ html: html, elements: elements, url: window.location.href, title: document.title });
        } else if (request.action === "execute_batch") {
            executeActions(request.commands).then(results => {
                clearLabels();
                const elements = getInteractiveElements();
                const html = getCleanHTML();
                sendResponse({ results: results, state: { html: html, elements: elements, url: window.location.href, title: document.title } });
            }).catch(err => {
                sendResponse({ error: err.toString() });
            });
        }
        return true;
    });
})();