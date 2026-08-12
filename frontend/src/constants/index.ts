import type { ProductCategory, Step } from "@/types";

export const PRODUCT_CATEGORIES: ProductCategory[] = [
  {
    id: "home",
    title: "Home & Repairs",
    description: "Plumbers, electricians, handypeople, heating and appliances.",
    icon: "🔧",
    color: "from-amber-500 to-orange-600",
    chatScope: "home repairs, plumbing, electrics and heating",
  },
  {
    id: "pets",
    title: "Pets & Vets",
    description: "Vets, vaccinations, grooming, and pet sitting.",
    icon: "🐾",
    color: "from-green-500 to-emerald-600",
    chatScope: "vets, pet grooming and pet care",
  },
  {
    id: "health",
    title: "Health & Wellbeing",
    description: "Dentists, physiotherapy, opticians and clinics.",
    icon: "🩺",
    color: "from-sky-400 to-blue-500",
    chatScope: "health, dental, physiotherapy and clinics",
  },
  {
    id: "community",
    title: "Community",
    description: "Local halls, classes, groups and council services.",
    icon: "🏘️",
    color: "from-violet-500 to-purple-600",
    chatScope: "community services, classes and local groups",
  },
  {
    id: "cleaning",
    title: "Cleaning & Garden",
    description: "Cleaners, gardeners, window cleaners and waste.",
    icon: "🧹",
    color: "from-teal-500 to-cyan-600",
    chatScope: "cleaning, gardening and waste removal",
  },
  {
    id: "motoring",
    title: "Motoring",
    description: "Servicing, tyres, mobile mechanics and inspections.",
    icon: "🚗",
    color: "from-red-500 to-rose-600",
    chatScope: "car servicing, tyres and mechanics",
  },
];

export const HOW_IT_WORKS_STEPS: Step[] = [
  {
    number: 1,
    title: "Tell us what has gone wrong",
    description: "Describe it in your own words, by typing or speaking. No need to know what it is called.",
    icon: "💬",
  },
  {
    number: 2,
    title: "We work out what is needed",
    description: "You get the service, what it usually costs, and how long it takes.",
    icon: "🔧",
  },
  {
    number: 3,
    title: "Pick a time",
    description: "Choose from the next available appointments and get a confirmation by email and text.",
    icon: "📅",
  },
];

export const BRAND_NAME = "Service Assistant";
export const BRAND_TAGLINE = "Describe what you need. Book someone who does it.";
