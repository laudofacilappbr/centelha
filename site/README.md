# Centelha — site e landing page

Site estático do Centelha (Astro + TypeScript + CSS puro com os tokens da marca).
Fase 0 + base da Fase 1: landing com lista de espera, `/sobre`, `/como-fazemos`,
`/transparencia`, `/kids` e páginas legais (`/privacidade`, `/termos`, `/suporte`).

## Requisitos

- Node.js 22+ e npm

## Como rodar

```bash
cp .env.example .env      # ajuste as variáveis
npm install
npm run dev               # http://localhost:4321
npm run build             # gera dist/
npm run preview           # serve dist/ localmente
npm run check             # astro check (tipos e diagnósticos)
```

## Variáveis de ambiente (todas de build)

| Variável | Uso |
| --- | --- |
| `PUBLIC_API_URL` | URL base da API, sem barra final. O formulário faz `POST ${PUBLIC_API_URL}/v1/waitlist` com `{"email": "...", "origem": "site"}`. Também entra no `connect-src` da CSP. Vazia = formulário mostra "lista indisponível". |
| `SITE_URL` | URL canônica (canonical, Open Graph, sitemap, robots.txt). Padrão `https://centelha.com.br` (domínio ainda a confirmar). |
| `PUBLIC_PLAUSIBLE_DOMAIN` | Opcional. Liga o Plausible (sem cookies). A página `/kids` nunca carrega analítica. |

Como o site é estático, mudar qualquer variável exige novo build.

## Estrutura

```
src/
  config.ts              e-mails, links das lojas (null = "Em breve"), redes sociais
  data/
    q88.json             texto da questão 88 + marcações de tempo do player demo
    obras.json           obras e status (lancamento / disponivel / em-breve)
    faq.json             perguntas frequentes (também vira JSON-LD FAQPage)
    campanhas.json       [] = seção "Campanha ativa" não aparece
    transparencia.json   custos (valores placeholder = null)
  components/            Header, Footer, Logo, ThemeToggle, DemoPlayer, WaitlistForm…
  layouts/BaseLayout.astro  SEO (title, description, OG, canonical, JSON-LD), fontes
  pages/                 rotas; robots.txt.ts gera o robots com a URL do sitemap
  styles/tokens.css      cópia de docs-iniciais/.../tokens/tokens.css (não editar aqui)
  styles/global.css      estilos base, acessibilidade, tokens complementares
public/
  brand/                 logos e ícones oficiais (SVG do guia da marca)
  og/share-1200x630.png  imagem de compartilhamento
  audio/                 q88.mp3 (ainda não existe; o player degrada sem ele)
  theme-init.js          aplica o tema salvo antes da pintura (padrão: escuro)
```

### Áudio de demonstração

Coloque o arquivo em `public/audio/q88.mp3` e ajuste `inicio`/`fim` de cada trecho
em `src/data/q88.json`. Sem o arquivo, o botão de play mostra "Áudio de demonstração
em breve" e o texto continua legível. O áudio só é baixado quando a pessoa toca em play.

## Decisões

- **Zero JS por padrão.** Só três scripts pequenos: alternância de tema, player demo e formulário.
- **Fontes self-hosted** (`@fontsource`), sem chamadas ao Google: menos dados pessoais trafegando (LGPD) e CSP mais simples.
- **CSP** gerada pelo Astro (`security.csp`) como `<meta>`, com hashes dos scripts e estilos inline. O nginx acrescenta `frame-ancestors` e os demais cabeçalhos.
- **Tema escuro padrão**, alternância salva em `localStorage`. Logo colorido no escuro e mono escuro no claro, como no guia da marca.
- **URLs sem barra final** (`build.format: 'file'`); o nginx redireciona `/pagina/` para `/pagina`.

## Deploy (Docker na VPS)

O site roda num container próprio: build com Node e serviço com nginx na porta 80
(sem TLS; o proxy reverso e a Cloudflare cuidam do HTTPS).

```bash
docker build \
  --build-arg PUBLIC_API_URL=https://api.centelha.com.br \
  --build-arg SITE_URL=https://centelha.com.br \
  -t centelha-site .

docker run -d --name centelha-site --restart unless-stopped -p 8080:80 centelha-site
curl -I http://localhost:8080/    # 200
```

O nginx (`nginx.conf` + `security-headers.conf`) faz:

- gzip para HTML, CSS, JS, SVG, JSON e XML;
- cache imutável de 1 ano em `/_astro/` (arquivos com hash), 7 dias em `/brand`, `/og` e favicons, 5 minutos no HTML;
- página 404 personalizada;
- cabeçalhos `X-Content-Type-Options`, `Referrer-Policy`, `Permissions-Policy`, `X-Frame-Options` e CSP `frame-ancestors 'none'`.

## Pendências (TODO)

- Conferir a redação da questão 88/88a na edição-fonte (Guillon Ribeiro); está marcada em `src/data/q88.json` e `src/pages/sobre.astro`.
- Gravar `public/audio/q88.mp3` e regerar as marcações de tempo.
- Confirmar o domínio e criar as caixas `suporte@` e `privacidade@` (`src/config.ts`).
- Links das lojas e perfis em redes sociais (`src/config.ts`).
- Revisão jurídica de `/privacidade`, `/termos` e `/suporte` (há campos `[a definir]`).
- Valores reais em `src/data/transparencia.json`.
- Ilustração oficial da Clara para `/kids` (hoje usa o ícone Kids).
- Fases seguintes: `/obras`, páginas por questão, blog, `/apoie`, `/campanhas`, i18n com hreflang.
