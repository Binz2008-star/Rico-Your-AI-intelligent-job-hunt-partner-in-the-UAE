import { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Rico Hunt",
    short_name: "Rico Hunt",
    description: "Your AI job-hunt partner in the UAE. Upload your CV and Rico finds matching jobs, tracks your applications, and guides your next move.",
    start_url: "/command",
    scope: "/",
    display: "standalone",
    orientation: "portrait",
    theme_color: "#0a0a1a",
    background_color: "#0a0a1a",
    icons: [
      {
        src: "/icons/icon-192.png",
        sizes: "192x192",
        type: "image/png",
        purpose: "any",
      },
      {
        src: "/icons/icon-512.png",
        sizes: "512x512",
        type: "image/png",
        purpose: "any",
      },
      {
        src: "/icons/icon-192.png",
        sizes: "192x192",
        type: "image/png",
        purpose: "maskable",
      },
      {
        src: "/icons/icon-512.png",
        sizes: "512x512",
        type: "image/png",
        purpose: "maskable",
      },
    ],
  };
}
