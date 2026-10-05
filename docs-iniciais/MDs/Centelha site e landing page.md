# Centelha: site e landing page

Oct 5, 2026 · @Ricardo

## Visão

O site do Centelha é um projeto próprio, separado do app mobile e do admin, mas que consome os mesmos dados. Nome definido: **Centelha** (app e site) e **Clara** (mascote).

| Projeto | Para quem | O que faz |
| --- | --- | --- |
| App (iOS/Android) | Ouvintes | Ouvir as obras, offline, com leitura acompanhada |
| Admin (CMS) | Equipe | Gerenciar obras, áudio, campanhas e posts |
| **Site (www)** | Quem ainda não conhece | Apresentar o projeto, atrair busca no Google, levar ao download |

Objetivos do site:

- Explicar em poucos segundos o que é o Centelha e levar ao download nas lojas.
- Ser encontrado no Google por quem busca as obras de Kardec, perguntas da doutrina e audiolivros espíritas.
- Dar transparência: custos, campanhas de caridade, uso de IA, direitos autorais.
- Servir de página externa para doações e apoio (exigida pelas regras da Apple, conforme a seção de monetização da especificação).
- Hospedar as páginas legais exigidas pelas lojas: política de privacidade, termos de uso e suporte.

Público principal: adultos curiosos sobre a doutrina, espíritas que querem estudar no trânsito, pessoas com dificuldade de leitura e pais e evangelizadores interessados na versão Kids.

## Conceito

### O que é o Centelha

Um app gratuito que transforma as obras de Allan Kardec em audiolivros, para ouvir no carro, no ônibus, antes de dormir ou para quem tem dificuldade de leitura. Todo o acervo vem de obras em domínio público, com narração gerada por inteligência artificial e revisão feita por pessoas.

Frase de posicionamento: **"As obras de Kardec para ouvir, grátis."**

### A centelha no espiritismo

O nome vem de O Livro dos Espíritos. Na questão 88, Kardec pergunta se os Espíritos têm forma determinada, e a resposta descreve o Espírito como "uma chama, um clarão, ou uma centelha etérea". Na sequência (88a), a cor dessa centelha vai do escuro e opaco ao brilho do rubi, conforme o Espírito seja mais ou menos puro. Mais adiante (92), a imagem volta: o Espírito irradia como uma centelha que projeta sua claridade ao longe.

Daí a ideia da marca:

- **Cada pessoa é uma centelha:** uma luz que existe antes do corpo e continua depois dele.
- **A luz cresce com o aprendizado:** quanto mais o Espírito se depura, mais brilha. Estudar é uma forma de acender essa luz.
- **Uma centelha acende outra:** o app espalha o conhecimento de graça, de ouvido em ouvido.

Cuidado no texto do site: a expressão de Kardec é "centelha etérea". "Centelha divina" é a forma popular, usada por autores posteriores e no meio espírita. O site pode usar as duas, mas, ao citar Kardec, deve citar a expressão dele, com o número da questão, e conferir a redação exata na edição-fonte de domínio público do projeto.

### A mascote Clara

Clara é uma pequena centelha de luz com rostinho, a guia das crianças no Centelha Kids. O nome junta clareza e luz e funciona em vários idiomas.

- **Personalidade:** curiosa, carinhosa, paciente e alegre. Pergunta mais do que responde e comemora cada acerto.
- **Papel:** apresenta as histórias e faz questionários simples sobre o que foi ouvido.
- **Relação com a marca:** Clara nasce do mesmo símbolo do logo, mas nunca substitui o logo. Aparece só nas áreas e materiais infantis.
- **Apresentação padrão:** "Clara, a luzinha do Centelha" (evita confusão com outros perfis chamados Clara nas redes).

## Mapa do site e landing page

### Mapa do site

| Caminho | Página | Origem do conteúdo |
| --- | --- | --- |
| / | Landing page | Fixo |
| /sobre | O projeto e a centelha no espiritismo | Fixo |
| /obras | Catálogo de obras disponíveis | API do catálogo |
| /obras/\[obra\] | Página de cada obra (ex.: /obras/o-livro-dos-espiritos) | API |
| /obras/\[obra\]/\[capitulo\] | Capítulo com texto e trecho de áudio | API |
| /livro-dos-espiritos/questao/\[n\] | Uma página por questão (1 a 1019) | API |
| /kids | Centelha Kids e a Clara, voltado aos pais | Fixo |
| /blog e /blog/\[post\] | Publicações | Admin |
| /campanhas e /campanhas/\[campanha\] | Campanhas de caridade e resultados | Admin |
| /apoie | Apoio ao projeto (pagamento externo) | Admin |
| /transparencia | Custos e arrecadação do mês | Admin |
| /como-fazemos | Uso de IA, revisão humana e direitos autorais | Fixo |
| /privacidade, /termos, /suporte | Páginas legais exigidas pelas lojas | Fixo |

### Landing page, seção por seção

