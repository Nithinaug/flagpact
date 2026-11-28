import { useEffect, useState } from "react";
import App from "./App";
import { HomePage } from "./components/HomePage";
import { STATIC } from "./api";

const direct = () => new URLSearchParams(window.location.search).has("demo") || window.location.pathname.replace(/\/$/, "") === "/demo";
const initial = () => (direct() || window.location.hash === "#console" ? "console" : "home");

export default function Root() {
  const [view, setView] = useState<"home" | "console">(initial);

  useEffect(() => {
    const onHash = () => setView(direct() || window.location.hash === "#console" ? "console" : "home");
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  const open = () => {
    window.location.hash = "console";
    setView("console");
    window.scrollTo(0, 0);
  };
  const home = () => {
    history.pushState(null, "", window.location.pathname === "/demo" ? "/" : window.location.pathname);
    setView("home");
  };

  const page = view === "console" ? <App onHome={home} /> : <HomePage onOpen={open} onImported={open} />;
  if (!STATIC) return page;
  return (
    <>
      {page}
      <aside className="fixed bottom-3 right-3 z-50 max-w-xs rounded-lg bg-black/80 px-4 py-3 text-xs leading-relaxed text-ink-muted shadow-lg">
        Recorded replay of real flagpact output. Nothing runs in this page. To use flagpact on your own Flagsmith:{" "}
        <code className="text-ink">pip install flagpact</code>{" "}
        <a className="underline" href="https://github.com/Nithinaug/flagpact">GitHub</a>
      </aside>
    </>
  );
}
