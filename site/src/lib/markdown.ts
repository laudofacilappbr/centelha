/**
 * Markdown restrito dos posts do blog: parágrafos, "## " e "### ", listas com "- ",
 * **negrito**, *itálico* e [links](url).
 *
 * Todo o texto é escapado ANTES de interpretar: HTML escrito no admin vira texto,
 * nunca marcação. Link só aceita http(s) ou caminho do próprio site; "javascript:"
 * e afins ficam como texto. Uma biblioteca de Markdown completa aceitaria HTML cru
 * e pediria um sanitizador à parte; este subconjunto cobre o que o blog usa.
 */

function escapar(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

const URL_OK = /^(https:\/\/|http:\/\/|\/(?!\/))[^\s*]*$/;

function inline(texto: string): string {
  return texto
    .replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, (todo, rotulo: string, url: string) => {
      if (!URL_OK.test(url)) return todo;
      const externo = !url.startsWith('/');
      return `<a href="${url}"${externo ? ' rel="noopener noreferrer"' : ''}>${rotulo}</a>`;
    })
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/\*([^*]+)\*/g, '<em>$1</em>');
}

export function renderizar(md: string): string {
  const blocos = escapar(md.replace(/\r\n/g, '\n'))
    .split(/\n\s*\n/)
    .map((b) => b.trim())
    .filter(Boolean);
  return blocos
    .map((b) => {
      const h = /^(#{2,3}) (.+)$/.exec(b);
      if (h && !b.includes('\n')) {
        const n = h[1].length;
        return `<h${n}>${inline(h[2])}</h${n}>`;
      }
      const linhas = b.split('\n');
      if (linhas.every((l) => l.startsWith('- '))) {
        return `<ul>${linhas.map((l) => `<li>${inline(l.slice(2))}</li>`).join('')}</ul>`;
      }
      return `<p>${inline(linhas.join(' '))}</p>`;
    })
    .join('\n');
}
