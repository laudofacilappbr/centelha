/**
 * Cliente da API pública do catálogo, usado só no build (geração estática).
 *
 * CATALOGO_API_URL é lida no servidor de build e pode apontar para a rede interna
 * (ex.: http://api:8000); sem ela, usa PUBLIC_API_URL.
 *
 * Sem API: o build segue sem as páginas do acervo (útil no CI). No deploy, defina
 * CATALOGO_OBRIGATORIO=1 para o build falhar em vez de publicar um site sem obras.
 */

export type TipoSegmento = 'titulo' | 'paragrafo' | 'pergunta' | 'resposta' | 'comentario' | 'nota';

export interface EdicaoResumo {
  id: number;
  idioma: string;
  publico: 'adulto' | 'juvenil' | 'infantil';
  titulo: string;
  tradutor: string | null;
  publicada_em: string;
}

export interface Obra {
  slug: string;
  sigla: string;
  autor: string;
  titulo_original: string;
  ano: number | null;
  edicoes: EdicaoResumo[];
}

export interface CapituloResumo {
  id: number;
  ordem: number;
  titulo: string;
  referencia_canonica: string;
}

export interface Edicao extends EdicaoResumo {
  obra_slug: string;
  fonte: string;
  capitulos: CapituloResumo[];
}

export interface Segmento {
  id: number;
  ordem: number;
  tipo: TipoSegmento;
  texto: string;
  numero_questao: number | null;
  subquestao: string | null;
}

export interface Faixa {
  url: string;
  versao: number;
  duracao_ms: number;
  marcacoes: { segmento_id: number; inicio_ms: number; fim_ms: number }[];
  // "m4a" toca no navegador; "cent1" é cifrado e só o app decifra (ADR 0004).
  // Ausente nos dados gerados antes do campo existir: vale "m4a".
  formato?: string;
}

/** Faixa que o navegador consegue tocar. Faixa cifrada nunca vira player nem link. */
export function audioAberto(faixa: Faixa | null | undefined): faixa is Faixa {
  return !!faixa && (faixa.formato ?? 'm4a') === 'm4a';
}

export interface Capitulo extends CapituloResumo {
  edicao_id: number;
  segmentos: Segmento[];
  faixa: Faixa | null;
}

const env = import.meta.env;
const BASE = String(env.CATALOGO_API_URL || env.PUBLIC_API_URL || '').replace(/\/+$/, '');
const OBRIGATORIO = env.CATALOGO_OBRIGATORIO === '1';

const cache = new Map<string, Promise<unknown>>();

async function buscar<T>(caminho: string): Promise<T> {
  const url = `${BASE}${caminho}`;
  const r = await fetch(url, { headers: { Accept: 'application/json' } });
  if (!r.ok) throw new Error(`catálogo: ${r.status} em ${url}`);
  return (await r.json()) as T;
}

function memo<T>(caminho: string): Promise<T> {
  if (!cache.has(caminho)) cache.set(caminho, buscar<T>(caminho));
  return cache.get(caminho) as Promise<T>;
}

let avisado = false;

/** Obras com edição publicada no idioma do site. Vazio se a API não responde (e não é obrigatória). */
export async function obrasPublicadas(): Promise<Obra[]> {
  if (!BASE) {
    if (OBRIGATORIO) throw new Error('catálogo: CATALOGO_OBRIGATORIO=1 sem CATALOGO_API_URL/PUBLIC_API_URL');
    return [];
  }
  try {
    return await memo<Obra[]>('/v1/obras?idioma=pt-BR&publico=adulto');
  } catch (e) {
    if (OBRIGATORIO) throw e;
    if (!avisado) {
      console.warn(`[catalogo] API indisponível (${(e as Error).message}); páginas do acervo não geradas.`);
      avisado = true;
    }
    return [];
  }
}

/** Edição de leitura do site: pt-BR, adulto. */
export function edicaoDoSite(obra: Obra): EdicaoResumo | undefined {
  return obra.edicoes.find((e) => e.idioma === 'pt-BR' && e.publico === 'adulto');
}

export function edicao(id: number): Promise<Edicao> {
  return memo<Edicao>(`/v1/edicoes/${id}`);
}

export function capitulo(id: number): Promise<Capitulo> {
  return memo<Capitulo>(`/v1/capitulos/${id}`);
}

/** URL permanente do capítulo: a ordem na edição. Nunca mudar depois de publicada. */
export function slugCapitulo(c: CapituloResumo): string {
  return `capitulo-${c.ordem}`;
}

/** Remove o rótulo "CAPÍTULO I — " para usar o nome em títulos de página. */
export function nomeCapitulo(titulo: string): string {
  const partes = titulo.split(' — ');
  return partes[partes.length - 1] || titulo;
}

/** Descrição curta para <meta description>, cortada em palavra. */
export function resumir(texto: string, max = 155): string {
  const limpo = texto.replace(/\s+/g, ' ').trim();
  if (limpo.length <= max) return limpo;
  return limpo.slice(0, limpo.lastIndexOf(' ', max - 1)).replace(/[,;:.]$/, '') + '…';
}
