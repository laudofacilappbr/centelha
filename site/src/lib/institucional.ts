/**
 * "Sobre" e "Como fazemos" nos outros idiomas (#48). O texto acompanha as páginas em
 * português (src/pages/sobre.astro e como-fazemos.astro): mudou lá, mude aqui.
 *
 * Os blocos em `html` são escritos aqui, não vêm de fora; o site os insere como estão.
 */
import type { Lingua } from './idiomas';

export type PaginaInstitucional = 'sobre' | 'como';

type Bloco =
  | { h2: string }
  | { p: string; muted?: boolean }
  | { lista: string[] }
  | { citacao: string; fonte: string };

export interface Conteudo {
  titulo: string;
  descricao: string;
  eyebrow: string;
  h1: string;
  lede: string;
  blocos: Bloco[];
  /** Link ao fim da página (para a outra página institucional). */
  seguir?: { pagina: PaginaInstitucional; texto: string };
}

/** Caminho de cada página por idioma; o português fica na raiz. */
export const CAMINHOS: Record<PaginaInstitucional, Record<Lingua, string>> = {
  sobre: { pt: '/sobre', fr: '/fr/a-propos', es: '/es/sobre', en: '/en/about' },
  como: { pt: '/como-fazemos', fr: '/fr/comment-nous-faisons', es: '/es/como-lo-hacemos', en: '/en/how-we-make-it' },
};

// Links para páginas que só existem em português levam o aviso no idioma da página.
const pt = (href: string, texto: string, aviso: string) => `<a href="${href}" hreflang="pt-BR">${texto}</a> ${aviso}`;

