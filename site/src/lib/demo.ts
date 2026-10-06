/**
 * Dados do player de demonstração da landing: questão 88 de O Livro dos Espíritos.
 *
 * Com a obra publicada, vem da API: texto revisado e o trecho da questão dentro do
 * áudio do capítulo (não há arquivo só da questão; o player toca do início do
 * primeiro segmento ao fim do último). Sem API, ou antes da publicação, usa
 * src/data/q88.json, para o build e o CI funcionarem sem o catálogo.
 */
import q88 from '../data/q88.json';
import { audioAberto, type Segmento } from './catalogo';
import { questoesDoLivroDosEspiritos } from './questoes';

export const QUESTAO_DEMO = 88;

export interface SegmentoDemo {
  /** Segundos, relativos ao início da questão. */
  inicio: number;
  fim: number;
  papel: string;
  texto: string;
}

export interface Demo {
  obra: string;
  referencia: string;
  traducao: string;
  /** Áudio e o trecho dele, em segundos; null quando ainda não há áudio publicado. */
  audio: { url: string; inicio: number; fim: number } | null;
  segmentos: SegmentoDemo[];
  /** De onde vieram os dados, para o build avisar. */
  origem: 'api' | 'estatico';
}

function estatico(): Demo {
  return {
    obra: q88.obra,
    referencia: q88.referencia,
    traducao: q88.traducao,
    audio: { url: q88.audio, inicio: 0, fim: q88.segmentos[q88.segmentos.length - 1].fim },
    segmentos: q88.segmentos,
    origem: 'estatico',
  };
}

function rotulo(s: Segmento): string {
  return `${s.numero_questao}${s.subquestao ?? ''}.`;
}

export async function demoQ88(): Promise<Demo> {
  const dados = await questoesDoLivroDosEspiritos();
  const q = dados?.questoes.find((x) => x.numero === QUESTAO_DEMO);
  if (!dados || !q) return estatico();

  const faixa = q.capitulo.faixa;
  const tempos = new Map(faixa?.marcacoes.map((m) => [m.segmento_id, m]) ?? []);
  // Áudio só se cada segmento da questão tiver marcação: com buraco, o destaque do
  // texto sairia do compasso da voz, e é isso que a demonstração quer mostrar.
  // Faixa cifrada (ADR 0004) não toca no navegador: fica só o texto.
  const comAudio = audioAberto(faixa) && q.segmentos.every((s) => tempos.has(s.id));
  const inicioMs = comAudio ? Math.min(...q.segmentos.map((s) => tempos.get(s.id)!.inicio_ms)) : 0;
  const fimMs = comAudio ? Math.max(...q.segmentos.map((s) => tempos.get(s.id)!.fim_ms)) : 0;
  const rel = (ms: number) => (ms - inicioMs) / 1000;

  const segmentos: SegmentoDemo[] = [];
  let ultimoRotulo = '';
  for (const s of q.segmentos) {
    const t = tempos.get(s.id);
    const inicio = comAudio && t ? rel(t.inicio_ms) : 0;
    const fim = comAudio && t ? rel(t.fim_ms) : 0;
    // "88." e "88a." como na edição impressa; duração zero, nunca destacados.
    const r = rotulo(s);
    if (r !== ultimoRotulo) {
      segmentos.push({ inicio, fim: inicio, papel: 'numero', texto: r });
      ultimoRotulo = r;
    }
    segmentos.push({ inicio, fim, papel: s.tipo, texto: s.texto });
  }

  return {
    obra: dados.ed.titulo,
    referencia: q.capitulo.titulo,
    traducao: dados.ed.tradutor ? `Tradução de ${dados.ed.tradutor}` : q88.traducao,
    audio: comAudio ? { url: faixa!.url, inicio: inicioMs / 1000, fim: fimMs / 1000 } : null,
    segmentos,
    origem: 'api',
  };
}
