import type {MetadataRoute} from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "TradeArena",
    short_name: "TradeArena",
    description: "Private simulated-investing leagues",
    start_url: "/",
    display: "standalone",
    background_color: "#000000",
    theme_color: "#2962ff",
    icons: [{src: "/icon.svg", sizes: "any", type: "image/svg+xml", purpose: "maskable"}]
  };
}