export const CONTEUDO: Record<Exclude<Lingua, 'pt'>, Record<PaginaInstitucional, Conteudo>> = {
  fr: {
    sobre: {
      titulo: 'À propos du projet et de l’étincelle dans le spiritisme',
      descricao:
        'Ce qu’est Centelhar, pourquoi il est gratuit et d’où vient son nom : la question 88 du Livre des Esprits, où l’Esprit est décrit comme une étincelle éthérée.',
      eyebrow: 'À propos',
      h1: 'Une étincelle en allume une autre',
      lede: 'Centelhar transforme les œuvres d’Allan Kardec en livres audio gratuits, à écouter en voiture, dans les transports, avant de dormir ou quand lire est difficile.',
      blocos: [
        { h2: 'Ce qu’est Centelhar' },
        {
          p: 'Une application gratuite, sans publicité, qui réunit les œuvres fondamentales du spiritisme en audio. Tout le catalogue vient d’œuvres du domaine public, avec une narration produite par intelligence artificielle et relue par des personnes. Vous pouvez télécharger les chapitres pour écouter hors ligne et suivre le texte surligné pendant l’écoute.',
        },
        {
          p: 'Le projet est pensé pour les adultes curieux de la doctrine, pour ceux qui étudient déjà et veulent profiter du temps de trajet, pour les personnes qui ont du mal à lire, et pour les parents et les éducateurs, avec le profil Kids.',
        },
        { h2: 'L’étincelle dans le spiritisme' },
        {
          p: '« Centelhar » est un verbe portugais : jeter des étincelles, scintiller. Il vient de « centelha », étincelle : faire naître la lumière et la répandre. L’image vient du <cite>Livre des Esprits</cite>. À la question 88, Kardec demande si les Esprits ont une forme déterminée, limitée et constante. La réponse :',
        },
        {
          citacao:
            '« À vos yeux, non ; aux nôtres, oui ; c’est, si vous voulez, une flamme, une lueur ou une étincelle éthérée. »',
          fonte: '<cite>Le Livre des Esprits</cite>, question 88 (2<sup>e</sup> édition, Didier, 1860).',
        },
        {
          p: 'Juste après, à la question 88a, la couleur de cette étincelle « varie du sombre à l’éclat du rubis, selon que l’Esprit est plus ou moins pur ». Plus loin, à la question 92, chaque Esprit est « un centre qui rayonne de différents côtés ».',
        },
        { p: 'D’où l’idée de la marque :' },
        {
          lista: [
            '<strong>Chaque personne est une étincelle :</strong> une lumière qui existe avant le corps et continue après lui.',
            '<strong>La lumière grandit avec l’apprentissage :</strong> plus l’Esprit s’épure, plus il brille. Étudier est une façon d’allumer cette lumière.',
            '<strong>Une étincelle en allume une autre :</strong> l’application diffuse la connaissance gratuitement, d’oreille en oreille.',
          ],
        },
        { h2: 'Comment le projet se finance' },
        {
          p: `Centelhar est gratuit pour qui écoute. Les coûts (serveurs, stockage de l’audio et production de la narration) sont couverts par des dons volontaires, avec des comptes publics sur la page ${pt('/transparencia', 'transparence', '(en portugais)')}.`,
        },
      ],
      seguir: { pagina: 'como', texto: 'Voir comment nous faisons les livres audio' },
    },
    como: {
      titulo: 'Comment nous faisons : IA, relecture humaine et droits d’auteur',
      descricao:
        'Comment Centelhar produit ses livres audio spirites : uniquement des œuvres du domaine public, une narration par intelligence artificielle et la relecture de chaque passage par des personnes.',
      eyebrow: 'Comment nous faisons',
      h1: 'La technologie au service du texte',
      lede: 'Nous utilisons l’intelligence artificielle pour la narration et des personnes pour la vérification. Et nous ne publions que ce qui est dans le domaine public.',
      blocos: [
        { h2: '1. Uniquement des œuvres du domaine public' },
        {
          p: 'Les œuvres d’Allan Kardec ont été publiées au XIX<sup>e</sup> siècle et sont dans le domaine public. En français, nous utilisons les éditions originales de l’époque, comme la 2<sup>e</sup> édition du <cite>Livre des Esprits</cite> (Didier, 1860), transcrite par Wikisource. Avant d’entrer dans le catalogue, chaque édition source est enregistrée avec son origine.',
        },
        {
          p: 'C’est pourquoi Centelhar ne propose pas d’œuvres d’auteurs contemporains, encore protégées par le droit d’auteur.',
        },
        { h2: '2. Narration par intelligence artificielle' },
        {
          p: 'La voix que vous entendez est synthétique. Elle permet de narrer de longues œuvres avec une qualité constante et un coût faible, ce qui garde l’application gratuite. Nous choisissons des voix calmes et claires, avec un rythme pensé pour l’étude.',
        },
        { h2: '3. Relecture par des personnes' },
        { p: 'Aucun passage n’arrive dans l’application sans passer par des personnes. À la relecture, nous vérifions :' },
        {
          lista: [
            'que le texte narré correspond exactement à l’édition source ;',
            'la prononciation des noms, des termes de la doctrine et des mots d’autres langues ;',
            'les pauses, le rythme et l’intonation des questions et des réponses ;',
            'la synchronisation entre l’audio et le texte surligné à l’écran.',
          ],
        },
        {
          p: 'Pour les adaptations destinées aux enfants, dans le profil Kids, il y a aussi une relecture doctrinale humaine avant la publication.',
        },
        { h2: '4. Vous avez trouvé une erreur ?' },
        {
          p: `Même avec la relecture, quelque chose peut échapper. Si vous entendez un mot erroné ou une prononciation étrange, dites-le-nous sur la page ${pt('/suporte', 'd’assistance', '(en portugais)')}, en indiquant l’œuvre et le numéro de la question ou du chapitre.`,
        },
      ],
      seguir: { pagina: 'sobre', texto: 'Ce qu’est Centelhar' },
    },
  },
  es: {
    sobre: {
      titulo: 'Sobre el proyecto y la chispa en el espiritismo',
      descricao:
        'Qué es Centelhar, por qué es gratuito y de dónde viene su nombre: la pregunta 88 de El Libro de los Espíritus, donde el Espíritu se describe como una chispa etérea.',
      eyebrow: 'Sobre',
      h1: 'Una chispa enciende otra',
      lede: 'Centelhar convierte las obras de Allan Kardec en audiolibros gratuitos, para escuchar en el coche, en el autobús, antes de dormir o cuando leer es difícil.',
      blocos: [
        { h2: 'Qué es Centelhar' },
        {
          p: 'Una app gratuita, sin anuncios, que reúne las obras básicas del espiritismo en audio. Todo el catálogo viene de obras de dominio público, con narración generada por inteligencia artificial y revisada por personas. Puedes descargar los capítulos para escuchar sin conexión y seguir el texto resaltado mientras escuchas.',
        },
        {
          p: 'El proyecto está pensado para adultos curiosos sobre la doctrina, para quien ya estudia y quiere aprovechar el tiempo de los trayectos, para personas con dificultad para leer y para padres y educadores, con el perfil Kids.',
        },
        { h2: 'La chispa en el espiritismo' },
        {
          p: '«Centelhar» es un verbo portugués: echar chispas, centellear. Viene de «centelha», chispa: hacer que la luz surja y se extienda. La imagen viene de <cite>El Libro de los Espíritus</cite>. En la pregunta 88, Kardec pregunta si los Espíritus tienen una forma determinada, limitada y constante. La respuesta:',
        },
        {
          citacao: '«A vuestros ojos, no; a los nuestros, sí; es, si queréis, una llama, un resplandor o una chispa etérea.»',
          fonte: '<cite>El Libro de los Espíritus</cite>, pregunta 88. Traducción nuestra del original francés de 1860.',
        },
        {
          p: 'Justo después, en la pregunta 88a, el color de esa chispa varía de lo oscuro al brillo del rubí, según el Espíritu sea más o menos puro. Más adelante, en la pregunta 92, cada Espíritu es «un centro que irradia en diferentes direcciones».',
        },
        { p: 'De ahí la idea de la marca:' },
        {
          lista: [
            '<strong>Cada persona es una chispa:</strong> una luz que existe antes del cuerpo y continúa después de él.',
            '<strong>La luz crece con el aprendizaje:</strong> cuanto más se depura el Espíritu, más brilla. Estudiar es una forma de encender esa luz.',
            '<strong>Una chispa enciende otra:</strong> la app difunde el conocimiento gratis, de oído en oído.',
          ],
        },
        { h2: 'Cómo se mantiene el proyecto' },
        {
          p: `Centelhar es gratuito para quien escucha. Los costos (servidores, almacenamiento del audio y generación de la narración) se cubren con apoyo voluntario, con rendición de cuentas abierta en la página de ${pt('/transparencia', 'transparencia', '(en portugués)')}.`,
        },
      ],
      seguir: { pagina: 'como', texto: 'Mira cómo hacemos los audiolibros' },
    },
    como: {
      titulo: 'Cómo lo hacemos: IA, revisión humana y derechos de autor',
      descricao:
        'Cómo Centelhar produce los audiolibros espíritas: solo obras de dominio público, narración por inteligencia artificial y revisión de cada fragmento por personas.',
      eyebrow: 'Cómo lo hacemos',
      h1: 'Tecnología al servicio del texto',
      lede: 'Usamos inteligencia artificial para narrar y personas para revisar. Y solo publicamos lo que está en dominio público.',
      blocos: [
        { h2: '1. Solo obras de dominio público' },
        {
          p: 'Las obras de Allan Kardec se publicaron en el siglo XIX y están en dominio público. Usamos ediciones y traducciones que también están en dominio público. Antes de entrar en el catálogo, cada edición fuente se registra con su origen.',
        },
        {
          p: 'Por eso Centelhar no tiene obras de autores contemporáneos ni traducciones recientes, que aún están protegidas por derechos de autor.',
        },
        { h2: '2. Narración por inteligencia artificial' },
        {
          p: 'La voz que escuchas es sintética. Permite narrar obras largas con calidad constante y bajo costo, lo que mantiene la app gratuita. Elegimos voces tranquilas y claras, con un ritmo pensado para el estudio.',
        },
        { h2: '3. Revisión hecha por personas' },
        { p: 'Ningún fragmento llega a la app sin pasar por personas. En la revisión comprobamos:' },
        {
          lista: [
            'que el texto narrado corresponde exactamente a la edición fuente;',
            'la pronunciación de nombres, términos de la doctrina y palabras en otros idiomas;',
            'las pausas, el ritmo y la entonación de preguntas y respuestas;',
            'la sincronía entre el audio y el texto resaltado en la pantalla.',
          ],
        },
        { p: 'En las adaptaciones infantiles del perfil Kids también hay revisión doctrinal humana antes de publicar.' },
        { h2: '4. ¿Encontraste un error?' },
        {
          p: `Aun con revisión, algo puede escaparse. Si oyes una palabra cambiada o una pronunciación extraña, cuéntanoslo en la página de ${pt('/suporte', 'soporte', '(en portugués)')}, indicando la obra y el número de la pregunta o del capítulo.`,
        },
      ],
      seguir: { pagina: 'sobre', texto: 'Qué es Centelhar' },
    },
  },
  en: {
    sobre: {
      titulo: 'About the project and the spark in Spiritism',
      descricao:
        'What Centelhar is, why it is free and where its name comes from: question 88 of The Spirits’ Book, where the Spirit is described as an ethereal spark.',
      eyebrow: 'About',
      h1: 'One spark lights another',
      lede: 'Centelhar turns the works of Allan Kardec into free audiobooks, to listen to in the car, on the bus, before sleep or when reading is hard.',
      blocos: [
        { h2: 'What Centelhar is' },
        {
          p: 'A free app, with no ads, that brings together the core works of Spiritism in audio. The whole catalogue comes from public domain works, narrated by artificial intelligence and reviewed by people. You can download chapters to listen offline and follow the highlighted text as you listen.',
        },
        {
          p: 'The project is meant for adults curious about the doctrine, for those who already study it and want to make use of their commute, for people who find reading hard, and for parents and teachers, with the Kids profile.',
        },
        { h2: 'The spark in Spiritism' },
        {
          p: '“Centelhar” is a Portuguese verb: to give off sparks, to sparkle. It comes from “centelha”, spark: making light appear and spread. The image comes from <cite>The Spirits’ Book</cite>. In question 88, Kardec asks whether Spirits have a definite, limited and constant form. The answer:',
        },
        {
          citacao: '“To your eyes, no; to ours, yes; it is, if you will, a flame, a glow or an ethereal spark.”',
          fonte: '<cite>The Spirits’ Book</cite>, question 88. Our translation of the 1860 French original.',
        },
        {
          p: 'Right after, in question 88a, the colour of that spark ranges from dark to the brilliance of a ruby, depending on how pure the Spirit is. Later, in question 92, each Spirit is “a centre that radiates in different directions”.',
        },
        { p: 'Hence the idea behind the brand:' },
        {
          lista: [
            '<strong>Each person is a spark:</strong> a light that exists before the body and continues after it.',
            '<strong>The light grows with learning:</strong> the purer the Spirit becomes, the brighter it shines. Studying is a way of kindling that light.',
            '<strong>One spark lights another:</strong> the app spreads knowledge for free, from ear to ear.',
          ],
        },
        { h2: 'How the project is funded' },
        {
          p: `Centelhar is free for listeners. The costs (servers, audio storage and producing the narration) are covered by voluntary support, with open accounts on the ${pt('/transparencia', 'transparency page', '(in Portuguese)')}.`,
        },
      ],
      seguir: { pagina: 'como', texto: 'See how we make the audiobooks' },
    },
    como: {
      titulo: 'How we make it: AI, human review and copyright',
      descricao:
        'How Centelhar produces its Spiritist audiobooks: public domain works only, narration by artificial intelligence and every passage reviewed by people.',
      eyebrow: 'How we make it',
      h1: 'Technology in service of the text',
      lede: 'We use artificial intelligence to narrate and people to check. And we only publish what is in the public domain.',
      blocos: [
        { h2: '1. Public domain works only' },
        {
          p: 'Allan Kardec’s works were published in the 19th century and are in the public domain. We use editions and translations that are also in the public domain. Before joining the catalogue, each source edition is recorded with its origin.',
        },
        {
          p: 'That is why Centelhar has no works by contemporary authors and no recent translations, which are still protected by copyright.',
        },
        { h2: '2. Narration by artificial intelligence' },
        {
          p: 'The voice you hear is synthetic. It lets us narrate long works with steady quality and low cost, which keeps the app free. We choose calm, clear voices, at a pace made for study.',
        },
        { h2: '3. Review by people' },
        { p: 'No passage reaches the app without going through people. When reviewing, we check:' },
        {
          lista: [
            'that the narrated text matches the source edition exactly;',
            'the pronunciation of names, doctrinal terms and words in other languages;',
            'the pauses, rhythm and intonation of questions and answers;',
            'the sync between the audio and the text highlighted on screen.',
          ],
        },
        { p: 'For the children’s adaptations in the Kids profile, there is also a human doctrinal review before publishing.' },
        { h2: '4. Found a mistake?' },
        {
          p: `Even with review, something may slip through. If you hear a wrong word or an odd pronunciation, let us know on the ${pt('/suporte', 'support page', '(in Portuguese)')}, with the work and the number of the question or chapter.`,
        },
      ],
      seguir: { pagina: 'sobre', texto: 'What Centelhar is' },
    },
  },
};

