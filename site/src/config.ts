/**
 * Configuração central do site. Valores marcados com TODO dependem de
 * decisões ainda pendentes (perfis em redes, publicação nas lojas).
 * Marca: docs-iniciais/MDs/CENTELHAR_Alteracao_de_Nome_e_Arquitetura_da_Marca.md.
 */
export const SITE = {
  nome: 'Centelhar',
  slogan: 'As obras de Kardec para ouvir, grátis.',
  // Descritor (SEO e lojas) e assinatura da marca.
  descritor: 'Audiolivros Espíritas',
  assinatura: 'Ouça. Reflita. Evolua.',
  descricaoPadrao:
    'Centelhar é um app gratuito de audiolivros espíritas: as obras de Allan Kardec narradas em português, para ouvir offline e acompanhar o texto. Sem anúncios.',
  locale: 'pt_BR',
  // TODO: criar as caixas de e-mail no domínio centelhar.com.br (registrado).
  emailSuporte: 'suporte@centelhar.com.br',
  emailPrivacidade: 'privacidade@centelhar.com.br',
  // App ainda não publicado: null = botão "Em breve".
  lojas: {
    appStore: null as string | null,
    googlePlay: null as string | null,
  },
  // TODO: preencher quando os perfis forem criados (alvos: @centelhar, @centelhar.app, @somoscentelhar).
  redes: [] as { nome: string; url: string }[],
} as const;

export const API_URL = (import.meta.env.PUBLIC_API_URL ?? '').replace(/\/+$/, '');