1. **Topo (hero).** Título: "As obras de Allan Kardec para ouvir, grátis." Subtítulo: "O Livro dos Espíritos, O Evangelho Segundo o Espiritismo e outras obras narradas em português, para ouvir onde estiver." Botões da App Store e do Google Play. Imagem: celular com o player, centelha dourada ao fundo.
2. **Ouça agora.** Player com uma questão do Livro dos Espíritos (sugestão: a 88, que dá nome ao app) e o texto acompanhando. Mostra o produto antes de pedir o download.
3. **Por que Centelha.** Três cartões: grátis e sem anúncios; ouça offline; acompanhe o texto enquanto ouve.
4. **De onde vem o nome.** Texto curto sobre a questão 88 e link para /sobre.
5. **Obras disponíveis.** Capas das obras do catálogo, com status (disponível / em breve).
6. **Centelha Kids.** A Clara se apresenta aos pais: histórias curtas, questionários, sem anúncios, sem coleta de dados. Link para /kids.
7. **Como fazemos.** Narração por IA, revisão por pessoas, só obras em domínio público. Link para /como-fazemos.
8. **Campanha ativa.** Aparece só quando há campanha no admin, com meta e progresso.
9. **Perguntas frequentes.** É de graça mesmo? Funciona sem internet? Quem narra? Por que não tem Chico Xavier? Como posso ajudar?
10. **Rodapé.** Botões das lojas, redes sociais, apoie, transparência, privacidade, termos, suporte.

Visual: segue o guia da marca (azul-noite, centelha dourada, tipografia arredondada), com tema escuro como padrão e alternância para claro.

## SEO

A maior fonte de tráfego não é a landing page, e sim as páginas geradas a partir do acervo: cada questão, cada capítulo e cada tema vira uma página que responde a uma busca real. Como o texto já está revisado no admin, essas páginas saem quase de graça.

### Páginas que buscam tráfego

| Tipo de página | Exemplo de busca | Quantidade |
| --- | --- | --- |
| Questão do Livro dos Espíritos | "questao 88 livro dos espiritos" | Uma por questão (1.019) |
| Capítulo do Evangelho | "evangelho segundo o espiritismo capitulo 5" | 28 capítulos |
| Obra | "o livro dos espiritos audiolivro", "livro dos espiritos completo" | Uma por obra |
| Tema | "o que o espiritismo diz sobre reencarnação" | Dezenas, ligando questões e capítulos |
| Prece | "preces espiritas", "prece pelos doentes" | Preces do Evangelho (cap. 28) |
| Glossário | "o que é perispírito" | Termos da doutrina |

Cada página de questão ou capítulo traz: o texto, o áudio daquele trecho, links para a questão anterior e a próxima, temas relacionados e o botão "ouça a obra completa no app".

### Palavras-chave principais

- audiolivro espírita, audiolivros espíritas grátis
- o livro dos espíritos (áudio, completo, ouvir)
- o evangelho segundo o espiritismo (áudio, ouvir)
- allan kardec obras completas
- centelha espírito, centelha divina (atenção: termo disputado por canais espiritualistas)
- evangelização infantil espírita (para /kids)

### Regras técnicas

- Renderizar as páginas no servidor (ou gerar estáticas) para o Google ler o texto completo.
- URL limpa e permanente para cada questão e capítulo; nunca mudar depois de publicada.
- Título e descrição gerados por modelo: "Questão 88 — O Livro dos Espíritos | Centelha".
- Dados estruturados (schema.org): Book e Audiobook nas obras, Chapter nos capítulos, FAQPage nas perguntas frequentes, Article no blog, MobileApplication na landing.
- Sitemap automático, atualizado quando o admin publica algo.
- Smart App Banner no iPhone e link direto para o app (o mesmo endereço abre a questão no app, se instalado).
- Páginas rápidas no celular, com o áudio carregando só ao tocar em play.
- Preparar desde já a estrutura por idioma (/pt, /es, /fr) com hreflang, para a fase multilíngue.

### Cuidado com conteúdo duplicado

O mesmo texto de Kardec existe em centenas de sites. Para a página ser escolhida pelo Google, ela precisa oferecer algo a mais: o áudio, a navegação entre questões, os temas relacionados e, onde fizer sentido, uma nota explicativa curta escrita pela equipe.

## Blog e publicações

O blog fica no site, mas é escrito e publicado pelo admin (um módulo novo de posts). Cada post pode virar vídeo curto nas redes e vice-versa.

### Linhas editoriais

| Linha | Exemplo de título | Público |
| --- | --- | --- |
| Kardec responde | "O que O Livro dos Espíritos diz sobre sonhos" | Adulto |
| Estudo guiado | "Por onde começar a ler Kardec: um roteiro em 5 obras" | Adulto iniciante |
| Vida prática | "Paciência no trabalho segundo o Evangelho Segundo o Espiritismo" | Adulto (alimenta o LinkedIn) |
| Para pais e evangelizadores | "Como conversar sobre a morte com crianças" | Pais |
| Bastidores | "Como geramos a narração com IA e por que revisamos tudo" | Curiosos e tecnologia |
| Campanhas | "Campanha do agasalho: o que conseguimos juntos" | Todos |
| Novidades | "A Gênese chegou ao Centelha" | Usuários |

