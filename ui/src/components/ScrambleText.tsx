import { useEffect, useState } from "react";

const GLYPHS = "01<>/_=+*#";

export function ScrambleText({ text }: { text: string }) {
  const [shown, setShown] = useState(text);

  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setShown(text);
      return;
    }
    let frame = 0;
    const total = 14;
    const id = window.setInterval(() => {
      frame += 1;
      const reveal = Math.floor((text.length * frame) / total);
      setShown(
        text
          .split("")
          .map((char, i) => (i < reveal || char === " " ? char : GLYPHS[Math.floor(Math.random() * GLYPHS.length)]))
          .join(""),
      );
      if (frame >= total) {
        window.clearInterval(id);
        setShown(text);
      }
    }, 32);
    return () => window.clearInterval(id);
  }, [text]);

  return <span aria-label={text}>{shown}</span>;
}
