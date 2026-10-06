/**
 * Prestação de contas publicada no admin (GET /v1/transparencia), lida no build.
 *
 * Sem API ou sem mês publicado, devolve [] e a página mostra o conteúdo provisório
 * de src/data/transparencia.json. Com CATALOGO_OBRIGATORIO=1 (deploy), API fora do
 * ar derruba o build em vez de publicar a página como se não houvesse contas.
 */

export interface ItemContas {
  item: string;
  valor_centavos: number;
  nota: string | null;
}

export interface MesContas {
  mes: string; // "2026-10"
  publicado_em: string;
  custos: ItemContas[];
  arrecadacao: ItemContas[];
  total_custos_centavos: number;
  total_arrecadacao_centavos: number;
}

const env = import.meta.env;
const BASE = String(env.CATALOGO_API_URL || env.PUBLIC_API_URL || '').replace(/\/+$/, '');
const OBRIGATORIO = env.CATALOGO_OBRIGATORIO === '1';

export async function mesesPublicados(): Promise<MesContas[]> {
  if (!BASE) {
    if (OBRIGATORIO) throw new Error('transparência: CATALOGO_OBRIGATORIO=1 sem URL da API');
    return [];
  }
  try {
    const r = await fetch(`${BASE}/v1/transparencia`, { headers: { Accept: 'application/json' } });
    if (!r.ok) throw new Error(`transparência: ${r.status}`);
    return (await r.json()) as MesContas[];
  } catch (e) {
    if (OBRIGATORIO) throw e;
    console.warn(`[transparencia] API indisponível (${(e as Error).message}); usando valores provisórios.`);
    return [];
  }
}

/** Centavos inteiros → "R$ 49,90". A API não usa float para dinheiro; aqui também não. */
export function reais(centavos: number): string {
  return (centavos / 100).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
}

/** "2026-10" → "outubro de 2026". */
export function nomeMes(mes: string): string {
  const [ano, m] = mes.split('-').map(Number);
  return new Date(Date.UTC(ano, m - 1, 1)).toLocaleDateString('pt-BR', {
    month: 'long',
    year: 'numeric',
    timeZone: 'UTC',
  });
}
