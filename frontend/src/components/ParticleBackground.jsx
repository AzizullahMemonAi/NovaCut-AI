import React, { useEffect, useRef } from 'react';
import './ParticleBackground.css';

const ParticleBackground = () => {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    let animationFrameId;
    let particles = [];
    let width = 0;
    let height = 0;

    const resize = () => {
      const dpr = window.devicePixelRatio || 1;
      width = window.innerWidth;
      height = window.innerHeight;
      canvas.width = width * dpr;
      canvas.height = height * dpr;
      canvas.style.width = width + 'px';
      canvas.style.height = height + 'px';
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };

    window.addEventListener('resize', resize);
    resize();

    // Three layers: far (tiny, slow, dim), mid, near (larger, slightly faster, brighter)
    const layers = [
      { count: 0.6, sizeRange: [0.3, 0.8], speedRange: [0.03, 0.08], opacityRange: [0.08, 0.2] },  // Far
      { count: 0.3, sizeRange: [0.6, 1.2], speedRange: [0.06, 0.15], opacityRange: [0.15, 0.35] },  // Mid
      { count: 0.1, sizeRange: [1.0, 1.8], speedRange: [0.1, 0.22], opacityRange: [0.25, 0.5] },    // Near
    ];

    const lerp = (a, b, t) => a + (b - a) * t;

    class Star {
      constructor(layer) {
        const t = Math.random();
        this.x = Math.random() * width;
        this.y = Math.random() * height;
        this.size = lerp(layer.sizeRange[0], layer.sizeRange[1], t);
        this.baseOpacity = lerp(layer.opacityRange[0], layer.opacityRange[1], Math.random());
        // Drift direction — mostly upward with slight horizontal wander
        const angle = -Math.PI / 2 + (Math.random() - 0.5) * 1.2;
        const speed = lerp(layer.speedRange[0], layer.speedRange[1], Math.random());
        this.vx = Math.cos(angle) * speed;
        this.vy = Math.sin(angle) * speed;
        // Twinkle
        this.twinkleSpeed = Math.random() * 0.015 + 0.003;
        this.twinklePhase = Math.random() * Math.PI * 2;
      }

      update() {
        this.x += this.vx;
        this.y += this.vy;

        // Wrap
        if (this.y < -2) { this.y = height + 2; this.x = Math.random() * width; }
        if (this.x < -2) this.x = width + 2;
        if (this.x > width + 2) this.x = -2;

        this.twinklePhase += this.twinkleSpeed;
      }

      draw() {
        const twinkle = Math.sin(this.twinklePhase) * 0.5 + 0.5; // 0–1
        const opacity = this.baseOpacity * (0.5 + twinkle * 0.5);

        ctx.beginPath();
        ctx.arc(this.x, this.y, this.size, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(155, 176, 220, ${opacity})`;
        ctx.fill();

        // Very subtle glow on brighter stars
        if (this.size > 1.2 && opacity > 0.3) {
          ctx.beginPath();
          ctx.arc(this.x, this.y, this.size * 2.5, 0, Math.PI * 2);
          ctx.fillStyle = `rgba(139, 164, 255, ${opacity * 0.12})`;
          ctx.fill();
        }
      }
    }

    const initParticles = () => {
      particles = [];
      const area = width * height;
      const totalCount = Math.min(Math.floor(area / 6000), 400);
      
      layers.forEach(layer => {
        const count = Math.floor(totalCount * layer.count);
        for (let i = 0; i < count; i++) {
          particles.push(new Star(layer));
        }
      });
    };

    initParticles();

    const animate = () => {
      ctx.clearRect(0, 0, width, height);
      
      for (let i = 0; i < particles.length; i++) {
        particles[i].update();
        particles[i].draw();
      }
      
      animationFrameId = requestAnimationFrame(animate);
    };

    animate();

    return () => {
      window.removeEventListener('resize', resize);
      cancelAnimationFrame(animationFrameId);
    };
  }, []);

  return (
    <canvas 
      ref={canvasRef}
      className="particle-canvas"
      aria-hidden="true"
    />
  );
};

export default ParticleBackground;
