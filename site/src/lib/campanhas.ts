/**
 * Campanhas de caridade publicadas no admin (GET /v1/campanhas, #41), lidas no build.
 *
 * O Pix é da instituição parceira: o projeto não recebe nada. Sem API, não há páginas
 * de campanha e a lista fica vazia. Com CATALOGO_OBRIGATORIO=1 (deploy), API fora do
 * ar derruba o build.
 */

export interface Instituicao {
  nome: string;
  cnpj: string;
  descricao: string;
  chave_pix: string | null;
  pagina_doacao: string | null;
  site: string | null;
}

export type Situacao = "futura" | "ativa" | "encerrada";

export interface Campanha {
  slug: string;
  titulo: string;
  texto: string;
  instituicao: Instituicao;
  inicio: string; // "2026-07-01"
  fim: string;
  situacao: Situacao;
  meta_centavos: number | null;
  imagem_url: string | null;
  arrecadado_centavos: number | null;
  resultado: string | null;
  publicado_em: string;
  atualizado_em: string;
}

const env = import.meta.env;
const BASE = String(env.CATALOGO_API_URL || env.PUBLIC_API_URL || "").replace(
  /\/+$/,
  "",
);
const OBRIGATORIO = env.CATALOGO_OBRIGATORIO === "1";

let carregado: Promise<Campanha[]> | undefined;

export function campanhasPublicadas(): Promise<Campanha[]> {
  carregado ??= (async () => {
    if (!BASE) {
      if (OBRIGATORIO)
        throw new Error("campanhas: CATALOGO_OBRIGATORIO=1 sem URL da API");
      return [];
    }
    try {
      const r = await fetch(`${BASE}/v1/campanhas`, {
        headers: { Accept: "application/json" },
      });
      if (!r.ok) throw new Error(`campanhas: ${r.status}`);
      const lista = (await r.json()) as Campanha[];
      // Só https sai do site; a API já recusa outro esquema, isto é a segunda trava.
      for (const c of lista) {
        for (const k of ["pagina_doacao", "site"] as const) {
          const v = c.instituicao[k];
          if (v && !v.startsWith("https://")) c.instituicao[k] = null;
        }
        if (c.imagem_url && !c.imagem_url.startsWith("https://"))
          c.imagem_url = null;
      }
      return lista;
    } catch (e) {
      if (OBRIGATORIO) throw e;
      console.warn(
        `[campanhas] API indisponível (${(e as Error).message}); páginas de campanha não geradas.`,
      );
      return [];
    }
  })();
  return carregado;
}

/** URL permanente da campanha; a API trava o slug depois de publicada. */
export function urlCampanha(slug: string): string {
  return `/campanhas/${slug}`;
}

/** "2026-07-01" → "1º de julho de 2026". */
export function dataCampanha(iso: string): string {
  const [a, m, d] = iso.split("-").map(Number);
  const texto = new Date(Date.UTC(a, m - 1, d)).toLocaleDateString("pt-BR", {
    day: "numeric",
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  });
  return d === 1 ? texto.replace(/^1 /, "1º ") : texto;
}

/** "11222333000181" → "11.222.333/0001-81". */
export function formatarCnpj(c: string): string {
  return c.replace(/^(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})$/, "$1.$2.$3/$4-$5");
}
