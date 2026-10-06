import {
  obrasPublicadas,
  edicaoDoSite,
  edicao,
  capitulo,
  type Capitulo,
  type Edicao,
  type Obra,
  type Segmento,
} from './catalogo';

/** Só O Livro dos Espíritos tem uma página por questão (1 a 1019). */
export const OBRA_COM_QUESTOES = 'o-livro-dos-espiritos';

/** URL permanente; nunca mudar depois de publicada. */
export function urlQuestao(n: number): string {
  return `/livro-dos-espiritos/questao/${n}`;
}

export interface Questao {
  numero: number;
  segmentos: Segmento[];
  capitulo: Capitulo;
}

export interface QuestoesDaObra {
  obra: Obra;
  ed: Edicao;
  questoes: Questao[];
}

const porEdicao = new Map<number, Promise<Questao[]>>();

/** Lê todos os capítulos publicados da edição e agrupa os segmentos por questão. */
export function questoesDaEdicao(ed: Edicao): Promise<Questao[]> {
  if (!porEdicao.has(ed.id)) {
    porEdicao.set(
      ed.id,
      (async () => {
        const porNumero = new Map<number, Questao>();
        for (const c of ed.capitulos) {
          const cap = await capitulo(c.id);
          for (const s of cap.segmentos) {
            if (s.numero_questao == null) continue;
            const q = porNumero.get(s.numero_questao) ?? { numero: s.numero_questao, segmentos: [], capitulo: cap };
            q.segmentos.push(s);
            porNumero.set(s.numero_questao, q);
          }
        }
        return [...porNumero.values()].sort((a, b) => a.numero - b.numero);
      })(),
    );
  }
  return porEdicao.get(ed.id)!;
}

let carregado: Promise<QuestoesDaObra | null> | undefined;

/** As questões da edição em português, que tem as URLs permanentes. */
export function questoesDoLivroDosEspiritos(): Promise<QuestoesDaObra | null> {
  carregado ??= (async () => {
    const obra = (await obrasPublicadas()).find((o) => o.slug === OBRA_COM_QUESTOES);
    const resumo = obra && edicaoDoSite(obra);
    if (!obra || !resumo) return null;
    const ed = await edicao(resumo.id);
    return { obra, ed, questoes: await questoesDaEdicao(ed) };
  })();
  return carregado;
}
