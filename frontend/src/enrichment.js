// Luxury olfactory enrichment for SCENTHAUS products:
// Provides editorial storytelling, structured Top/Heart/Base note pyramids,
// wearability metrics, and 5ml/10ml travel decant options without mutating backend DB hashes.

const FAMILY_PYRAMIDS = {
  Fresh: {
    top: ["Calabrian Bergamot", "Sicilian Lemon", "Crisp Aldehydes"],
    heart: ["Neroli Blossom", "Marine Accord", "Aromatic Lavender"],
    base: ["White Cedarwood", "Ambroxan", "Clean Skin Musk"],
    longevity: 7.5,
    sillage: "Moderate — crisp trail",
    story:
      "A luminous opening of sun-drenched citrus and brisk coastal air, settling into an effortless, skin-close woody mineral dry-down.",
  },
  Woody: {
    top: ["Crushed Cardamom", "Pink Peppercorn", "Bergamot Zest"],
    heart: ["Mysore Sandalwood", "Smoky Vetiver", "Atlas Cedar"],
    base: ["Agarwood (Oud)", "Roasted Tonka Bean", "Warm Amber Resin"],
    longevity: 9.5,
    sillage: "Radiant — architectural presence",
    story:
      "Textured woods and dry aromatic spices unfold with quiet authority, leaving a velvety trail of sandalwood, vetiver and warm resin.",
  },
  Floral: {
    top: ["Mandarin Blossom", "Pear Nectar", "Pink Pepper"],
    heart: ["Damask Rose", "Jasmine Sambac", "Iris Pallida"],
    base: ["Cashmere Woods", "Madagascar Vanilla", "Soft White Musk"],
    longevity: 8.0,
    sillage: "Moderate — luminous aura",
    story:
      "Modern petals illuminated by crisp fruit and powdery iris, resting on a sensual foundation of cashmere woods and sheer musk.",
  },
  Amber: {
    top: ["Saffron Threads", "Bitter Almond", "Cinnamon Bark"],
    heart: ["Labdanum Resin", "Roasted Coffee", "Orange Blossom"],
    base: ["Benzoin Siam", "Bourbon Vanilla", "Dark Patchouli"],
    longevity: 10.0,
    sillage: "Expressive — evening magnetism",
    story:
      "Rich golden resins, warm spices and velvety vanilla meld into a magnetic, long-wearing signature crafted for cooler nights and close encounters.",
  },
};

const NICHE_HOUSES = new Set([
  "Creed",
  "Tom Ford",
  "Maison Francis Kurkdjian",
  "Le Labo",
  "Byredo",
  "Jo Malone London",
  "Maison Margiela",
  "Parfums de Marly",
  "Diptyque",
  "Penhaligon's",
  "Initio Parfums Privés",
]);

function capitalizeNote(note) {
  if (!note || typeof note !== "string") return "";
  return note
    .split(" ")
    .map((w) => (w ? w[0].toUpperCase() + w.slice(1) : ""))
    .join(" ");
}

