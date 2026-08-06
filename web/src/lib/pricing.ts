import type {Locale} from "./i18n";

export type PlanAvailability = "available" | "coming-soon";

export type PricingPlan = {
  name: "Free" | "Friends" | "Club";
  availability: PlanAvailability;
  description: string;
  features: readonly string[];
};

export const pricingCopy = {
  es: {
    navLabel: "Navegación principal",
    pricingNav: "Planes",
    appNav: "Ir a la aplicación",
    accessNav: "Acceder",
    eyebrow: "PLANES · INVERSIÓN SIMULADA",
    title: "Empieza gratis. Compite con reglas claras.",
    intro: "TradeArena está disponible con Free. Friends y Club llegarán más adelante; todavía no tienen precio ni se pueden contratar.",
    available: "Disponible",
    comingSoon: "Próximamente",
    freeCta: "Empezar con Free",
    appCta: "Ir a la aplicación",
    unavailable: "Aún no disponible",
    limitsLabel: "Límites incluidos",
    plans: [
      {
        name: "Free",
        availability: "available",
        description: "Todo lo necesario para empezar una liga privada de inversión simulada.",
        features: [
          "Una liga activa",
          "Dos plazas",
          "3.000 USD de capital virtual inicial por competición"
        ]
      },
      {
        name: "Friends",
        availability: "coming-soon",
        description: "Publicaremos los detalles antes de su lanzamiento.",
        features: []
      },
      {
        name: "Club",
        availability: "coming-soon",
        description: "Publicaremos los detalles antes de su lanzamiento.",
        features: []
      }
    ]
  },
  en: {
    navLabel: "Primary navigation",
    pricingNav: "Plans",
    appNav: "Go to the app",
    accessNav: "Sign in",
    eyebrow: "PLANS · SIMULATED INVESTING",
    title: "Start for free. Compete under clear rules.",
    intro: "TradeArena is available on Free. Friends and Club will arrive later; they do not have a price and cannot be purchased yet.",
    available: "Available",
    comingSoon: "Coming soon",
    freeCta: "Start with Free",
    appCta: "Go to the app",
    unavailable: "Not available yet",
    limitsLabel: "Included limits",
    plans: [
      {
        name: "Free",
        availability: "available",
        description: "Everything you need to start a private simulated-investing league.",
        features: [
          "One active league",
          "Two seats",
          "USD 3,000 starting virtual capital per competition"
        ]
      },
      {
        name: "Friends",
        availability: "coming-soon",
        description: "We will publish the details before launch.",
        features: []
      },
      {
        name: "Club",
        availability: "coming-soon",
        description: "We will publish the details before launch.",
        features: []
      }
    ]
  }
} as const satisfies Record<Locale, {plans: readonly PricingPlan[]; [key: string]: unknown}>;

export function pricingCta(locale: Locale, authenticated: boolean) {
  return authenticated
    ? {href: `/${locale}/app`, label: pricingCopy[locale].appCta}
    : {href: `/auth/login?locale=${locale}&returnTo=/${locale}/app`, label: pricingCopy[locale].freeCta};
}
