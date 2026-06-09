import { ImageResponse } from "next/og";
import { OG_ALT, OG_SIZE, RicoOgImage } from "@/components/og/ricoOgImage";

// File-convention route: Next injects the resulting PNG as <meta property="og:image">.
export const runtime = "edge";
export const alt = OG_ALT;
export const size = OG_SIZE;
export const contentType = "image/png";

export default function OpengraphImage() {
    return new ImageResponse(RicoOgImage(), { ...OG_SIZE });
}
