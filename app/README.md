# App Centelha (Flutter)

Android e iOS, um código só. MVP sem login: preferências e progresso ficam no aparelho.

## Rodar

Flutter 3.47.6 (stable), a mesma versão de `ci/app.Dockerfile`.

```sh
cd app
flutter pub get
flutter run --dart-define=CENTELHA_API_URL=http://10.0.2.2:8000   # emulador Android, API local
flutter run --dart-define=CENTELHA_API_URL=https://api.<domínio>  # API de produção
```

Sem `CENTELHA_API_URL`, o app usa `http://10.0.2.2:8000`, que é o localhost do computador visto do emulador Android. Http sem TLS só é permitido no build de debug.

## Onde fica cada coisa

| Caminho | O quê |
| --- | --- |
| `lib/tema/centelha_tema.dart` | Tema claro e escuro a partir dos tokens da marca (`docs-iniciais/centelha-brand/tokens`) |
| `lib/l10n/app_*.arb` | Todas as strings da interface (pt, es, fr, en). O Dart é gerado pelo `flutter gen-l10n` e não vai para o git |
| `lib/idioma/` | Idioma do aparelho por padrão, troca manual salva no aparelho |
| `lib/api/` | Cliente da API pública do catálogo |
| `lib/tela/` | Telas. `compartilhar.dart`: segurar um trecho do capítulo compartilha ou copia o texto com a citação e o link permanente do site, só em edição adulta (o perfil infantil não tem link externo) |
| `assets/fonts/` | Comfortaa e Atkinson Hyperlegible, empacotadas com a licença OFL. Nada é baixado em tempo de uso |

String nova: adicione a chave em `app_pt.arb` e nos outros três arquivos. Sem tradução, o `gen-l10n` avisa.

## Validar

```sh
bash ci/validar.sh app   # na raiz: format, analyze e testes em Docker
```

## Antes da primeira publicação na loja

- O `applicationId`/bundle id (`app.centelha.centelha`) não pode mudar depois do primeiro envio. Confirme antes.
- Ícone, splash e assinatura dos builds ainda não estão configurados.

## Player

`lib/player/`: `reprodutor.dart` é o motor (just_audio dentro do audio_service, com segundo plano e controles na tela de bloqueio); `controle_player.dart` é o estado para as telas (velocidade, timer de sono, marcadores); `progresso.dart` guarda posição, marcadores e velocidade no aparelho. A posição guarda o segmento junto: se o áudio for regenerado, a retomada cai no começo do mesmo segmento.

Faixa com `formato` diferente de `m4a` (áudio cifrado, #73) ainda não toca: a decifragem entra em `fonteDe()`.
