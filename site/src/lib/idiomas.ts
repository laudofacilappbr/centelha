/**
 * Idiomas do acervo no site (#48). Decisões do dono: português na raiz, sem prefixo
 * (1A), e /fr, /es, /en com os nomes das seções e o slug da edição no idioma (2A).
 *
 * As URLs em português (/obras/<obra>/capitulo-<n>, /livro-dos-espiritos/questao/<n>)
 * são permanentes: o app compartilha links para elas.
 */
import type { CapituloResumo, Obra, EdicaoResumo } from './catalogo';

export type Lingua = 'pt' | 'fr' | 'es' | 'en';

/** Idiomas com prefixo, na ordem do seletor. */
export const OUTRAS: Exclude<Lingua, 'pt'>[] = ['fr', 'es', 'en'];

interface Rotas {
  prefixo: string;
  obras: string;
  capitulo: string;
  questao: string;
}

const ROTAS: Record<Lingua, Rotas> = {
  pt: { prefixo: '', obras: 'obras', capitulo: 'capitulo', questao: 'questao' },
  fr: { prefixo: '/fr', obras: 'oeuvres', capitulo: 'chapitre', questao: 'question' },
  es: { prefixo: '/es', obras: 'obras', capitulo: 'capitulo', questao: 'pregunta' },
  en: { prefixo: '/en', obras: 'works', capitulo: 'chapter', questao: 'question' },
};

/** Valor de lang e hreflang. */
export const HREFLANG: Record<Lingua, string> = { pt: 'pt-BR', fr: 'fr', es: 'es', en: 'en' };
export const OG_LOCALE: Record<Lingua, string> = { pt: 'pt_BR', fr: 'fr_FR', es: 'es_ES', en: 'en_US' };

/** "fr-FR", "fr" → "fr"; idioma fora do site → undefined. */
export function linguaDaEdicao(idioma: string): Lingua | undefined {
  const base = idioma.split('-')[0].toLowerCase();
  return (['pt', ...OUTRAS] as string[]).includes(base) ? (base as Lingua) : undefined;
}

export function rotas(l: Lingua): Rotas {
  return ROTAS[l];
}

/** Slug da edição na URL: o da obra em português; nos outros idiomas, o da edição. */
export function slugDaEdicao(l: Lingua, obra: Obra, ed: EdicaoResumo): string {
  return l === 'pt' ? obra.slug : (ed.slug ?? obra.slug);
}

export function urlInicio(l: Lingua): string {
  return l === 'pt' ? '/' : ROTAS[l].prefixo;
}

export function urlObras(l: Lingua): string {
  return `${ROTAS[l].prefixo}/${ROTAS[l].obras}`;
}

export function urlObra(l: Lingua, slug: string): string {
  return `${urlObras(l)}/${slug}`;
}

export function slugCapituloEm(l: Lingua, c: Pick<CapituloResumo, 'ordem'>): string {
  return `${ROTAS[l].capitulo}-${c.ordem}`;
}

export function urlCapitulo(l: Lingua, slug: string, c: Pick<CapituloResumo, 'ordem'>): string {
  return `${urlObra(l, slug)}/${slugCapituloEm(l, c)}`;
}

/** Em português continua /livro-dos-espiritos/questao/<n> (urlQuestao em questoes.ts). */
export function urlQuestaoEm(l: Exclude<Lingua, 'pt'>, slug: string, n: number): string {
  return `${ROTAS[l].prefixo}/${slug}/${ROTAS[l].questao}/${n}`;
}

/** Edição adulta publicada da obra em cada idioma do site. */
export function edicoesPorLingua(obra: Obra): Partial<Record<Lingua, EdicaoResumo>> {
  const r: Partial<Record<Lingua, EdicaoResumo>> = {};
  for (const ed of obra.edicoes) {
    const l = linguaDaEdicao(ed.idioma);
    if (l && ed.publico === 'adulto' && !r[l]) r[l] = ed;
  }
  return r;
}

export interface Alternativa {
  hreflang: string;
  href: string;
}

