# 0002 — Astro para o site www

Data: 2026-10-05 · Status: aceita (#16)

## Contexto

O site precisa de páginas rápidas e lidas pelo Google: landing, páginas legais e, na Fase 1, mais de mil páginas de questões e capítulos geradas a partir da API. A especificação deixava em aberto Next.js ou Astro.

## Decisão

Astro com saída estática, servido por nginx em container próprio. JavaScript só onde há interação (player de demonstração, formulário, tema).

## Consequências

- Build gera HTML puro; cada publicação no admin dispara rebuild (ou rebuild parcial) do site.
- O admin pode seguir em Next.js sem compartilhar código com o site.
