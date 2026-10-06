/**
 * Temas publicados no admin (GET /v1/temas), lidos no build.
 *
 * Cada item já vem resolvido pela API só para trechos publicados; o site não precisa
 * conferir estado nem direitos. Sem API, não há páginas de tema e a lista fica vazia.
 */
import { OBRA_COM_QUESTOES, urlQuestao } from './questoes';

export interface ItemTema {
  referencia: string;
  tipo: 'questao' | 'capitulo';
  obra_slug: string;
  edicao_id: number;
  capitulo_id: number;
  capitulo_ordem: number;
  titulo: string;
  numero_questao: number | null;
}

export interface Tema {
  slug: string;
  titulo: string;
  resumo: string;
  idioma: string;
  publicado_em: string;
  atualizado_em: string;
  itens: ItemTema[];
}

const env = import.meta.env;
const BASE = String(env.CATALOGO_API_URL || env.PUBLIC_API_URL || '').replace(/\/+$/, '');
const OBRIGATORIO = env.CATALOGO_OBRIGATORIO === '1';

let carregado: Promise<Tema[]> | undefined;

export function temasPublicados(): Promise<Tema[]> {
  carregado ??= (async () => {
    if (!BASE) {
      if (OBRIGATORIO) throw new Error('temas: CATALOGO_OBRIGATORIO=1 sem URL da API');
      return [];
    }
    try {
      const r = await fetch(`${BASE}/v1/temas?idioma=pt-BR`, { headers: { Accept: 'application/json' } });
      if (!r.ok) throw new Error(`temas: ${r.status}`);
      return (await r.json()) as Tema[];
    } catch (e) {
      if (OBRIGATORIO) throw e;
      console.warn(`[temas] API indisponível (${(e as Error).message}); páginas de tema não geradas.`);
      return [];
    }
  })();
  return carregado;
}

/** URL permanente do tema; nunca mudar depois de publicada (a API também trava o slug). */
export function urlTema(slug: string): string {
  return `/temas/${slug}`;
}

/** Para onde o item leva: página da questão (só o LE tem) ou o capítulo. */
export function urlItem(i: ItemTema): string {
  const capitulo = `/obras/${i.obra_slug}/capitulo-${i.capitulo_ordem}`;
  if (i.tipo === 'questao' && i.numero_questao != null) {
    return i.obra_slug === OBRA_COM_QUESTOES ? urlQuestao(i.numero_questao) : `${capitulo}#q${i.numero_questao}`;
  }
  return capitulo;
}

/** Temas que citam a questão n de O Livro dos Espíritos ("temas relacionados"). */
export async function temasDaQuestao(n: number): Promise<Tema[]> {
  return (await temasPublicados()).filter((t) =>
    t.itens.some((i) => i.tipo === 'questao' && i.obra_slug === OBRA_COM_QUESTOES && i.numero_questao === n),
  );
}

/** Parágrafos do resumo: texto puro, separados por linha em branco. */
export function paragrafos(texto: string): string[] {
  return texto
    .split(/\n\s*\n/)
    .map((p) => p.trim())
    .filter(Boolean);
}
