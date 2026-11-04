// Only local catalogue images have build-time responsive alternatives.
export function productImageSources(src) {
  if (!/^\/images\/products\/[^/]+\.(png|jpe?g)$/i.test(src || "")) return { src };
  const base = src.replace(/\.(png|jpe?g)$/i, "");
  return {
    src: `${base}-640.webp`,
    srcSet: `${base}-320.webp 320w, ${base}-640.webp 640w`,
  };
}

export default function ProductImage({ src, alt, sizes = "(max-width: 800px) 45vw, 23vw", ...props }) {
  return <img {...props} {...productImageSources(src)} sizes={sizes} alt={alt} />;
}
