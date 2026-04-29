export const bgManager = {
    canvas: null,
    ctx: null,
    animId: null,
    items: [],
    time: 0,
    enabled: false,
    currentType: 'none',

    init(type = 'neon') {
        if (type === 'none') {
            this.stop();
            return;
        }
        
        this.currentType = type;
        
        if (!this.canvas) {
            this.canvas = document.createElement('canvas');
            this.canvas.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;z-index:0;pointer-events:none;opacity:0;transition:opacity 2s ease;filter:blur(100px) contrast(1.1);';
            this.canvas.style.mixBlendMode = 'screen'; 
            this.canvas.style.opacity = '0.5'; 

            document.body.appendChild(this.canvas);
            setTimeout(() => { if(this.canvas) this.canvas.style.opacity = '0.6'; }, 50);

            this.ctx = this.canvas.getContext('2d');
            
            this.resizeHandler = () => {
                if(!this.canvas) return;
                this.canvas.width = window.innerWidth / 4;
                this.canvas.height = window.innerHeight / 4;
            };
            window.addEventListener('resize', this.resizeHandler);
            this.resizeHandler();
        }
        
        this.setupItems();
        if (!this.animId) {
            this.loop();
        }
        this.enabled = true;
    },

    stop() {
        if (this.animId) {
            cancelAnimationFrame(this.animId);
            this.animId = null;
        }
        if (this.canvas) {
            this.canvas.style.opacity = 0;
            const c = this.canvas;
            setTimeout(() => { if(c) c.remove(); }, 2000);
            this.canvas = null;
        }
        if (this.resizeHandler) window.removeEventListener('resize', this.resizeHandler);
        this.enabled = false;
        this.currentType = 'none';
    },

    setupItems() {
        this.items = [];
        const colors = [
            {h: 260, s: 70, l: 60},
            {h: 210, s: 80, l: 55},
            {h: 320, s: 70, l: 55},
            {h: 170, s: 80, l: 50},
            {h: 280, s: 75, l: 60} 
        ];
        
        
        this.stars = [];
        for(let i=0; i<200; i++) {
            this.stars.push({
                x: Math.random() * window.innerWidth,
                y: Math.random() * window.innerHeight,
                z: Math.random() * 2, // Глубина (параллакс)
                size: Math.random() * 2 + 0.5,
                speed: (Math.random() * 0.5 + 0.1),
                opacity: Math.random(),
                blinkSpeed: Math.random() * 0.02 + 0.005
            });
        }

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
        
        if (this.currentType === 'neon') {
            this.renderNeon(ctx, w, h);
        } else if (this.currentType === 'grid') {
            this.renderGrid(ctx, w, h);
        } else if (this.currentType === 'stars') {
            this.renderStars(ctx, w, h);
        }
        
        this.animId = requestAnimationFrame(() => this.loop());
    },
    
    
    
    renderStars(ctx, w, h) {
        if (this.canvas.style.filter.includes('blur')) {
            this.canvas.style.filter = 'none';
            this.canvas.style.opacity = '0.8'; 
        }

        ctx.fillStyle = '#030712'; // Темный космос
        ctx.fillRect(0, 0, w, h);
        
        // Немного туманности
        const cx = w/2;
        const cy = h/2;
        const g = ctx.createRadialGradient(cx, cy, 0, cx, cy, Math.max(w, h));
        g.addColorStop(0, 'rgba(30, 27, 75, 0.4)');
        g.addColorStop(0.5, 'rgba(17, 24, 39, 0.2)');
        g.addColorStop(1, 'rgba(3, 7, 18, 0)');
        ctx.fillStyle = g;
        ctx.fillRect(0, 0, w, h);

        this.stars.forEach(star => {
            // Движение (параллакс - ближние летят быстрее)
            star.y -= star.speed * (star.z + 1);
            
            // Мерцание
            star.opacity += Math.sin(this.time * star.blinkSpeed) * 0.05;
            if (star.opacity > 1) star.opacity = 1;
            if (star.opacity < 0.2) star.opacity = 0.2;

            // Возврат сверху вниз
            if (star.y < 0) {
                star.y = h;
                star.x = Math.random() * w;
            }

            ctx.beginPath();
            ctx.arc(star.x, star.y, star.size, 0, Math.PI * 2);
            ctx.fillStyle = `rgba(255, 255, 255, ${star.opacity})`;
            ctx.fill();
            
            // Свечение для крупных звезд
            if (star.size > 1.5) {
                ctx.beginPath();
                ctx.arc(star.x, star.y, star.size * 3, 0, Math.PI * 2);
                ctx.fillStyle = `rgba(167, 139, 250, ${star.opacity * 0.3})`; // Фиолетовый ореол
                ctx.fill();
            }
        });
    },
    renderGrid(ctx, w, h) {
        // Убираем блюр для этого фона, так как сетка должна быть четкой
        if (this.canvas.style.filter.includes('blur')) {
            this.canvas.style.filter = 'none';
            this.canvas.style.opacity = '0.3'; // Чуть прозрачнее
        }

        const horizon = h * 0.4; // Горизонт чуть выше центра
        const perspective = 300;
        
        // Рисуем затухание к горизонту (небо/горизонт)
        const skyGrad = ctx.createLinearGradient(0, 0, 0, horizon);
        skyGrad.addColorStop(0, '#030712'); // Тёмно-синий/черный
        skyGrad.addColorStop(1, '#1e1b4b'); // Фиолетовый оттенок горизонта
        ctx.fillStyle = skyGrad;
        ctx.fillRect(0, 0, w, horizon);

        const groundGrad = ctx.createLinearGradient(0, horizon, 0, h);
        groundGrad.addColorStop(0, '#1e1b4b');
        groundGrad.addColorStop(0.2, '#000000');
        groundGrad.addColorStop(1, '#000000');
        ctx.fillStyle = groundGrad;
        ctx.fillRect(0, horizon, w, h - horizon);

        // Настройки сетки
        ctx.strokeStyle = '#4f46e5'; // Индиго
        ctx.lineWidth = 1;

        const speed = 0.05;
        const zOffset = (this.time * speed) % 50; // Движение вперед

        // Вертикальные линии (уходящие вдаль)
        ctx.beginPath();
        const numVLines = 40;
        for (let i = -numVLines; i <= numVLines; i++) {
            const x = i * 40;
            // Точка на горизонте
            const startX = w / 2 + x;
            const startY = horizon;
            
            // Точка внизу экрана с учетом перспективы
            const endX = w / 2 + x * (h / perspective);
            const endY = h;

            ctx.moveTo(startX, startY);
            ctx.lineTo(endX, endY);
        }
        ctx.stroke();

        // Горизонтальные линии (приближающиеся)
        ctx.beginPath();
        ctx.strokeStyle = '#ec4899'; // Розовый акцент
        const numHLines = 30;
        for (let i = 1; i <= numHLines; i++) {
            let z = i * 50 - zOffset;
            if (z < 1) z = 1; // Защита от деления на 0

            // Расчет позиции Y с учетом перспективы
            // Чем меньше Z, тем ближе линия к низу экрана
            const scale = perspective / z;
            const y = horizon + 50 * scale;

            if (y < horizon || y > h) continue;

            // Расчет X, чтобы линии расходились
            const x1 = w / 2 - (w * scale);
            const x2 = w / 2 + (w * scale);

            // Меняем толщину в зависимости от приближения
            ctx.lineWidth = Math.max(0.5, scale * 1.5);
            ctx.globalAlpha = Math.min(1, Math.max(0, (y - horizon) / (h - horizon))); // Затухание у горизонта
            
            ctx.moveTo(x1, y);
            ctx.lineTo(x2, y);
        }
        ctx.stroke();
        ctx.globalAlpha = 1;
        ctx.lineWidth = 1;
        
        // Солнце в стиле ретровейв
        const sunRadius = 100;
        const sunX = w / 2;
        const sunY = horizon;
        
        const sunGrad = ctx.createLinearGradient(sunX, sunY - sunRadius, sunX, sunY + sunRadius);
        sunGrad.addColorStop(0, '#fde047'); // Желтый
        sunGrad.addColorStop(0.5, '#f97316'); // Оранжевый
        sunGrad.addColorStop(1, '#db2777'); // Розовый
        
        ctx.beginPath();
        ctx.arc(sunX, sunY, sunRadius, Math.PI, 0); // Полукруг над горизонтом
        ctx.fillStyle = sunGrad;
        ctx.fill();
        
        // Полосы на солнце
        ctx.fillStyle = '#030712'; // Цвет фона
        for(let i = 0; i < 5; i++) {
            const barY = sunY - i * 15 - 5;
            const barH = 2 + i * 1.5;
            ctx.fillRect(sunX - sunRadius, barY, sunRadius * 2, barH);
        }
    },
    renderNeon(ctx, w, h) {
        if (this.canvas.style.filter === 'none') {
            this.canvas.style.filter = 'blur(100px) contrast(1.1)';
            this.canvas.style.opacity = '0.6';
        }
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
    }
};