### Ritmo inicial

- 1 post por semana, alternando as linhas.
- Datas do calendário de campanhas e marcos (18 de abril, 3 de outubro, Natal) ganham post próprio.
- Cada lançamento de obra no app ganha um post de novidade.

### Regras

- Todo post cita a fonte exata (obra e número da questão ou capítulo) e linka para a página daquela questão no site.
- Rascunho com IA é permitido; revisão doutrinária humana antes de publicar é obrigatória, como nas adaptações infantis.
- Não citar trechos de obras protegidas (Chico Xavier, Divaldo Franco, traduções recentes).
- Tom: sereno, acolhedor, sem polêmica com outras religiões ou correntes espíritas.
- Cada post termina com chamada para ouvir o trecho no app.
- Posts escritos em grande volume por IA, sem revisão, prejudicam o ranqueamento e a credibilidade; menos posts, mais cuidado.

## Arquitetura técnica

O site é um quarto componente ao lado do app, do admin e da API, sem banco próprio: lê tudo da API do catálogo.

| Camada | Escolha | Por quê |
| --- | --- | --- |
| Framework | Next.js (geração estática com revalidação) ou Astro | Páginas pré-geradas, rápidas e lidas pelo Google; Next.js reaproveita o conhecimento do admin |
| Dados | API do catálogo (FastAPI) | Mesma fonte do app: obras, capítulos, questões, áudio, posts, campanhas |
| Áudio | Mesmo storage e CDN do app (Cloudflare R2) | Nada duplicado |
| Hospedagem | Cloudflare Pages ou Vercel | Plano gratuito cobre o início |
| Análise de acesso | Plausible ou Umami, sem cookies | Dispensa banner de cookies; nenhuma medição em /kids |
| Formulários | Suporte por e-mail; sem login no site | Menos dados pessoais, menos LGPD |

O que muda no admin e na API:

- **Novo módulo de posts** (título, texto, capa, linha editorial, obra e questões citadas, estado rascunho/revisado/publicado).
- **Páginas de tema** (tema, texto curto, lista de questões e capítulos ligados).
- **Campos de SEO** por obra, capítulo e post (título e descrição opcionais; se vazios, usa o modelo).
- **Aviso de publicação:** ao publicar ou alterar algo, o admin chama o site para regenerar só as páginas afetadas e o sitemap.
- **Endpoints públicos** de leitura na API com cache, sem autenticação, separados dos endpoints do admin.

Links para o app:

- Universal Links (iOS) e App Links (Android) no mesmo domínio, para que /livro-dos-espiritos/questao/88 abra direto no app quando instalado.
- Os arquivos de verificação (apple-app-site-association e assetlinks.json) ficam no site.

Domínio: verificar centelha.com.br e variações (centelhaapp.com.br, ouvircentelha.com.br) junto com os perfis de redes sociais, já que "Centelha" é disputado.

## Fases, pendências e referências

### Fases do site

| Fase do app | O site entrega |
| --- | --- |
| Fase 0 — Validação | Página "em breve" com lista de espera por e-mail e as páginas legais (necessárias para o teste nas lojas) |
| Fase 1 — MVP | Landing completa, /sobre, /como-fazemos, /transparencia e páginas das duas obras do MVP, com todas as questões do Livro dos Espíritos |
| Fase 2 — Catálogo | Blog, páginas de tema, glossário, /apoie, /campanhas e /kids |
| Fase 3 — Multilíngue | Versões /es, /fr, /en com hreflang |

### Pendências

- [ ] Registrar o domínio (junto com os perfis nas redes)
- [ ] Confirmar a redação exata da questão 88 na edição-fonte de domínio público
- [ ] Escolher Next.js ou Astro
- [ ] Escrever a política de privacidade e os termos (revisão jurídica)
- [ ] Gerar o guia da marca antes do layout do site

### Documentos do projeto

- [Plataforma de audiolivros espíritas: especificação](https://claude.ai/code/artifact/b71130a0-0e0e-4da4-8484-673e3c1c52a8)
- [Centelha: prompts de logo e mascote](https://claude.ai/code/artifact/cd9e9db2-641a-4bb9-9249-a5c8e55090f3)
- [Centelha: análise de concorrentes](https://claude.ai/code/artifact/96bdd8c6-019c-4144-95c2-cbb2ab776a5d)
- [Centelha: plano de redes sociais](https://claude.ai/code/artifact/60cfcbac-7ec7-4100-9f01-d78884078f1d)

### Referências

- [O Livro dos Espíritos, questão 88 — KardecPedia](https://kardecpedia.com/roteiro-de-estudos/2/o-livrodos-espiritos/345/parte-segunda-do-mundo-espirita-ou-mundo-dos-espiritos/capitulo-i-dos-espiritos/forma-e-ubiquidade-dos-espiritos/88)
