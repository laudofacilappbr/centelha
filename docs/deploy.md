# Deploy na VPS

Um container por serviço, com a Cloudflare na frente ([ADR 0001](decisoes/0001-deploy-vps-docker-cloudflare.md)). A VPS é a da Locaweb (#26).

| Serviço | O que faz | Rede |
| --- | --- | --- |
| `caddy` | TLS com Origin Certificate e proxy para `site` e `api`; serve o áudio | borda (80/443 só para a Cloudflare) |
| `site` | Site estático (nginx), servido do volume `site` | borda |
| `site-construtor` | Regera o site quando o conteúdo muda: lê `GET /v1/site/marca` a cada minuto e, com a marca nova estável, faz o build contra a API interna e troca a versão servida (#42). Build com falha mantém o site no ar; o motivo fica em `docker compose logs site-construtor` | interna |
| `api` | FastAPI; roda as migrações na partida | borda, interna |
| `worker` | Fila de áudio (TTS e ffmpeg) | interna, saída |
| `piper` | TTS local | interna |
| `backup` | Banco e áudio, cifrados, para o bucket, todo dia | interna, saída |
| `postgres` | Banco | interna |

## Primeira vez

O dono faz os passos 1 a 5, o 7 e o 8; o 6 é um comando.

1. **SSH por chave na VPS**, com um usuário que tenha sudo. Confirme que entra sem senha.
2. **Chave do deploy:** `ssh-keygen -t ed25519 -f centelha-deploy -C deploy-github`. A pública vai no passo 6; a privada vai para o GitHub no passo 7.
3. **Cloudflare (domínio, #5):**
   - nameservers apontados para a Cloudflare;
   - SSL/TLS em **Full (strict)**;
   - registros `@`, `www`, `api` e `audio` apontando para a VPS, com proxy ligado (nuvem laranja).
4. **Origin Certificate:** gere na Cloudflare e guarde `origin.pem` e `origin.key` (só na VPS, no passo 8).
5. **Bucket de backup** (R2 ou B2):
   - crie o bucket e uma chave restrita a ele;
   - gere uma `BACKUP_SENHA` longa e guarde-a também num gerenciador de senhas. Sem ela, o backup não restaura.
6. **Preparar a VPS**, como root:
   ```sh
   git clone https://github.com/laudofacilappbr/centelha && cd centelha/infra/vps
   CHAVE_DEPLOY="ssh-ed25519 AAAA… deploy-github" bash preparar.sh   # conteúdo de centelha-deploy.pub
   ```
   O script cria o usuário `centelha`, deixa o SSH só com chave e sem root e fecha 80/443 para tudo que não for a Cloudflare. Ele também instala fail2ban, atualizações automáticas e Docker. Antes de fechar a sessão de root, teste num segundo terminal: `ssh -i centelha-deploy centelha@<host>`.
7. **Segredos no GitHub** (Settings → Secrets and variables → Actions):
   - segredos `VPS_HOST`, `VPS_USUARIO` (`centelha`), `VPS_CHAVE_SSH` (o conteúdo de `centelha-deploy`) e `VPS_KNOWN_HOSTS` (a saída de `ssh-keyscan -t ed25519 <host>`);
   - variável `DOMINIO`.
8. **Na VPS, em `/opt/centelha`:**
   - `certs/origin.pem` e `certs/origin.key`;
   - `.env` a partir de [`infra/.env.example`](../infra/.env.example).

   Os três arquivos precisam ser do usuário `centelha`, com `chmod 600`, porque é ele quem roda o `docker compose` no deploy: `sudo chown centelha: .env certs/* && sudo chmod 600 .env certs/*`.
9. **Primeiro deploy:** Actions → Deploy → Run workflow.

Nunca cole IP, chave, senha ou certificado em issue ou PR: o repositório é público.

## Depois

- **Cada merge na `main`:**
  1. o workflow Imagens publica as imagens com o SHA do commit;
  2. o Deploy copia o compose e o Caddyfile, faz `pull` e `up -d --wait` com essa tag;
  3. o Deploy confere `https://api.<domínio>/health` e o site.

  Sem os segredos, o Deploy é pulado com um aviso.
- **Voltar uma versão:** Actions → Deploy → Run workflow, com o SHA de um commit anterior em `tag`.
- **Logs:** `docker compose -f docker-compose.prod.yml logs -f api worker`, com rotação de 20 MB × 5 por serviço.
- **Restaurar o backup:** cabeçalho de [`infra/backup/restaurar.sh`](../infra/backup/restaurar.sh).
- **Ligar o áudio cifrado (ADR 0004, #73)**, só quando o app decifrar a `.cent`:
  1. no `.env`, `CENTELHA_AUDIO_CIFRAR=true` (com a chave-mestra no backup) e, para a purga automática, `CENTELHA_CLOUDFLARE_ZONA` e `CENTELHA_CLOUDFLARE_TOKEN`; depois `up -d worker`;
  2. `docker compose -f docker-compose.prod.yml exec worker python -m centelha_api.pipeline.recifrar --simular` mostra quantas faixas `.m4a` existem;
  3. sem `--simular`, cada uma vira `.cent`, o `.m4a` é apagado e o cache dele e do JSON do capítulo é purgado. Sem o token, o comando lista as URLs para purgar no painel. Pode ser interrompido e rodado de novo.
- **IPs da Cloudflare:** `centelha-firewall-cloudflare` baixa a lista a cada partida do Docker. Para atualizar na hora, rode `sudo systemctl restart centelha-firewall`.

## Testar sem VPS

```sh
bash ci/validar.sh vps      # preparar.sh num Ubuntu 24.04 e firewall com pacote de verdade
bash ci/validar.sh backup   # backup → apaga → restaura
bash ci/validar.sh infra    # compose de dev e prod, Caddyfile
```
