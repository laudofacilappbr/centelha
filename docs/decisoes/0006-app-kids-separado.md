# 0006 — Centelha Kids: app separado para o público infantil

Data: 2026-10-07 · Status: aceita (#50)

## Contexto

A Fase 4 traz a Clara e as adaptações infantis (#49). A regra do repositório para o público infantil é "nenhuma analítica, anúncio, apoio ou link externo". As lojas acrescentam:

- **Google Play (Families Policy):** se o app mira crianças, mesmo em parte, o app inteiro segue as regras de família, inclusive quais SDKs pode usar.
- **Apple (categoria Kids):** sem links para concluir transações em sites, restrições a SDKs de terceiros e controle parental antes de sair do app.

Um perfil infantil dentro do app principal sujeitaria o app inteiro a essas regras, com apoio, campanhas, Sentry (#27) e atestação (#73) junto. Opções e riscos estão na #50.

## Decisão

Resposta do dono transcrita na #50: **1a, 2a**.

1. **Só o app Centelha Kids separado (1a).** Nada de perfil infantil no app principal: as edições com `publico = infantil` não aparecem nele (`Obra.semInfantil`) e só aparecem no Kids.
2. **Link só do app principal para o Kids (2a).** O Kids não tem link para fora, nem para o app principal.

## Como fica no código

- **Mesmo projeto Flutter, outra entrada:** `lib/main_kids.dart` sobe o `CentelhaKidsApp` (`lib/kids/app_kids.dart`). Ele lista só as edições infantis, abre os capítulos e toca o áudio.
- **A regra é garantida no import, não num `if`.** O Kids não importa apoio, campanhas, configurações, compartilhar, baixados, planos, chaves, downloads, `url_launcher` nem `share_plus`, e `test/kids_test.dart` confere. O capítulo abre sem citação e sem origem, o que desliga compartilhar e trocar de edição.
- **Limite:** a tela do capítulo é a mesma do app principal, e ela importa o código de compartilhar. Por isso `share_plus` e `url_launcher` entram no binário do Kids, embora nenhuma tela do Kids os chame. Nenhum dos dois é SDK de analítica ou anúncio. Se a revisão da loja reclamar, a tela do capítulo se separa em leitura e ações.
- **Android:** *flavors* `principal` e `kids` (`applicationIdSuffix ".kids"`, nome "Centelha Kids"). O padrão é `principal` (`default-flavor` no `pubspec.yaml`), então os builds sem `--flavor` seguem como antes. O Kids sai com `flutter build apk --flavor kids -t lib/main_kids.dart`.
- **iOS:** ainda sem *scheme* nem *target* Kids. Isso entra junto com a ficha na App Store (#39), que pede o bundle id do dono.
- **Áudio:** o Kids não tem atestação nem downloads por enquanto, e toca só `.m4a` aberto. A decisão 4A da #73 (atestação também no infantil) entra com os atestadores reais.

## Consequências

- Duas fichas nas lojas e duas revisões: um passo `manual` do dono, na #39.
- O app principal fica livre das regras de família, com apoio, campanhas, Sentry e atestação.
- Para o Kids ter conteúdo, faltam as adaptações (#49), que esperam o parecer (#3) e o motor de voz (#1).
- Reversível: dá para fundir depois, mas as declarações nas lojas mudam.
