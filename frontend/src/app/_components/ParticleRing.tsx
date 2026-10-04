"use client";

import { useEffect, useRef } from "react";

// A slowly turning, lumpy ring of points joined by fine lines ("constellation"),
// with a few accent triangles mixed in. Drawn on a canvas; static under reduced motion.

const COUNT = 280;
const TRIANGLE_SHARE = 0.16;
const NODE = "rgba(255, 255, 255, 0.85)";
const ACCENT = "#8FB0FF";

interface Point {
  angle: number;
  radius: number; // as a fraction of the ring radius
  phase: number;
  wobble: number;
  triangle: boolean;
  size: number;
  spin: number;
}

// Small seeded PRNG so the ring looks the same on every load.
function mulberry32(seed: number) {
  return () => {
    seed |= 0;
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function makePoints(): Point[] {
  const rand = mulberry32(7);
  const gauss = () => (rand() + rand() + rand() - 1.5) / 1.5;
  return Array.from({ length: COUNT }, () => {
    const angle = rand() * Math.PI * 2;
    // Low-frequency bumps make the ring irregular, like hand-drawn.
    const lump = 0.07 * Math.sin(3 * angle + 0.6) + 0.05 * Math.sin(5 * angle + 2.1);
    const triangle = rand() < TRIANGLE_SHARE;
    return {
      angle,
      radius: 1 + lump + gauss() * 0.22,
      phase: rand() * Math.PI * 2,
      wobble: 0.6 + rand() * 1.4,
      triangle,
      size: triangle ? 3.2 + rand() * 2.2 : 0.9 + rand() * 0.9,
      spin: (rand() - 0.5) * 0.002,
    };
  });
}

export function ParticleRing({ className }: { className?: string }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return;

    const points = makePoints();
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let size = 0;
    let frame = 0;

    const resize = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      size = canvas.clientWidth;
      canvas.width = size * dpr;
      canvas.height = size * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };

    const draw = (t: number) => {
      const c = size / 2;
      const R = size * 0.34;
      const link = R * 0.22;
      ctx.clearRect(0, 0, size, size);

      const xy = points.map((p) => {
        const a = p.angle + t * 0.00005;
        const r = R * p.radius + Math.sin(t * 0.0009 * p.wobble + p.phase) * R * 0.025;
        return [c + Math.cos(a) * r, c + Math.sin(a) * r];
      });

      ctx.lineWidth = 0.6;
      for (let i = 0; i < xy.length; i++) {
        for (let j = i + 1; j < xy.length; j++) {
          const dx = xy[i][0] - xy[j][0];
          const dy = xy[i][1] - xy[j][1];
          const d = Math.hypot(dx, dy);
          if (d < link) {
            ctx.strokeStyle = `rgba(200, 214, 255, ${(1 - d / link) * 0.45})`;
            ctx.beginPath();
            ctx.moveTo(xy[i][0], xy[i][1]);
            ctx.lineTo(xy[j][0], xy[j][1]);
            ctx.stroke();
          }
        }
      }

      points.forEach((p, i) => {
        const [x, y] = xy[i];
        if (p.triangle) {
          const rot = p.phase + t * p.spin;
          ctx.fillStyle = ACCENT;
          ctx.globalAlpha = 0.85;
          ctx.beginPath();
          for (let k = 0; k < 3; k++) {
            const a = rot + (k * Math.PI * 2) / 3;
            const px = x + Math.cos(a) * p.size;
            const py = y + Math.sin(a) * p.size;
            if (k === 0) ctx.moveTo(px, py);
            else ctx.lineTo(px, py);
          }
          ctx.closePath();
          ctx.fill();
          ctx.globalAlpha = 1;
        } else {
          ctx.fillStyle = NODE;
          ctx.beginPath();
          ctx.arc(x, y, p.size, 0, Math.PI * 2);
          ctx.fill();
        }
      });
    };

    const loop = (t: number) => {
      draw(t);
      frame = requestAnimationFrame(loop);
    };

    resize();
    const observer = new ResizeObserver(() => {
      resize();
      if (reduced) draw(0);
    });
    observer.observe(canvas);

    if (reduced) draw(0);
    else frame = requestAnimationFrame(loop);

    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
    };
  }, []);

  return <canvas ref={canvasRef} className={className} aria-hidden="true" />;
}
