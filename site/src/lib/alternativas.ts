/**
 * Versões da mesma página em outros idiomas, para <link rel="alternate" hreflang> (#48).
 * Só entram páginas que existem: capítulo publicado e questão presente naquela edição.
 */
import { edicao, obrasEmTodosOsIdiomas } from './catalogo';
import {
  HREFLANG,
  edicoesPorLingua,
  slugDaEdicao,
  urlCapitulo,
  urlObra,
  urlQuestaoEm,
  type Alternativa,
  type Lingua,
} from './idiomas';
import { OBRA_COM_QUESTOES, questoesDaEdicao, urlQuestao } from './questoes';

type Pagina =
  | { tipo: 'obra' }
  | { tipo: 'capitulo'; referencia: string }
  | { tipo: 'questao'; numero: number };

async function caminho(l: Lingua, obraSlug: string, pagina: Pagina): Promise<string | undefined> {
  const obra = (await obrasEmTodosOsIdiomas()).find((o) => o.slug === obraSlug);
  const resumo = obra && edicoesPorLingua(obra)[l];
  if (!obra || !resumo) return undefined;
  const slug = slugDaEdicao(l, obra, resumo);
  if (pagina.tipo === 'obra') return urlObra(l, slug);
  const ed = await edicao(resumo.id);
  if (pagina.tipo === 'capitulo') {
    const c = ed.capitulos.find((x) => x.referencia_canonica === pagina.referencia);
    return c && urlCapitulo(l, slug, c);
  }
  if (obra.slug !== OBRA_COM_QUESTOES) return undefined;
  const tem = (await questoesDaEdicao(ed)).some((q) => q.numero === pagina.numero);
  if (!tem) return undefined;
  return l === 'pt' ? urlQuestao(pagina.numero) : urlQuestaoEm(l, slug, pagina.numero);
}

/** Lista para o BaseLayout; vazia quando a página só existe num idioma. */
export async function alternativas(obraSlug: string, pagina: Pagina, site: URL): Promise<Alternativa[]> {
  const r: Alternativa[] = [];
  for (const l of ['pt', 'fr', 'es', 'en'] as Lingua[]) {
    const c = await caminho(l, obraSlug, pagina);
    if (c) r.push({ hreflang: HREFLANG[l], href: new URL(c, site).href });
  }
  return r.length > 1 ? r : [];
}
