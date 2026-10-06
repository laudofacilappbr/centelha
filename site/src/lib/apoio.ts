/**
 * Apoio ao projeto configurado no admin (GET /v1/apoio, #40), lido no build.
 *
 * Desligado ou sem API: a página /apoie diz que o apoio ainda não está aberto e o
 * rodapé não aponta para ela. Com CATALOGO_OBRIGATORIO=1 (deploy), API fora do ar
 * derruba o build: publicar o site com o apoio "fechado" quando ele está aberto, ou
 * o contrário, é exatamente o erro que a página não pode ter.
 */

export interface Apoio {
  ligado: boolean;
  recebedor: string | null;
  mensagem: string | null;
  valores_centavos: number[];
  compra_no_app: boolean;
  chave_pix: string | null;
  link_externo: string | null;
}

const DESLIGADO: Apoio = {
  ligado: false,
  recebedor: null,
  mensagem: null,
  valores_centavos: [],
  compra_no_app: false,
  chave_pix: null,
  link_externo: null,
};

const env = import.meta.env;
const BASE = String(env.CATALOGO_API_URL || env.PUBLIC_API_URL || '').replace(/\/+$/, '');
const OBRIGATORIO = env.CATALOGO_OBRIGATORIO === '1';

async function buscar(): Promise<Apoio> {
  if (!BASE) {
    if (OBRIGATORIO) throw new Error('apoio: CATALOGO_OBRIGATORIO=1 sem URL da API');
    return DESLIGADO;
  }
  try {
    const r = await fetch(`${BASE}/v1/apoio`, {
      headers: { Accept: 'application/json' },
    });
    if (!r.ok) throw new Error(`apoio: ${r.status}`);
    const a = (await r.json()) as Apoio;
    // Só https sai do site; a API já recusa outro esquema, isto é a segunda trava.
    if (a.link_externo && !a.link_externo.startsWith('https://')) a.link_externo = null;
    return a;
  } catch (e) {
    if (OBRIGATORIO) throw e;
    console.warn(`[apoio] API indisponível (${(e as Error).message}); apoio aparece fechado.`);
    return DESLIGADO;
  }
}

// O rodapé está em todas as páginas: uma consulta por build, não uma por página.
let pendente: Promise<Apoio> | undefined;
export function apoio(): Promise<Apoio> {
  pendente ??= buscar();
  return pendente;
}
