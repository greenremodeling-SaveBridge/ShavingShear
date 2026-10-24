/* 3D 새싹 (three.js). 화면 곳곳의 BuddyBody 가 이 파일을 쓴다.
   - 모든 새싹이 requestAnimationFrame 하나를 같이 쓰고, 화면 밖이거나 탭이 숨겨지면 그리지 않는다.
   - 움직임 줄이기 설정이면 자세만 바뀌고 흔들림·점프·한 바퀴는 없다.
   - 윤곽선 없는 클레이 질감. 모양을 바꾸려면 createBuddy 안의 색·크기 값만 고치면 된다. */
import * as THREE from 'three';

let motion = true;
try {
  const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
  motion = !mq.matches;
  const on = e => { motion = !e.matches; };
  mq.addEventListener ? mq.addEventListener('change', on) : mq.addListener(on);
} catch (e) { /* 그냥 움직임 켬 */ }

const lerp = (a, b, k) => a + (b - a) * k;
const clamp = (v, a, b) => Math.max(a, Math.min(b, v));

function createBuddy(canvas, opts) {
    var renderer;
    try { renderer = new THREE.WebGLRenderer({ canvas: canvas, antialias: true, alpha: true }); }
    catch (e) { return null; }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.setClearColor(0x000000, 0);

    var scene = new THREE.Scene();
    var camera = new THREE.PerspectiveCamera(30, 1, 0.1, 60);
    scene.add(new THREE.HemisphereLight(0xFFFFFF, 0xBCD4A2, 0.76));
    var sun = new THREE.DirectionalLight(0xFFFFFF, 0.5); sun.position.set(-3, 4, 6); scene.add(sun);
    var fill = new THREE.DirectionalLight(0xDDF3E8, 0.22); fill.position.set(4, 0, -3); scene.add(fill);

    var cHoodHi = 0x7DA23F, cHoodLo = 0x557A30, cLeaf = 0x5C9A3A, cLeaf2 = 0x6BA844, cEar = 0xC8DEA6, cBlush = 0xF2B796, cInk = 0x2B2316, cLine = 0x23371A, cVein = 0x58852F;
    var lineMat = new THREE.MeshBasicMaterial({ color: cLine, side: THREE.BackSide });
    var lineFlat = new THREE.MeshBasicMaterial({ color: cLine });
    var gc = document.createElement('canvas'); gc.width = gc.height = 128;
    var gx = gc.getContext('2d'); gx.fillStyle = '#808080'; gx.fillRect(0, 0, 128, 128);
    for (var gi = 0; gi < 2600; gi++) { var gv = 110 + Math.random() * 36; gx.fillStyle = 'rgb(' + gv + ',' + gv + ',' + gv + ')'; gx.beginPath(); gx.arc(Math.random() * 128, Math.random() * 128, 0.8 + Math.random() * 1.6, 0, 6.283); gx.fill(); }
    var grain = new THREE.CanvasTexture(gc); grain.wrapS = grain.wrapT = THREE.RepeatWrapping; grain.repeat.set(5, 4);
    function clay(o) { o.roughness = 0.95; o.metalness = 0; o.bumpMap = grain; o.bumpScale = 0.045; return new THREE.MeshStandardMaterial(o); }
    function lam(c) { return clay({ color: c }); }
    function gsphere(top, bottom) { /* 위는 밝게, 아래는 살짝 어둡게 */
      var g = new THREE.SphereGeometry(1, 56, 40), pos = g.attributes.position, col = new Float32Array(pos.count * 3);
      var ct = new THREE.Color(top), cb = new THREE.Color(bottom), c = new THREE.Color();
      for (var i = 0; i < pos.count; i++) { c.copy(cb).lerp(ct, (pos.getY(i) + 1) / 2); col[i * 3] = c.r; col[i * 3 + 1] = c.g; col[i * 3 + 2] = c.b; }
      g.setAttribute('color', new THREE.BufferAttribute(col, 3)); return g; }
    function outline(m, grow) { return null; /* 윤곽선 없음 */
      var o = new THREE.Mesh(m.geometry, lineMat); o.position.copy(m.position); o.rotation.copy(m.rotation); o.scale.copy(m.scale).multiplyScalar(grow); m.parent.add(o); return o; }
    function part(parent, top, bottom, pos, scl, grow) {
      var m = new THREE.Mesh(gsphere(top, bottom), clay({ vertexColors: true }));
      m.position.set(pos[0], pos[1], pos[2]); m.scale.set(scl[0], scl[1], scl[2]); parent.add(m); if (grow) outline(m, grow); return m; }
    function leafShape(len, wid, g) {
      var s = new THREE.Shape(); s.moveTo(0, 0);
      s.bezierCurveTo(len * 0.15, wid, len * 0.62, wid * 1.1, len, 0);
      s.bezierCurveTo(len * 0.62, -wid * 1.1, len * 0.15, -wid, 0, 0);
      var geo = new THREE.ExtrudeGeometry(s, { depth: 0.05, bevelEnabled: true, bevelThickness: 0.09, bevelSize: 0.06, bevelSegments: 8, curveSegments: 32 });
      geo.translate(0, 0, -0.025); return geo; }
    function leaf(parent, len, wid, color, veinLen) {
      var grp = new THREE.Group(); parent.add(grp);
      grp.add(new THREE.Mesh(leafShape(len, wid, 0), lam(color)));
      if (veinLen) { var v = new THREE.Mesh(new THREE.BoxGeometry(len * veinLen, 0.02, 0.012), new THREE.MeshBasicMaterial({ color: cVein })); v.position.set(len * (0.1 + veinLen / 2), 0, 0.128); grp.add(v); }
      return grp; }

    var root = new THREE.Group(); scene.add(root);

    /* 그림자 */
    var sc = document.createElement('canvas'); sc.width = sc.height = 64;
    var sx = sc.getContext('2d'), gr = sx.createRadialGradient(32, 32, 2, 32, 32, 30);
    gr.addColorStop(0, 'rgba(20,50,40,0.42)'); gr.addColorStop(1, 'rgba(20,50,40,0)');
    sx.fillStyle = gr; sx.fillRect(0, 0, 64, 64);
    var shadow = new THREE.Mesh(new THREE.PlaneGeometry(2.8, 2.8), new THREE.MeshBasicMaterial({ map: new THREE.CanvasTexture(sc), transparent: true, depthWrite: false }));
    shadow.rotation.x = -Math.PI / 2; shadow.position.y = -1.93; scene.add(shadow);

    /* 몸: 작고 통통하게 */
    var BT = 0xE0EFC8, BB = 0xC9DEA8;
    part(root, BT, BB, [0, -1.3, 0], [0.42, 0.44, 0.38], 1.1);
    [-1, 1].forEach(function (s) {
      part(root, BT, BB, [s * 0.17, -1.68, 0], [0.15, 0.2, 0.15], 1.2);
      part(root, BT, BB, [s * 0.18, -1.84, 0.08], [0.2, 0.11, 0.26], 1.17);
    });
    function makeArm(side) {
      var piv = new THREE.Group(); piv.position.set(side * 0.36, -1.17, 0.02); root.add(piv);
      part(piv, BT, BB, [0, -0.25, 0], [0.135, 0.36, 0.135], 1.22);
      part(piv, BT, BB, [0, -0.52, 0], [0.165, 0.165, 0.165], 1.2);
      return piv;
    }
    var armR = makeArm(1), armL = makeArm(-1);

    /* 목 둘레 잎 */
    var collarLeaf = leafShape(0.4, 0.12, 0);
    for (var i = 0; i < 9; i++) {
      var an = (i / 9) * Math.PI * 2;
      var g1 = new THREE.Group(); g1.position.set(Math.sin(an) * 0.33, -1.0, Math.cos(an) * 0.3); g1.rotation.y = an - Math.PI / 2;
      var g2 = new THREE.Group(); g2.rotation.z = -0.55; g1.add(g2);
      var m2 = new THREE.Mesh(collarLeaf, lam(i % 2 ? cLeaf : cLeaf2)); m2.rotation.x = Math.PI / 2; g2.add(m2);
      root.add(g1);
    }

    /* 머리: 동글동글한 씨앗 모양 모자 */
    var head = new THREE.Group(); root.add(head);
    var prof = [];
    for (var j = 0; j <= 32; j++) { var aa = -Math.PI / 2 + (j / 32) * (Math.PI / 2 + 0.55); prof.push(new THREE.Vector2(Math.max(0, Math.cos(aa)), Math.sin(aa) * 0.97)); }
    var tipPts = new THREE.SplineCurve([new THREE.Vector2(0.852, 0.51), new THREE.Vector2(0.7, 0.82), new THREE.Vector2(0.47, 1.08), new THREE.Vector2(0.23, 1.26), new THREE.Vector2(0.075, 1.36), new THREE.Vector2(0.0, 1.4)]).getPoints(22);
    tipPts.shift(); prof = prof.concat(tipPts);
    var hoodGeo = new THREE.LatheGeometry(prof, 96), hp = hoodGeo.attributes.position, hcol = new Float32Array(hp.count * 3), hc = new THREE.Color(), hA = new THREE.Color(cHoodHi), hB = new THREE.Color(cHoodLo);
    for (var q = 0; q < hp.count; q++) { var tt = THREE.MathUtils.clamp(0.5 + (-hp.getX(q) * 0.32 + hp.getY(q) * 0.26 + hp.getZ(q) * 0.16), 0, 1); hc.copy(hB).lerp(hA, tt); hcol[q * 3] = hc.r; hcol[q * 3 + 1] = hc.g; hcol[q * 3 + 2] = hc.b; }
    hoodGeo.setAttribute('color', new THREE.BufferAttribute(hcol, 3));
    var HX = 1.22;
    var hood = new THREE.Mesh(hoodGeo, clay({ vertexColors: true, side: THREE.DoubleSide })); hood.scale.set(HX, 1, 1); head.add(hood);

    /* 잎맥(모자 가운데 선) */
    function hoodR(y) { for (var k = 1; k < prof.length; k++) { if (prof[k].y >= y) { var a = prof[k - 1], b = prof[k], f = (y - a.y) / Math.max(1e-6, b.y - a.y); return a.x + (b.x - a.x) * f; } } return 0; }
    var vp = []; for (var vy = 0.62; vy <= 1.28; vy += 0.05) { var vx = -0.1 * Math.pow((1.3 - vy) / 0.7, 2), rr = hoodR(vy); vp.push(new THREE.Vector3(vx * 1.0, vy, Math.sqrt(Math.max(0, rr * rr - Math.pow(vx / HX, 2))) + 0.006)); }
    head.add(new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(vp), 24, 0.014, 6, false), new THREE.MeshBasicMaterial({ color: cVein })));

    /* 윤기 */
    [[-0.5, 0.64, 0.5, 0.17, 0.09], [-0.72, 0.36, 0.55, 0.065, 0.045], [-0.34, 0.8, 0.45, 0.04, 0.03]].forEach(function (h) {
      var n = new THREE.Vector3(h[0], h[1], h[2]).normalize();
      var hl = new THREE.Mesh(new THREE.CircleGeometry(1, 24), new THREE.MeshBasicMaterial({ color: 0xF1F6C6, transparent: true, opacity: 0.45 }));
      hl.position.copy(n).multiplyScalar(1.03); hl.position.x *= HX; hl.quaternion.setFromUnitVectors(new THREE.Vector3(0, 0, 1), n); hl.scale.set(h[3], h[4], 1); head.add(hl);
    });

    /* 얼굴 창 */
    var faceM = part(head, 0xE4F1CC, 0xCDE2AB, [0, -0.18, 0.45], [0.95, 0.8, 0.7], 0);
    var seam = new THREE.Mesh(faceM.geometry, new THREE.MeshBasicMaterial({ color: 0x5E8333, side: THREE.BackSide })); seam.position.copy(faceM.position); seam.scale.copy(faceM.scale).multiplyScalar(1.045); head.add(seam);
    function faceZ(x, y) { var a = x / 0.95, b = (y + 0.18) / 0.8; return 0.45 + 0.7 * Math.sqrt(Math.max(1 - a * a - b * b, 0)); }

    /* 이마 위 뾰족한 홈: 얼굴 표면에 붙는 판 */
    function notch(grow, dz, mat) {
      var rows = 12, cols = 10, pos = [], idx = [];
      for (var r = 0; r <= rows; r++) {
        var y = 0.1 + (r / rows) * 0.4, hw = 0.42 * Math.pow((y - 0.1) / 0.35, 0.72) + (r ? grow : 0);
        for (var c = 0; c <= cols; c++) { var x = -hw + (2 * hw * c) / cols, yy = y - grow * 1.3; pos.push(x, yy, faceZ(x, yy) + dz); }
      }
      for (var r2 = 0; r2 < rows; r2++) for (var c2 = 0; c2 < cols; c2++) { var a = r2 * (cols + 1) + c2, b = a + 1, c = a + cols + 1, d = c + 1; idx.push(a, c, b, b, c, d); }
      var g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3)); g.setIndex(idx); g.computeVertexNormals();
      var m = new THREE.Mesh(g, mat); head.add(m); }
    notch(0, 0.026, clay({ color: 0x739838, side: THREE.DoubleSide }));

    /* 잎사귀 귀 */
    var earR = new THREE.Group(), earL = new THREE.Group();
    earR.position.set(1.08, -0.12, 0.03); earL.position.set(-1.08, -0.12, 0.03); earL.scale.x = -1; head.add(earR); head.add(earL);
    leaf(earR, 0.92, 0.27, cEar, 0.6); leaf(earL, 0.92, 0.27, cEar, 0.6);

    /* 새싹 */
    var stem = new THREE.Mesh(new THREE.CylinderGeometry(0.06, 0.075, 0.3, 18), lam(cLeaf)); stem.position.set(0, 1.5, 0); head.add(stem);
    var sprout = new THREE.Group(); sprout.position.set(0, 1.63, 0); head.add(sprout);
    var leafR = new THREE.Group(), leafL = new THREE.Group(); leafL.scale.x = -1; sprout.add(leafR); sprout.add(leafL);
    leaf(leafR, 0.86, 0.3, cLeaf, 0.62); leaf(leafL, 0.86, 0.3, cLeaf, 0.62);

    /* 얼굴 */
    var eyes = new THREE.Group(); head.add(eyes);
    var eyeE = [], eyeA = [];
    [-1, 1].forEach(function (s) {
      var g = new THREE.Group(); g.position.set(s * 0.41, -0.22, 1.075); eyes.add(g);
      var e = new THREE.Mesh(new THREE.SphereGeometry(1, 28, 20), new THREE.MeshBasicMaterial({ color: cInk })); e.scale.set(0.12, 0.14, 0.045); g.add(e); eyeE.push(e);
      var ar = new THREE.Mesh(new THREE.TorusGeometry(0.1, 0.03, 12, 28, Math.PI), new THREE.MeshBasicMaterial({ color: cInk })); ar.position.set(0, -0.045, 0.01); ar.visible = false; g.add(ar); eyeA.push(ar);
    });
    var blushes = [-1, 1].map(function (s) {
      var b = new THREE.Mesh(new THREE.SphereGeometry(1, 24, 16), clay({ color: cBlush })); b.scale.set(0.19, 0.115, 0.03); b.position.set(s * 0.7, -0.4, 0.86); b.rotation.y = s * 0.75; head.add(b); return b;
    });
    var smile = new THREE.Mesh(new THREE.TorusGeometry(0.09, 0.021, 10, 28, Math.PI), new THREE.MeshBasicMaterial({ color: cInk })); smile.rotation.z = Math.PI; smile.position.set(0, -0.36, 1.12); head.add(smile);
    var open = new THREE.Mesh(new THREE.SphereGeometry(0.1, 20, 16), new THREE.MeshBasicMaterial({ color: 0x5B2A2A })); open.position.set(0, -0.42, 1.1); open.visible = false; head.add(open);
    var grin = new THREE.Group(); grin.position.set(0, -0.33, 1.125); grin.visible = false; head.add(grin);
    var gm = new THREE.Mesh(new THREE.CircleGeometry(0.135, 28, Math.PI, Math.PI), new THREE.MeshBasicMaterial({ color: 0x4E2222, side: THREE.DoubleSide })); grin.add(gm);
    var tg0 = new THREE.Mesh(new THREE.CircleGeometry(0.07, 20, Math.PI, Math.PI), new THREE.MeshBasicMaterial({ color: 0xE98A8A, side: THREE.DoubleSide })); tg0.position.set(0, -0.052, 0.003); grin.add(tg0);
    var gl = new THREE.Mesh(new THREE.TorusGeometry(0.135, 0.018, 8, 28, Math.PI), new THREE.MeshBasicMaterial({ color: cInk })); gl.rotation.z = Math.PI; grin.add(gl);

    var P = { aRz: 0.8, aRx: 0, aLz: -0.8, aLx: 0, tilt: 0, lookX: 0, lookY: 0, eyeY: 1, mouthW: 0, mouthH: 0, lift: 0, back: 0, leaf: 0 };
    var mood = 'idle', moodStart = 0, spinStart = -10, nextBlink = 2, blinkAt = -10, pointer = { x: 0, y: 0 }, visible = true;

    function fit() {
      var r = canvas.getBoundingClientRect(), w = Math.max(1, r.width), h = Math.max(1, r.height), asp = w / h;
      renderer.setSize(w, h, false); camera.aspect = asp;
      var d = Math.max(opts.dist, opts.wide / asp);
      camera.position.set(0, opts.lookY + 0.15, d); camera.lookAt(0, opts.lookY, 0); camera.updateProjectionMatrix();
    }
    fit();
    var ro = window.ResizeObserver ? new ResizeObserver(fit) : null; if (ro) ro.observe(canvas);
    var io = window.IntersectionObserver ? new IntersectionObserver(function (e) { visible = e[0].isIntersecting; }) : null; if (io) io.observe(canvas);

    function setMood(m, now) { mood = m; moodStart = now; if (m === 'spin') spinStart = now; }
    function spin(now) { spinStart = now; }

    function frame(t, dt) {
      if (!visible) return;
      var m = motion ? 1 : 0, dm = t - moodStart;
      var tg = { aRz: 0.8, aRx: 0, aLz: -0.8, aLx: 0, tilt: 0, eyeY: 1, mouthW: 0, mouthH: 0, lift: 0, back: 0, leaf: Math.sin(t * 2.2) * 0.07 * m };
      var lookOn = true;

      if (mood === 'idle') { tg.aLz = -1.95 + Math.sin(t * 3.2) * 0.12 * m; }
      else if (mood === 'wave') { tg.aRz = 1.9 + Math.sin(t * 9) * 0.3 * m; tg.tilt = 0.09; tg.leaf = Math.sin(t * 5) * 0.1 * m; }
      else if (mood === 'think') { tg.aRx = -1.95; tg.aRz = -0.45; tg.tilt = 0.18; lookOn = false; tg.leaf = Math.sin(t * 1.4) * 0.12 * m; }
      else if (mood === 'cheer') { tg.aRz = 2.05 + Math.sin(t * 8) * 0.14 * m; tg.aLz = -2.05 - Math.sin(t * 8) * 0.14 * m; tg.lift = Math.abs(Math.sin(t * 5.5)) * 0.34 * m; tg.tilt = Math.sin(t * 5.5) * 0.05 * m; tg.leaf = Math.sin(t * 8) * 0.16 * m; }
      else if (mood === 'surprise') { tg.eyeY = 1.3; tg.mouthW = 0.07; tg.mouthH = 0.1; tg.back = 0.14; tg.aRz = 0.95; tg.aLz = -0.95; tg.lift = 0.3 * Math.exp(-3 * dm) * Math.abs(Math.sin(dm * 10)) * m; tg.leaf = 0.2 + Math.sin(t * 20) * 0.04 * m; }

      var sp = (t - spinStart) / 0.95, ry = 0, spinning = motion && sp >= 0 && sp < 1;
      if (spinning) { var e = 1 - Math.pow(1 - sp, 3); ry = e * Math.PI * 2; tg.lift += Math.sin(sp * Math.PI) * 0.5; tg.aRz = 1.7; tg.aLz = -1.7; }
      var happy = mood === 'cheer' || spinning;

      if (t > nextBlink) { blinkAt = t; nextBlink = t + 2.2 + Math.random() * 2.5; }
      var bl = motion ? clamp(1 - Math.sin(clamp((t - blinkAt) / 0.14, 0, 1) * Math.PI), 0.08, 1) : 1;

      var lx = lookOn ? pointer.x : 0.35, ly = lookOn ? pointer.y : 0.5;
      tg.lookX = motion ? lx : 0; tg.lookY = motion ? ly : 0;
      var k = 1 - Math.exp(-dt * (motion ? 10 : 30));
      for (var key in tg) P[key] = lerp(P[key] === undefined ? tg[key] : P[key], tg[key], k);

      var bob = Math.sin(t * 2.4) * 0.035 * m, lift = P.lift + bob;
      root.position.y = Math.max(0, lift);
      root.rotation.y = ry;
      var squash = 1 + (lift > 0 ? -0.02 : 0.025) + Math.sin(t * 2.4 + 1) * 0.012 * m;
      root.scale.set(1 / Math.sqrt(squash), squash, 1 / Math.sqrt(squash));
      shadow.scale.setScalar(1 - clamp(root.position.y, 0, 0.8) * 0.45);
      shadow.material.opacity = 1 - clamp(root.position.y, 0, 0.8) * 0.5;

      head.rotation.set(-P.lookY * 0.3 - P.back, P.lookX * 0.45, P.tilt);
      eyes.position.set(P.lookX * 0.05, P.lookY * 0.04, 0);
      for (var ei = 0; ei < 2; ei++) { eyeE[ei].visible = !happy; eyeE[ei].scale.set(0.12, 0.14 * P.eyeY * bl, 0.045); eyeA[ei].visible = happy; }
      var surp = mood === 'surprise';
      open.visible = surp && !happy; grin.visible = happy; smile.visible = !happy && !surp;
      if (surp) open.scale.set(P.mouthW / 0.1, P.mouthH / 0.1, 0.5);
      var bs = happy ? 1.15 : 1; blushes.forEach(function (b) { b.scale.x = lerp(b.scale.x, 0.19 * bs, 0.2); b.scale.y = lerp(b.scale.y, 0.115 * bs, 0.2); });

      armR.rotation.set(P.aRx, 0, P.aRz); armL.rotation.set(P.aLx, 0, P.aLz);
      leafR.rotation.z = 0.5 + P.leaf; leafL.rotation.z = -(0.5 + P.leaf);
      earR.rotation.z = 0.55 + P.leaf * 1.3; earL.rotation.z = -(0.55 + P.leaf * 1.3);
      sprout.rotation.z = Math.sin(t * 1.3) * 0.05 * m;

      renderer.render(scene, camera);
    }

    var api = {
      canvas: canvas, frame: frame, setMood: setMood, spin: spin,
      setPointer: function (x, y) { pointer.x = x; pointer.y = y; },
      dispose: function () { if (ro) ro.disconnect(); if (io) io.disconnect(); scene.traverse(function (o) { if (o.geometry) o.geometry.dispose(); if (o.material) { (Array.isArray(o.material) ? o.material : [o.material]).forEach(function (mm) { mm.dispose(); }); } }); renderer.dispose(); }
    };
    return api;
  }