/** Textos das páginas do acervo nos outros idiomas. */
export const TEXTOS = {
  fr: {
    pular: 'Aller au contenu',
    obras: 'Œuvres',
    obrasTitulo: 'Œuvres en audio',
    obrasLede: 'Les œuvres d’Allan Kardec à écouter, gratuitement, dans leur texte intégral.',
    audiolivro: 'livre audio complet',
    descricaoObra: (t: string, a: string) => `Écoutez ${t}, d’${a}, en entier et gratuitement, en français.`,
    traducao: (t: string) => `Traduction de ${t}. `,
    fonte: (f: string) => `Source : ${f}. Narration par voix de synthèse, relue par des personnes.`,
    capitulos: 'Chapitres',
    ouvirCapitulo: 'Écouter ce chapitre',
    baixar: 'Télécharger l’audio',
    trilha: 'Fil d’Ariane',
    questao: (n: number) => `Question ${n}`,
    ctaObra: 'Écoutez l’œuvre complète dans l’application',
    ctaObraTexto: 'Gratuite, sans publicité, avec téléchargement pour écouter hors ligne.',
    ctaCapituloTexto: 'Avec le texte qui suit la narration et le téléchargement hors ligne.',
    ctaQuestao: (t: string) => `Écoutez ${t} en entier`,
    ctaQuestaoTexto: 'Dans l’application Centelha, gratuite, avec le texte qui suit la narration.',
    emBreve: 'Bientôt sur',
    lojas: 'Boutiques d’applications',
    vozSintetica: 'Voix de synthèse',
    nenhuma: 'Aucune œuvre publiée en français pour le moment.',
  },
  es: {
    pular: 'Saltar al contenido',
    obras: 'Obras',
    obrasTitulo: 'Obras en audio',
    obrasLede: 'Las obras de Allan Kardec para escuchar, gratis y completas.',
    audiolivro: 'audiolibro completo',
    descricaoObra: (t: string, a: string) => `Escucha ${t}, de ${a}, completo y gratis, en español.`,
    traducao: (t: string) => `Traducción de ${t}. `,
    fonte: (f: string) => `Fuente: ${f}. Narración con voz sintética, revisada por personas.`,
    capitulos: 'Capítulos',
    ouvirCapitulo: 'Escucha este capítulo',
    baixar: 'Descargar el audio',
    trilha: 'Ruta de navegación',
    questao: (n: number) => `Pregunta ${n}`,
    ctaObra: 'Escucha la obra completa en la app',
    ctaObraTexto: 'Gratis, sin anuncios, con descarga para escuchar sin conexión.',
    ctaCapituloTexto: 'Con el texto acompañando la narración y descarga sin conexión.',
    ctaQuestao: (t: string) => `Escucha ${t} completo`,
    ctaQuestaoTexto: 'En la app Centelha, gratis, con el texto acompañando la narración.',
    emBreve: 'Próximamente en',
    lojas: 'Tiendas de aplicaciones',
    vozSintetica: 'Voz sintética',
    nenhuma: 'Todavía no hay obras publicadas en español.',
  },
  en: {
    pular: 'Skip to content',
    obras: 'Works',
    obrasTitulo: 'Audiobooks',
    obrasLede: 'The works of Allan Kardec to listen to, free and unabridged.',
    audiolivro: 'complete audiobook',
    descricaoObra: (t: string, a: string) => `Listen to ${t}, by ${a}, unabridged and free, in English.`,
    traducao: (t: string) => `Translated by ${t}. `,
    fonte: (f: string) => `Source: ${f}. Narrated by a synthetic voice, reviewed by people.`,
    capitulos: 'Chapters',
    ouvirCapitulo: 'Listen to this chapter',
    baixar: 'Download the audio',
    trilha: 'Breadcrumb',
    questao: (n: number) => `Question ${n}`,
    ctaObra: 'Listen to the full work in the app',
    ctaObraTexto: 'Free, no ads, with downloads to listen offline.',
    ctaCapituloTexto: 'With the text following the narration and offline downloads.',
    ctaQuestao: (t: string) => `Listen to ${t} in full`,
    ctaQuestaoTexto: 'In the Centelha app, free, with the text following the narration.',
    emBreve: 'Coming soon to',
    lojas: 'App stores',
    vozSintetica: 'Synthetic voice',
    nenhuma: 'No works published in English yet.',
  },
} as const;