/** Página inicial de cada idioma (/fr, /es, /en). */
export interface Inicio {
  titulo: string;
  descricao: string;
  eyebrow: string;
  h1: string;
  lede: string;
  obras: string;
  emBreve: string;
  como: string;
  passos: [string, string][];
  sobre: string;
}

export const INICIO: Record<Exclude<Lingua, 'pt'>, Inicio> = {
  fr: {
    titulo: 'Centelhar — les œuvres d’Allan Kardec à écouter, gratuitement',
    descricao:
      'Livres audio spirites gratuits : Le Livre des Esprits et les autres œuvres d’Allan Kardec, dans le domaine public, à écouter hors ligne en suivant le texte. Sans publicité.',
    eyebrow: 'Livres audio spirites gratuits',
    h1: 'Les œuvres d’Allan Kardec à écouter, gratuitement.',
    lede: 'Le Livre des Esprits et les autres œuvres fondamentales du spiritisme, dans leur texte original, à écouter où que vous soyez.',
    obras: 'Œuvres en français',
    emBreve: 'Les premières œuvres en français arrivent bientôt.',
    como: 'Comment nous faisons',
    passos: [
      ['Uniquement le domaine public', 'Nous n’utilisons que des œuvres et des éditions déjà dans le domaine public.'],
      ['Narration par IA', 'Une voix de synthèse, claire et calme, lit le texte de l’édition source, passage par passage.'],
      ['Relecture par des personnes', 'Chaque passage est écouté et vérifié avant d’arriver dans l’application.'],
    ],
    sobre: 'Ce qu’est Centelhar et d’où vient son nom',
  },
  es: {
    titulo: 'Centelhar — las obras de Allan Kardec para escuchar, gratis',
    descricao:
      'Audiolibros espíritas gratuitos: El Libro de los Espíritus y las demás obras de Allan Kardec, de dominio público, para escuchar sin conexión siguiendo el texto. Sin anuncios.',
    eyebrow: 'Audiolibros espíritas gratuitos',
    h1: 'Las obras de Allan Kardec para escuchar, gratis.',
    lede: 'El Libro de los Espíritus y las demás obras básicas del espiritismo, para escuchar donde estés.',
    obras: 'Obras en español',
    emBreve: 'Las primeras obras en español llegarán pronto.',
    como: 'Cómo lo hacemos',
    passos: [
      ['Solo dominio público', 'Usamos únicamente obras y ediciones que ya están en dominio público.'],
      ['Narración por IA', 'Una voz sintética, clara y serena, narra el texto de la edición fuente, fragmento a fragmento.'],
      ['Revisión por personas', 'Cada fragmento se escucha y se revisa antes de llegar a la app.'],
    ],
    sobre: 'Qué es Centelhar y de dónde viene su nombre',
  },
  en: {
    titulo: 'Centelhar — the works of Allan Kardec to listen to, for free',
    descricao:
      'Free Spiritist audiobooks: The Spirits’ Book and the other works of Allan Kardec, in the public domain, to listen to offline while following the text. No ads.',
    eyebrow: 'Free Spiritist audiobooks',
    h1: 'The works of Allan Kardec to listen to, for free.',
    lede: 'The Spirits’ Book and the other core works of Spiritism, to listen to wherever you are.',
    obras: 'Works in English',
    emBreve: 'The first works in English are coming soon.',
    como: 'How we make it',
    passos: [
      ['Public domain only', 'We only use works and editions that are already in the public domain.'],
      ['AI narration', 'A clear, calm synthetic voice reads the text of the source edition, passage by passage.'],
      ['Reviewed by people', 'Every passage is listened to and checked before it reaches the app.'],
    ],
    sobre: 'What Centelhar is and where its name comes from',
  },
};
