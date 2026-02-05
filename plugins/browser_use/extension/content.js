function isVisible(el) {
    if (!el.offsetParent && el.tagName !== 'BODY') return false;
    const style = window.getComputedStyle(el);
    if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') return false;
    const rect = el.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0;
}

function getInteractiveElements() {
    const all = document.querySelectorAll('*');
    const interactive = [];
    all.forEach(el => {
        if (!isVisible(el)) return;

        const style = window.getComputedStyle(el);
        const isStandard = ['BUTTON', 'A', 'INPUT', 'TEXTAREA', 'SELECT'].includes(el.tagName);
        const isPointer = style.cursor === 'pointer';
        const role = el.getAttribute('role');
        const isRole = role && ['button', 'link', 'checkbox', 'menuitem'].includes(role);

        if (isStandard || isPointer || isRole) {
            let text = el.innerText || el.value || el.placeholder || el.getAttribute('aria-label') || '';
            
            // SVG processing
            const svgs = el.querySelectorAll('svg');
            svgs.forEach(svg => {
                const label = svg.getAttribute('aria-label') || svg.getAttribute('title') || svg.className.baseVal || 'Graphic';
                text += ` [Icon: ${label}]`;
            });

            interactive.push({
                tagName: el.tagName,
                text: text.trim().substring(0, 50),
                id: el.id.substring(0, 40),
                className: (typeof el.className === 'string' ? el.className : '').substring(0, 40),
                rect: el.getBoundingClientRect()
            });
        }
    });
    return interactive;
}

function getCleanHTML() {
    const clone = document.documentElement.cloneNode(true);
    
    // Удаляем скрипты и стили для чистоты
    const scripts = clone.querySelectorAll('script, style');
    scripts.forEach(s => s.remove());

    const walk = document.createTreeWalker(clone, NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT);
    let n;
    while (n = walk.nextNode()) {
        if (n.nodeType === Node.TEXT_NODE) {
            if (n.textContent.length > 500) {
                n.textContent = n.textContent.substring(0, 500) + '...';
            }
        } else if (n.tagName === 'IFRAME') {
            const src = n.src || 'about:blank';
            const placeholder = document.createElement('iframe');
            placeholder.src = src;
            placeholder.innerHTML = '[Internal]'; 
            n.parentNode.replaceChild(placeholder, n);
        }
    }
    return clone.outerHTML;
}

async function executeSingleAction(action) {
    const el = action.selector ? document.querySelector(action.selector) : null;
    
    if (!el && !['js_exec', 'wait', 'scroll'].includes(action.action)) {
        return { error: 'Element not found: ' + action.selector };
    }

    switch (action.action) {
        case 'click':
            el.scrollIntoView({ block: 'center', inline: 'center' });
            el.click();
            return { status: 'clicked' };

        case 'type':
            el.scrollIntoView({ block: 'center', inline: 'center' });
            el.focus();
            el.value = action.text;
            el.dispatchEvent(new Event('input', { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
            return { status: 'typed', text: action.text };

        case 'scroll':
            if (action.direction === 'down') window.scrollBy(0, window.innerHeight * 0.8);
            else if (action.direction === 'up') window.scrollBy(0, -window.innerHeight * 0.8);
            else if (el) el.scrollIntoView({ block: 'center', inline: 'center' });
            return { status: 'scrolled' };

        case 'wait':
            const ms = action.time || 1000;
            await new Promise(resolve => setTimeout(resolve, ms));
            return { status: 'waited', ms };

        case 'hover':
            el.scrollIntoView({ block: 'center', inline: 'center' });
            el.dispatchEvent(new MouseEvent('mouseover', { bubbles: true }));
            el.dispatchEvent(new MouseEvent('mouseenter', { bubbles: true }));
            el.dispatchEvent(new MouseEvent('mousemove', { bubbles: true }));
            return { status: 'hovered' };

        case 'js_exec':
            try {
                const res = new Function(action.text)();
                return { status: 'executed', result: res };
            } catch (e) {
                return { error: 'JS Exec error: ' + e.message };
            }

        case 'get_text':
            return { status: 'success', text: el.innerText || el.value };

        default:
            return { error: 'Unknown action: ' + action.action };
    }
}