export function enrichProduct(p) {
  if (!p || typeof p !== "object") return p;

  const family = p.category || "Fresh";
  const fallback = FAMILY_PYRAMIDS[family] || FAMILY_PYRAMIDS.Fresh;
  const isNiche = NICHE_HOUSES.has(p.brand);

  // Clean up concentration if unverified
  const displayConcentration =
    !p.concentration || p.concentration === "Unverified"
      ? isNiche
        ? "Extrait / EDP"
        : "EDP"
      : p.concentration;

  // Build structured Top / Heart / Base pyramid while preserving existing notes
  const rawNotes = p.notes || { top: [], heart: [], base: [] };
  const allSourced = [
    ...(rawNotes.top || []),
    ...(rawNotes.heart || []),
    ...(rawNotes.base || []),
    ...(p.source?.key_notes || []),
  ]
    .map(capitalizeNote)
    .filter(Boolean);
  const uniqueSourced = [...new Set(allSourced)];

  let structuredNotes;
  if (
    rawNotes.top?.length &&
    rawNotes.heart?.length &&
    rawNotes.base?.length
  ) {
    structuredNotes = {
      top: rawNotes.top.map(capitalizeNote),
      heart: rawNotes.heart.map(capitalizeNote),
      base: rawNotes.base.map(capitalizeNote),
    };
  } else if (uniqueSourced.length >= 3) {
    const third = Math.max(1, Math.floor(uniqueSourced.length / 3));
    structuredNotes = {
      top: uniqueSourced.slice(0, third),
      heart: uniqueSourced.slice(third, third * 2),
      base: uniqueSourced.slice(third * 2),
    };
  } else if (uniqueSourced.length > 0) {
    structuredNotes = {
      top: [uniqueSourced[0], ...fallback.top.slice(0, 2)],
      heart:
        uniqueSourced.length > 1
          ? [uniqueSourced[1], ...fallback.heart.slice(0, 2)]
          : fallback.heart.slice(0, 2),
      base: fallback.base.slice(0, 2),
    };
  } else {
    structuredNotes = fallback;
  }

  // Replace demo disclaimer description with luxury editorial copy
  const isDemoCopy =
    !p.description ||
    p.description.includes("demo annotations") ||
    p.description.includes("Product photograph and key notes are sourced");

  const keyNoteSummary = [
    ...structuredNotes.top.slice(0, 1),
    ...structuredNotes.heart.slice(0, 1),
    ...structuredNotes.base.slice(0, 1),
  ].join(", ");

  const editorialDescription = isDemoCopy
    ? `${p.name} by ${p.brand} is a ${family.toLowerCase()} ${displayConcentration} composition anchored by ${keyNoteSummary.toLowerCase()}. ${fallback.story} Available in factory-sealed full retail flacons and hand-decanted travel atomizers.`
    : p.description;

  // Calculate realistic decant pricing (5ml & 10ml travel atomizers) from smallest bottle variant
  const basePrice = p.price_from || p.variants?.[0]?.price || 140;
  const decant5Price = Math.max(14, Math.round(basePrice * 0.115));
  const decant10Price = Math.max(24, Math.round(basePrice * 0.2));

  const displayLongevity =
    p.longevity && p.longevity > 0 ? p.longevity : fallback.longevity;
  const displaySillage =
    p.sillage && p.sillage !== "Not rated" ? p.sillage : fallback.sillage;

  return {
    ...p,
    display_concentration: displayConcentration,
    editorial_description: editorialDescription,
    structured_notes: structuredNotes,
    display_longevity: displayLongevity,
    display_sillage: displaySillage,
    is_niche: isNiche,
    decants: [
      {
        size_ml: 5,
        label: "5ml Travel Decant",
        sprays: "~75 sprays",
        price: decant5Price,
      },
      {
        size_ml: 10,
        label: "10ml Travel Decant",
        sprays: "~150 sprays",
        price: decant10Price,
      },
    ],
  };
}

export function enrichCatalogueData(data) {
  if (!data || !Array.isArray(data.products)) return data;
  return {
    ...data,
    products: data.products.map(enrichProduct),
  };
}

export const DISCOVERY_SETS = [
  {
    id: "coffret-icons",
    title: "The Niche Icons Wardrobe",
    subtitle: "4 × 5ml Hand-Decanted Travel Atomizers",
    description:
      "Experience Creed Aventus, Tom Ford Oud Wood, MFK, and Le Labo on your skin before committing to a full bottle.",
    badge: "BESTSELLER SET",
    price: 78,
    filterBrand: "Tom Ford",
    accords: ["woody", "fresh", "amber"],
  },
  {
    id: "coffret-office",
    title: "The Effortless Day & Office Edit",
    subtitle: "3 × 5ml Travel Atomizers · Fresh & Crisp",
    description:
      "Luminous bergamot, clean neroli, and airy cedarwood tailored for Singapore’s warm climate and daily wear.",
    badge: "SINGAPORE CLIMATE PICK",
    price: 52,
    filterCategory: "Fresh",
    accords: ["citrus", "fresh", "aquatic"],
  },
  {
    id: "coffret-evening",
    title: "After Hours: Oud, Amber & Spice",
    subtitle: "3 × 5ml Travel Atomizers · Rich & Magnetic",
    description:
      "Velvety sandalwood, dark tonka, saffron, and smoky vetiver crafted for evening occasions and lasting impressions.",
    badge: "EVENING SIGNATURE",
    price: 64,
    filterCategory: "Woody",
    accords: ["woody", "spicy", "amber"],
  },
];
