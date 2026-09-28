import { useEffect, useState } from "react";
import Ballhog78 from "./Ballhog78";
import Ballhog80 from "./Ballhog80";

function routeOf(): "78" | "80" {
  const hash = window.location.hash.replace(/^#/, "");
  if (hash === "/first80" || hash === "/80") return "80";
  return "78";
}

export default function App() {
  const [route, setRoute] = useState(routeOf);

  useEffect(() => {
    const onHash = () => setRoute(routeOf());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  return route === "80" ? <Ballhog80 /> : <Ballhog78 />;
}
