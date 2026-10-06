# 0004 — Áudio cifrado, com a chave entregue só ao app atestado

Data: 2026-10-06 · Status: aceita (#73)

## Contexto

O áudio era servido como `.m4a` aberto em `audio.{domínio}`, com URL pública e cache eterno ([ADR 0003](0003-fila-no-postgres-e-audio-em-volume.md)), e o site tocava e oferecia o download do capítulo inteiro. Qualquer pessoa raspava o acervo sem abrir o app, e cifrar só os downloads offline não protegeria nada. O dono pediu downloads offline que não possam ser copiados num formato aberto, como no Spotify.

Opções e riscos em #73. Resposta do dono transcrita lá: **1A, 2B, 3B, 4A**.

## Decisão

1. **Cifra no app + chave só para app atestado (1A).** O worker grava cada faixa no formato `.cent`: AES-256-GCM em blocos de 64 KiB, cada bloco com o próprio nonce e autenticado com o cabeçalho, o índice e a marca de último bloco (bloco trocado, reordenado ou cortado não passa). O arquivo continua público na CDN, com cache eterno: sem a chave ele é ilegível. A chave de cada faixa é aleatória e fica no banco cifrada por uma chave-mestra do servidor (`CENTELHA_AUDIO_CHAVE_MESTRA`, só no `.env` da VPS). O app recebe a chave por `POST /v1/faixas/{id}/chave` depois de provar, por App Attest (iOS) ou Play Integrity (Android), que é uma instalação legítima, e a guarda no Keychain ou no Keystore. Streaming e offline usam o mesmo arquivo.
2. **Renovação a cada 90 dias online (2B).** A chave entregue vale 90 dias; depois disso o app precisa ficar online uma vez para renová-la. Permite revogar uma faixa. O custo cai sobre quem tem pouca internet, e o app deve avisar antes de vencer.
3. **App acessível + exportação aberta mediante pedido de acessibilidade (3B).** O player funciona por inteiro com VoiceOver e TalkBack; quem precisar de outro player pede a exportação pelo suporte.
4. **Atestação também no público infantil (4A).** App Attest e Play Integrity são APIs das plataformas, não SDKs de terceiros, e não fazem analítica. Precisa constar na política de privacidade (#17).

O site não toca nem linka faixa cifrada; amostras para a landing saem de trechos abertos gerados à parte.

## Consequências

- A CDN e o cache da ADR 0003 continuam valendo; só a entrega da chave passa pela API.
- A cifragem é ligada por `CENTELHA_AUDIO_CIFRAR`, desligada até o app decifrar. Ligar sem a chave-mestra impede o worker de subir.
- Perder a chave-mestra torna todo o áudio cifrado ilegível: ela entra no backup (#26), fora da VPS e fora do repositório.
- Não é inquebrável: root ou jailbreak extrai a chave ou o áudio decifrado, e gravar a saída de som sempre funciona. A meta é barrar a cópia casual e a raspagem em massa.
- DRM completo (Widevine + FairPlay) foi descartado: custo alto e, no Android, áudio costuma ficar no nível de software (L3).
