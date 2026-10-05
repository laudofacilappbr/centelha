/**
 * Configuração central do site. Valores marcados com TODO dependem de
 * decisões ainda pendentes (domínio, perfis em redes, publicação nas lojas).
 */
export const SITE = {
  nome: 'Centelha',
  slogan: 'As obras de Kardec para ouvir, grátis.',
  descricaoPadrao:
    'Centelha é um app gratuito de audiolivros espíritas: as obras de Allan Kardec narradas em português, para ouvir offline e acompanhar o texto. Sem anúncios.',
  locale: 'pt_BR',
  // TODO: criar a caixa de e-mail quando o domínio for registrado.
  emailSuporte: 'suporte@centelha.com.br',
  emailPrivacidade: 'privacidade@centelha.com.br',
  // App ainda não publicado: null = botão "Em breve".
  lojas: {
    appStore: null as string | null,
    googlePlay: null as string | null,
  },
  // TODO: preencher quando os perfis forem criados (nome "Centelha" é disputado).
  redes: [] as { nome: string; url: string }[],
} as const;

export const API_URL = (import.meta.env.PUBLIC_API_URL ?? '').replace(/\/+$/, '');
