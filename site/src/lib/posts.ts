/**
 * Posts publicados no admin (GET /v1/posts), lidos no build.
 *
 * A API só devolve post que passou pela revisão e cita ao menos um trecho publicado;
 * as fontes já vêm resolvidas. Sem API, o blog fica vazio.
 */
import type { ItemTema } from './temas';

export interface PostResumo {
  slug: string;
  titulo: string;
  resumo: string;
  linha: string;
  capa_url: string | null;
  publicado_em: string;
  atualizado_em: string;
}

export interface Post extends PostResumo {
  texto: string;
  idioma: string;
  fontes: ItemTema[];
}

export const NOMES_LINHA: Record<string, string> = {
  kardec_responde: 'Kardec responde',
  estudo_guiado: 'Estudo guiado',
  vida_pratica: 'Vida prática',
  pais_e_evangelizadores: 'Para pais e evangelizadores',
  bastidores: 'Bastidores',
  campanhas: 'Campanhas',
  novidades: 'Novidades',
};

const env = import.meta.env;
const BASE = String(env.CATALOGO_API_URL || env.PUBLIC_API_URL || '').replace(/\/+$/, '');
const OBRIGATORIO = env.CATALOGO_OBRIGATORIO === '1';

async function buscar<T>(caminho: string): Promise<T> {
  const r = await fetch(`${BASE}${caminho}`, { headers: { Accept: 'application/json' } });
  if (!r.ok) throw new Error(`blog: ${r.status} em ${caminho}`);
  return (await r.json()) as T;
}

let carregado: Promise<Post[]> | undefined;

/** Posts completos, do mais recente ao mais antigo. */
export function postsPublicados(): Promise<Post[]> {
  carregado ??= (async () => {
    if (!BASE) {
      if (OBRIGATORIO) throw new Error('blog: CATALOGO_OBRIGATORIO=1 sem URL da API');
      return [];
    }
    try {
      const lista = await buscar<PostResumo[]>('/v1/posts?idioma=pt-BR');
      return await Promise.all(lista.map((p) => buscar<Post>(`/v1/posts/${p.slug}`)));
    } catch (e) {
      if (OBRIGATORIO) throw e;
      console.warn(`[blog] API indisponível (${(e as Error).message}); blog não gerado.`);
      return [];
    }
  })();
  return carregado;
}

export function urlPost(slug: string): string {
  return `/blog/${slug}`;
}

export function dataPost(iso: string): string {
  return new Date(iso).toLocaleDateString('pt-BR', { day: 'numeric', month: 'long', year: 'numeric', timeZone: 'America/Sao_Paulo' });
}
