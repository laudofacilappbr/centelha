import { SITE } from '../config';

export function organizationLd(site: URL) {
  return {
    '@context': 'https://schema.org',
    '@type': 'Organization',
    name: SITE.nome,
    url: site.href,
    logo: new URL('/brand/app-icon-1024.png', site).href,
    email: SITE.emailSuporte,
    ...(SITE.redes.length ? { sameAs: SITE.redes.map((r) => r.url) } : {}),
  };
}

export function mobileApplicationLd(site: URL) {
  return {
    '@context': 'https://schema.org',
    '@type': 'MobileApplication',
    name: SITE.nome,
    description: SITE.descricaoPadrao,
    url: site.href,
    image: new URL('/brand/app-icon-1024.png', site).href,
    applicationCategory: 'EducationalApplication',
    applicationSubCategory: 'Audiolivros',
    operatingSystem: 'iOS, Android',
    inLanguage: 'pt-BR',
    isAccessibleForFree: true,
    offers: { '@type': 'Offer', price: '0', priceCurrency: 'BRL' },
    publisher: { '@type': 'Organization', name: SITE.nome, url: site.href },
  };
}

export function faqLd(items: { pergunta: string; resposta: string }[]) {
  return {
    '@context': 'https://schema.org',
    '@type': 'FAQPage',
    mainEntity: items.map((i) => ({
      '@type': 'Question',
      name: i.pergunta,
      acceptedAnswer: { '@type': 'Answer', text: i.resposta },
    })),
  };
}
