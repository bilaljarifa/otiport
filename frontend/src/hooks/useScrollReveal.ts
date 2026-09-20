import { useEffect, useRef } from "react";

/**
 * Adds `is-visible` to the returned ref's element once it scrolls into
 * view, pairing with the `.reveal`/`.reveal-stagger` CSS in `index.css`
 * (which only animates under `prefers-reduced-motion: no-preference` —
 * this hook still adds the class either way, it's the CSS that no-ops).
 * Fires once per element, then disconnects — a marketing page section
 * doesn't need to re-hide itself on scroll-back-up.
 */
export function useScrollReveal<T extends HTMLElement>() {
  const ref = useRef<T | null>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          el.classList.add("is-visible");
          observer.disconnect();
        }
      },
      { threshold: 0.15, rootMargin: "0px 0px -60px 0px" },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  return ref;
}
