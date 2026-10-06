/**
 * Glossário publicado no admin (GET /v1/glossario), lido no build.
 *
 * Como nos temas, cada item já vem resolvido pela API só para trechos publicados com
 * direitos aprovados. Sem API, não há páginas de termo e o índice fica vazio.
 */
import { OBRA_COM_QUESTOES } from "./questoes";
import type { ItemTema } from "./temas";

export interface Termo {
  slug: string;
  termo: string;
  definicao: string;
  idioma: string;
  publicado_em: string;
  atualizado_em: string;
  itens: ItemTema[];
}

const env = import.meta.env;
const BASE = String(env.CATALOGO_API_URL || env.PUBLIC_API_URL || "").replace(
  /\/+$/,
  "",
);
const OBRIGATORIO = env.CATALOGO_OBRIGATORIO === "1";

let carregado: Promise<Termo[]> | undefined;

export function termosPublicados(): Promise<Termo[]> {
  carregado ??= (async () => {
    if (!BASE) {
      if (OBRIGATORIO)
        throw new Error("glossário: CATALOGO_OBRIGATORIO=1 sem URL da API");
      return [];
    }
    try {
      const r = await fetch(`${BASE}/v1/glossario?idioma=pt-BR`, {
        headers: { Accept: "application/json" },
      });
      if (!r.ok) throw new Error(`glossário: ${r.status}`);
      return (await r.json()) as Termo[];
    } catch (e) {
      if (OBRIGATORIO) throw e;
      console.warn(
        `[glossario] API indisponível (${(e as Error).message}); páginas de termo não geradas.`,
      );
      return [];
    }
  })();
  return carregado;
}

/** URL permanente do termo; nunca mudar depois de publicada (a API também trava o slug). */
export function urlTermo(slug: string): string {
  return `/glossario/${slug}`;
}

/** Termos que citam a questão n de O Livro dos Espíritos. */
export async function termosDaQuestao(n: number): Promise<Termo[]> {
  return (await termosPublicados()).filter((t) =>
    t.itens.some(
      (i) =>
        i.tipo === "questao" &&
        i.obra_slug === OBRA_COM_QUESTOES &&
        i.numero_questao === n,
    ),
  );
}

/** Letra do índice: "Ânimo" e "anjo" ficam juntos em "A". */
export function letra(termo: string): string {
  const l = termo
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .charAt(0)
    .toUpperCase();
  return /[A-Z]/.test(l) ? l : "#";
}
