import { mkdirSync, writeFileSync } from 'node:fs';

mkdirSync('dist', { recursive: true });

const html = `<!doctype html>
<html lang="tr">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>Online Sanat Galerisi</title>
<style>
body{font-family:Inter,Arial,sans-serif;margin:0;background:#f8fafc;color:#0f172a}
.header{background:linear-gradient(135deg,#4338ca,#7c3aed);color:#fff;padding:28px}
.wrap{max-width:1100px;margin:0 auto;padding:24px}
.grid{display:grid;gap:16px;grid-template-columns:repeat(auto-fit,minmax(240px,1fr))}
.card{background:#fff;border:1px solid #e2e8f0;border-radius:14px;padding:16px;box-shadow:0 2px 8px rgba(0,0,0,.04)}
.small{color:#475569;font-size:14px}
</style>
</head>
<body>
<div class="header"><div class="wrap"><h1>Online Sanat Galerisi</h1><p>Build çıktısı: UI iskeleti başarıyla üretildi.</p></div></div>
<div class="wrap">
<h2>Öne Çıkan Eserler</h2>
<div class="grid">
<div class="card"><h3>Yıldızlı Gece</h3><p class="small">Van Gogh</p></div>
<div class="card"><h3>Mona Lisa</h3><p class="small">Da Vinci</p></div>
<div class="card"><h3>Soyut Harmoni</h3><p class="small">Aylin Demir</p></div>
</div>
<h2 style="margin-top:28px">Etkinlikler</h2>
<div class="grid">
<div class="card"><h3>Modern Art Night</h3><p class="small">İstanbul • 2026-01-01</p></div>
<div class="card"><h3>Renaissance Workshop</h3><p class="small">Ankara • 2026-02-15</p></div>
</div>
</div>
</body>
</html>`;

writeFileSync('dist/index.html', html);
console.log('Static dist prepared at frontend/dist');
