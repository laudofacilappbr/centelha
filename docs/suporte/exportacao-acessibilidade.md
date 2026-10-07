# Exportação do áudio por acessibilidade

Decisão 3B da [ADR 0004](../decisoes/0004-audio-cifrado-e-chave-atestada.md): o app é acessível por inteiro (VoiceOver e TalkBack), e quem precisa ouvir em outro player pede a exportação ao suporte. Os termos de uso já prometem isso (`site/src/pages/termos.astro`, seção 3).

## Como atender (decisão do dono na #134: 1A e 2D)

1. **Conferência: autodeclaração.** Basta a pessoa dizer que precisa. Não peça laudo nem comprovante: seria dado de saúde, que é dado sensível na LGPD (art. 11). Dê um número ao pedido (ex.: `S-2026-014`).
2. **A pessoa entra no app** com a conta opcional (e-mail e código). A liberação é da conta: sem conta, não há onde liberar.
3. **O suporte libera** com um usuário administrador do admin:
   ```sh
   curl -X POST https://api.centelhar.com.br/v1/admin/exportacoes \
     -H "Authorization: Bearer <token do admin>" -H "Content-Type: application/json" \
     -d '{"email": "<e-mail da conta>", "pedido": "S-2026-014"}'
   ```
   Fica na auditoria quem liberou e quando (`exportacao_liberada`), sem o e-mail.
4. **No app dessa conta, e só nela**, cada capítulo ganha "Baixar em formato aberto": o `.m4a` sai decifrado a cada pedido, como anexo, com o `LEIAME.txt` do pedido. Cada capítulo baixado fica registrado, com limite de 200 por dia (`CENTELHA_EXPORTACAO_DOWNLOADS_POR_DIA`).
5. **Revogar**, em caso de abuso: `GET /v1/admin/exportacoes` lista as vigentes, com quantos capítulos cada uma baixou; `DELETE /v1/admin/exportacoes/<id>` revoga na hora.

Só sai o que o catálogo público mostraria: edição publicada com direitos aprovados, capítulo publicado e faixa de motor com licença liberada. Se a pessoa excluir a conta, a liberação e o registro dos downloads saem junto.

O botão no app ainda está para entrar (parte de #134); até lá, o caminho é o comando abaixo.

## Pela linha de comando (caminho antigo)

Na VPS, no container do worker (que tem a chave-mestra e o volume do áudio):

```sh
docker compose -f docker-compose.prod.yml exec worker \
  python -m centelha_api.pipeline.exportar --edicao <id> --saida /tmp/exportacao-<pedido> --pedido <número do pedido>
```

- Sai um `.m4a` aberto por capítulo publicado, numerado na ordem (`01-capitulo-i-de-deus.m4a`…), e um `LEIAME.txt` com a obra, a tradução, a fonte, o número do pedido e o aviso de uso pessoal.
- Só sai o que o catálogo público mostraria: edição publicada com direitos aprovados, capítulo publicado e faixa de motor com licença liberada. Edição infantil sai do mesmo jeito, sem link nem chamada no áudio.
- A `.cent` é decifrada só na pasta de saída. **Apague a pasta depois da entrega**: é uma cópia aberta do acervo.

O id da edição aparece no admin, ou em `GET /v1/obras` (campo `edicoes[].id`).

## Obras com tradução protegida

Hoje o acervo é Kardec na tradução de Guillon Ribeiro, em domínio público desde 2014 ([dossiê](../juridico/dossie-direitos.md), seção 1). Para obras ou traduções futuras ainda protegidas (#38, #46), a exportação aberta depende do art. 46, I, *d*, da Lei 9.610/1998 (reprodução para deficientes visuais, sem fim lucrativo): vai para o parecer (#3), inclusive se cobre outras necessidades de acessibilidade.
