# Exportação do áudio por acessibilidade

Decisão 3B da [ADR 0004](../decisoes/0004-audio-cifrado-e-chave-atestada.md): o app é acessível por inteiro (VoiceOver e TalkBack), e quem precisa ouvir em outro player pede a exportação ao suporte. Os termos de uso já prometem isso (`site/src/pages/termos.astro`, seção 3).

## Como o suporte gera os arquivos

Na VPS, no container do worker (que tem a chave-mestra e o volume do áudio):

```sh
docker compose -f docker-compose.prod.yml exec worker \
  python -m centelha_api.pipeline.exportar --edicao <id> --saida /tmp/exportacao-<pedido> --pedido <número do pedido>
```

- Sai um `.m4a` aberto por capítulo publicado, numerado na ordem (`01-capitulo-i-de-deus.m4a`…), e um `LEIAME.txt` com a obra, a tradução, a fonte, o número do pedido e o aviso de uso pessoal.
- Só sai o que o catálogo público mostraria: edição publicada com direitos aprovados, capítulo publicado e faixa de motor com licença liberada. Edição infantil sai do mesmo jeito, sem link nem chamada no áudio.
- A `.cent` é decifrada só na pasta de saída. **Apague a pasta depois da entrega**: é uma cópia aberta do acervo.

O id da edição aparece no admin, ou em `GET /v1/obras` (campo `edicoes[].id`).

## A decidir pelo dono (#134)

Os termos ainda dizem *[Definir como o pedido é conferido e em que formato o áudio é entregue.]*. Até a decisão, o comando existe, mas o suporte não tem regra para atender.

1. **Conferência do pedido.** Pedir comprovante de deficiência é tratar dado de saúde, que é dado sensível na LGPD (art. 11), com base legal, guarda e descarte próprios. A recomendação é a autodeclaração, com o pedido registrado e o aviso de uso pessoal no LEIAME.
2. **Entrega.** Um capítulo tem de 5 a 60 MB, e uma obra inteira passa de 1 GB: não cabe em e-mail. As opções estão na #134.
3. **Obras com tradução protegida.** Hoje o acervo é Kardec na tradução de Guillon Ribeiro, em domínio público desde 2014 ([dossiê](../juridico/dossie-direitos.md), seção 1). Para obras ou traduções futuras ainda protegidas (#38, #46), a exportação aberta depende do art. 46, I, *d*, da Lei 9.610/1998 (reprodução para deficientes visuais, sem fim lucrativo): vai para o parecer (#3), inclusive se cobre outras necessidades de acessibilidade.
