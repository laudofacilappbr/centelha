# 0007 — Marca Centelhar e domínio centelhar.com.br

Data: 2026-10-07 · Status: aceita (#5)

## Contexto

"Centelha" era disputado: centelha.com.br e centelha.app ocupados por outros titulares, o "Programa Centelha" e a "Centelha Divina" competindo na busca, e o @ indisponível nas redes (#5). O dono reavaliou o nome e decidiu em 06/10/2026, com a análise em [`docs-iniciais/MDs/CENTELHAR_Alteracao_de_Nome_e_Arquitetura_da_Marca.md`](../../docs-iniciais/MDs/CENTELHAR_Alteracao_de_Nome_e_Arquitetura_da_Marca.md). Em 07/10/2026 registrou **centelhar.com.br**.

## Decisão

- **Marca:** Centelhar (verbo: emitir centelhas, fazer a luz surgir e se espalhar). A centelha continua sendo o símbolo; Centelhar é a ação e a marca.
- **Nas lojas e na busca:** "Centelhar — Audiolivros Espíritas". O descritor não faz parte do nome, para o produto poder ganhar outros formatos sem novo rebranding. Allan Kardec aparece em títulos, descrições e metadados, nunca no nome.
- **Assinatura:** "Ouça. Reflita. Evolua."
- **Públicos:** Centelhar (adulto), Centelhar Jovem, Centelhar Kids. A mascote é a **Clara, a pequena centelha** (antes: "a luzinha do Centelha"), personagem do Kids e do Jovem, nunca nome do app.
- **Domínio:** `centelhar.com.br`, com `www`, `api` e `audio` como subdomínios (`DOMINIO` no `.env` de produção) e e-mails `@centelhar.com.br`. Os alvos `centelhar.app.br`, `centelhar.app` e os @ nas redes (`@centelhar`, `@centelhar.app`, `@somoscentelhar`) ficam por registrar.
- **App:** nome exibido "Centelhar"; bundle id e `applicationId` passam de `app.centelha.centelha` para `br.com.centelhar.app`. O app ainda não foi enviado às lojas (#33), então é a última hora em que a troca é de graça.
- **Wordmark:** o desenho vetorial é Comfortaa Bold. O "r" foi acrescentado com o glyph da mesma fonte, na escala e na linha de base medidas no "Centelha" (as outras letras não mudaram).

## O que não muda

Identificadores internos que ninguém de fora vê ficam como estão, como permite a seção 13 do documento: o pacote Python `centelha_api`, o pacote Dart `centelha`, as variáveis `CENTELHA_*`, o banco e o usuário `centelha`, as imagens `ghcr.io/.../centelha-*`, `/opt/centelha` e o usuário da VPS, as chaves do Keychain e do `localStorage`, o repositório e as skills `centelha-*`. Trocá-los custaria migração de dados e de servidor sem ganho para quem usa.

A especificação em `docs-iniciais/MDs/` é o registro do que foi pensado com o nome antigo; onde ela disser "Centelha" como marca, vale este ADR.
