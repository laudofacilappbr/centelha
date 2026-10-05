// @ts-check
import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';
import { loadEnv } from 'vite';

const env = loadEnv(process.env.NODE_ENV ?? 'production', process.cwd(), '');
const SITE_URL = env.SITE_URL || 'https://centelha.com.br'; // TODO: domínio definitivo
const API_URL = (env.PUBLIC_API_URL || '').replace(/\/+$/, '');
let apiOrigin = '';
try {
  apiOrigin = API_URL ? new URL(API_URL).origin : '';
} catch {
  apiOrigin = '';
}
// Origem do storage de áudio (faixas dos capítulos), ex.: https://audio.centelha.com.br
let audioOrigin = '';
try {
  audioOrigin = env.AUDIO_URL ? new URL(env.AUDIO_URL).origin : '';
} catch {
  audioOrigin = '';
}
const plausible = env.PUBLIC_PLAUSIBLE_DOMAIN ? ' https://plausible.io' : '';

export default defineConfig({
  site: SITE_URL,
  output: 'static',
  markdown: { syntaxHighlight: false },
  trailingSlash: 'never',
  build: { format: 'file' },
  integrations: [
    sitemap({
      filter: (page) => !page.endsWith('/404'),
    }),
  ],
  security: {
    // Astro gera um <meta http-equiv="Content-Security-Policy"> com hashes
    // dos scripts e estilos que ele mesmo emite. O nginx complementa com
    // frame-ancestors e demais cabeçalhos (ver nginx.conf).
    csp: {
      algorithm: 'SHA-256',
      directives: [
        "default-src 'self'",
        "img-src 'self' data:",
        "font-src 'self'",
        `media-src 'self'${audioOrigin ? ' ' + audioOrigin : ''}`,
        `connect-src 'self'${apiOrigin ? ' ' + apiOrigin : ''}${plausible}`,
        "base-uri 'self'",
        "form-action 'self'",
        "object-src 'none'",
      ],
      scriptDirective: { resources: ["'self'", ...(plausible ? ['https://plausible.io'] : [])] },
      styleDirective: { resources: ["'self'"] },
    },
  },
});
