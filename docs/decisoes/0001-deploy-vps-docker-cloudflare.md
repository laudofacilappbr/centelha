# 0001 — Deploy em VPS própria com Docker por serviço e Cloudflare

Data: 2026-10-05 · Status: aceita

## Contexto

A especificação sugeria hospedagem gerenciada (Cloudflare Pages, banco gerenciado). O projeto prefere controlar a própria infraestrutura e o custo.

## Decisão

- VPS própria; cada serviço em seu container (`site`, `api`, `worker`, `admin`, `postgres`, `redis`), orquestrados por Docker Compose.
- Caddy é o único container com portas expostas. Ele termina TLS com o Origin Certificate da Cloudflare e roteia por subdomínio.
- Cloudflare faz DNS (proxied), TLS de borda, cache e proteção. SSL em modo Full (strict). O firewall da VPS só aceita 443 vindo dos IPs da Cloudflare.
- Imagens construídas no GitHub Actions e publicadas no GHCR; deploy por `docker compose pull && up -d`.
- PostgreSQL e Redis ficam em rede interna, sem acesso externo.

## Consequências

- Backup do PostgreSQL e do storage passa a ser responsabilidade do projeto (#26).
- Limite de taxa em memória na API serve enquanto houver uma réplica; com mais, mover para o Redis.
- O IP do cliente chega em `CF-Connecting-IP`; Caddy só confia nesse cabeçalho vindo das faixas da Cloudflare.