/* ---- 새싹들이 같이 쓰는 반복 ---- */
const live = new Set();
let raf = 0, last = 0, pointerBound = false;
const now = () => performance.now() / 1000;

function loop() {
  const t = now(), dt = Math.min(0.05, t - last); last = t;
  live.forEach(b => b.frame(t, dt));
  raf = live.size ? requestAnimationFrame(loop) : 0;
}
function onPointer(e) {
  live.forEach(b => {
    const r = b.canvas.getBoundingClientRect();
    b.setPointer(clamp((e.clientX - (r.left + r.width / 2)) / 420, -1, 1), clamp(-(e.clientY - (r.top + r.height / 2)) / 320, -1, 1));
  });
}

/* canvas 에 새싹을 올린다. WebGL 을 못 쓰면 null (그림으로 대신 보여주면 된다) */
export function mountBuddy(canvas, opts) {
  const b = createBuddy(canvas, opts);
  if (!b) return null;
  live.add(b);
  if (!pointerBound) { window.addEventListener('pointermove', onPointer, { passive: true }); pointerBound = true; }
  if (!raf) { last = now(); raf = requestAnimationFrame(loop); }
  return {
    setMood: m => b.setMood(m, now()),
    spin: () => b.spin(now()),
    unmount: () => { live.delete(b); b.dispose(); if (!live.size && pointerBound) { window.removeEventListener('pointermove', onPointer); pointerBound = false; } },
  };
}

