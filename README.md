# Centelha

App gratuito de audiolivros espíritas (iOS e Android) com as obras de Allan Kardec em domínio público, narradas com TTS e revisadas por pessoas. Inclui leitura acompanhada, uso offline e perfis Jovem e Kids com a mascote Clara.

Por enquanto o repositório tem só a documentação inicial e a identidade visual. Ainda não há código.

## Conteúdo

- `docs-iniciais/MDs/` — especificação da plataforma, análise de concorrentes, plano de redes sociais, site e landing page, prompts de logo e mascote.
- `docs-iniciais/centelho-brand/` — brand package v1: logos, ícones de app, ícones de interface, mockups, templates para redes sociais e design tokens (CSS, JSON, Flutter).
- `docs-iniciais/imagens/` — referências raster originais.

## Stack prevista

FastAPI + PostgreSQL + Redis/Celery (API e pipeline de TTS), Next.js (admin), Flutter (app), Cloudflare R2 e CDN.
