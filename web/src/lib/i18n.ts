export const locales = ["es", "en"] as const;
export type Locale = typeof locales[number];

export function isLocale(value: string): value is Locale {
  return locales.includes(value as Locale);
}

export const copy = {
  es: {
    tagline: "Compite con criterio. Aprende sin jugarte tu dinero.",
    taglineAccent: "Compite con criterio.",
    taglineMain: "Aprende sin jugarte tu dinero.",
    intro: "Ligas privadas de inversión simulada con reglas claras, una cartera virtual de 3.000 USD y cero ruido.",
    access: "Acceder o crear cuenta",
    eyebrow: "INVERSIÓN SIMULADA · LIGAS PRIVADAS",
    featureOne: "La misma salida para todos",
    featureOneText: "Reglas versionadas y rentabilidad comparable, sin atajos invisibles.",
    featureTwo: "Privado por diseño",
    featureTwoText: "Tus ligas no se enumeran y una persona ajena siempre recibe 404.",
    featureThree: "Primero aprende",
    featureThreeText: "Dinero virtual, decisiones reales y una experiencia deliberadamente tranquila.",
    featureHeading: "Una arena diseñada para aprender",
    featureIntro: "Compara decisiones y rentabilidad con reglas transparentes, sin convertir la experiencia en ruido.",
    previewLabel: "Pulso de la liga",
    previewLive: "Simulación activa",
    previewPeriod: "Temporada actual",
    profile: "Tu perfil",
    profileIntro: "Necesitamos estos datos antes de entrar en la arena.",
    displayName: "Nombre visible",
    birthDate: "Fecha de nacimiento",
    terms: "Confirmo que tengo 18 años o más y acepto las condiciones de uso.",
    save: "Guardar y continuar",
    welcome: "Bienvenida a la arena",
    accountReady: "Tu cuenta está preparada. La creación de ligas llega en TA-032.",
    editProfile: "Editar perfil",
    logout: "Cerrar sesión",
    authError: "No se pudo completar el acceso. Inténtalo de nuevo.",
    language: "Idioma"
  },
  en: {
    tagline: "Compete thoughtfully. Learn without risking your money.",
    taglineAccent: "Compete thoughtfully.",
    taglineMain: "Learn without risking your money.",
    intro: "Private simulated-investing leagues with clear rules, a USD 3,000 virtual portfolio and zero noise.",
    access: "Sign in or create account",
    eyebrow: "SIMULATED INVESTING · PRIVATE LEAGUES",
    featureOne: "The same starting line",
    featureOneText: "Versioned rules and comparable returns, with no invisible shortcuts.",
    featureTwo: "Private by design",
    featureTwoText: "Your leagues cannot be enumerated; outsiders always receive a 404.",
    featureThree: "Learning comes first",
    featureThreeText: "Virtual money, real decisions and a deliberately calm experience.",
    featureHeading: "An arena built for learning",
    featureIntro: "Compare decisions and returns under transparent rules, without turning the experience into noise.",
    previewLabel: "League pulse",
    previewLive: "Simulation live",
    previewPeriod: "Current season",
    profile: "Your profile",
    profileIntro: "We need these details before you enter the arena.",
    displayName: "Display name",
    birthDate: "Date of birth",
    terms: "I confirm I am 18 or older and accept the terms of use.",
    save: "Save and continue",
    welcome: "Welcome to the arena",
    accountReady: "Your account is ready. League creation arrives in TA-032.",
    editProfile: "Edit profile",
    logout: "Sign out",
    authError: "We could not complete sign-in. Please try again.",
    language: "Language"
  }
} as const;
