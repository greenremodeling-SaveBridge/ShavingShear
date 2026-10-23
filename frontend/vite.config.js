import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { viteSingleFile } from 'vite-plugin-singlefile';
import { fileURLToPath } from 'node:url';

const here = fileURLToPath(new URL('.', import.meta.url));

// 화면은 한 장짜리 HTML 하나. PC와 모바일이 같은 파일이다.
//   npm run build           →  ../web/index.html          (FastAPI가 web/ 을 그대로 내준다)
//   npm run build:preview   →  ../out/preview/index.html  (서버 없이 저장된 시연 데이터로만 도는 미리보기)
const REACT_CDN = [
  'https://cdnjs.cloudflare.com/ajax/libs/react/18.3.1/umd/react.production.min.js',
  'https://cdnjs.cloudflare.com/ajax/libs/react-dom/18.3.1/umd/react-dom.production.min.js',
];

function reactFromCdn() {
  return {
    name: 'react-from-cdn',
    transformIndexHtml: {
      order: 'post',
      handler: html => html.replace('<title>', REACT_CDN.map(s => `<script src="${s}"></script>`).join('\n') + '\n<title>'),
    },
  };
}

export default defineConfig(({ mode }) => {
  const preview = mode === 'preview';
  return {
    base: './',
    define: { 'import.meta.env.VITE_STANDALONE': JSON.stringify(preview ? '1' : '0') },
    plugins: [react(), viteSingleFile({ removeViteModuleLoader: true }), preview && reactFromCdn()].filter(Boolean),
    build: {
      outDir: preview ? here + '../out/preview' : here + '../dist',
      emptyOutDir: false,
      target: 'es2020',
      assetsInlineLimit: 100_000_000,
      cssCodeSplit: false,
      chunkSizeWarningLimit: 4000,
      rollupOptions: preview ? {
        input: here + 'index.html',
        external: ['react', 'react-dom', 'react-dom/client'],
        output: { format: 'iife', globals: { react: 'React', 'react-dom': 'ReactDOM', 'react-dom/client': 'ReactDOM' } },
      } : { input: here + 'index.html' },
    },
    server: {
      proxy: { '/api': process.env.SS_API || 'http://localhost:8000', '/backup.json': process.env.SS_API || 'http://localhost:8000' },   // SS_API=http://localhost:8130 npm run dev
    },
  };
});
