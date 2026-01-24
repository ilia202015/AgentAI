export const bgManager = {
    canvas: null,
    ctx: null,
    animId: null,
    items: [],
    time: 0,
    enabled: false,

    init() {
        if (this.canvas) return;
        this.canvas = document.createElement('canvas');
        this.canvas.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;z-index:0;pointer-events:none;opacity:0;transition:opacity 2s ease;filter:blur(100px) contrast(1.1);';
        
        const isDark = true; // Default to dark for this theme
        if (isDark) {
            this.canvas.style.mixBlendMode = 'screen'; 
            this.canvas.style.opacity = '0.5'; 
        } else {
            this.canvas.style.mixBlendMode = 'multiply';
            this.canvas.style.opacity = '0.7';
        }

        document.body.appendChild(this.canvas);
        setTimeout(() => { if(this.canvas) this.canvas.style.opacity = isDark ? '0.6' : '0.8'; }, 50);

        this.ctx = this.canvas.getContext('2d');
        
        this.resizeHandler = () => {
            if(!this.canvas) return;
            this.canvas.width = window.innerWidth / 4;
            this.canvas.height = window.innerHeight / 4;
        };
        window.addEventListener('resize', this.resizeHandler);
        this.resizeHandler();
        
        this.setupItems();
        this.loop();
        this.enabled = true;
    },

    stop() {
        if (this.animId) cancelAnimationFrame(this.animId);
        if (this.canvas) {
            this.canvas.style.opacity = 0;
            const c = this.canvas;
            setTimeout(() => { if(c) c.remove(); }, 2000);
            this.canvas = null;
        }
        if (this.resizeHandler) window.removeEventListener('resize', this.resizeHandler);
        this.enabled = false;
    },
    
    toggle() {
        if (this.enabled) this.stop();
        else this.init();
        return this.enabled;
    },

    setupItems() {
        this.items = [];
        const colors = [
            {h: 260, s: 70, l: 60}, // Violet
            {h: 210, s: 80, l: 55}, // Blue
            {h: 320, s: 70, l: 55}, // Pink
            {h: 170, s: 80, l: 50}, // Teal
            {h: 280, s: 75, l: 60}  // Purple
        ];
        
        for(let i=0; i<6; i++) {
            this.items.push({
                x: Math.random() * window.innerWidth,
                y: Math.random() * window.innerHeight,
                tOffset: Math.random() * 1000,
                xSpeed: 0.0003 + Math.random() * 0.0005,
                ySpeed: 0.0003 + Math.random() * 0.0005,
                xAmp: window.innerWidth * 0.5, 
                yAmp: window.innerHeight * 0.5,
                r: 300 + Math.random() * 200,
                color: colors[i % colors.length],
                scaleX: 0.8 + Math.random() * 0.4,
                rotationSpeed: (Math.random() - 0.5) * 0.002
            });
        }
    },

    loop() {
        if (!this.canvas) return;
        const ctx = this.ctx;
        const w = this.canvas.width;
        const h = this.canvas.height;
        this.time += 16;
        
        ctx.clearRect(0, 0, w, h);
        const scale = 0.25;
        
        this.items.forEach(p => {
            const xNow = p.x + Math.sin(this.time * p.xSpeed + p.tOffset) * p.xAmp;
            const yNow = p.y + Math.cos(this.time * p.ySpeed + p.tOffset) * p.yAmp;
            const rot = this.time * p.rotationSpeed;
            const hueMod = (p.color.h + this.time * 0.005) % 360;
            
            ctx.save();
            ctx.translate(xNow * scale, yNow * scale);
            ctx.rotate(rot);
            ctx.scale(p.scaleX, 1);
            
            const rAdj = p.r * scale;
            const g = ctx.createRadialGradient(0, 0, 0, 0, 0, rAdj);
            g.addColorStop(0, `hsla(${hueMod}, ${p.color.s}%, ${p.color.l}%, 0.7)`);
            g.addColorStop(1, `hsla(${hueMod}, ${p.color.s}%, ${p.color.l}%, 0)`);
            
            ctx.fillStyle = g;
            ctx.beginPath();
            ctx.arc(0, 0, rAdj, 0, Math.PI * 2);
            ctx.fill();
            ctx.restore();
        });
        
        this.animId = requestAnimationFrame(() => this.loop());
    }
};
