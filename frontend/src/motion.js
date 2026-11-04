import { useEffect } from "react";

// A single observer per route. Content stays visible if JS or motion is unavailable.
export function useReveals(routeKey) {
  useEffect(() => {
    if (!window.IntersectionObserver || window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) return;
    const observer = new IntersectionObserver((entries) => {
      entries.forEach(({ target, isIntersecting }) => {
        if (!isIntersecting) return;
        target.classList.remove("reveal-pending");
        observer.unobserve(target);
      });
    }, { threshold: 0.08 });
    const elements = document.querySelectorAll(".family-section, .section-heading, .quiz-banner, .values");
    elements.forEach((element) => {
      if (element.getBoundingClientRect().top < window.innerHeight) return;
      element.classList.add("reveal-pending");
      observer.observe(element);
    });
    return () => {
      observer.disconnect();
      elements.forEach((element) => element.classList.remove("reveal-pending"));
    };
  }, [routeKey]);
}
