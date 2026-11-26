import { useEffect, useState } from "react";
import App from "./App";
import { HomePage } from "./components/HomePage";

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

  return view === "console" ? <App onHome={home} /> : <HomePage onOpen={open} onImported={open} />;
}
