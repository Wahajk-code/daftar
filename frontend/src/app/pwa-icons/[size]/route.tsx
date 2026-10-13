import { ImageResponse } from "next/og";
import tokens from "../../../../design/tokens.json";

/** The home-screen icon: the Daftar mark on the ink tile, drawn at the size asked for (192, 512, or a padded maskable one). */
export async function GET(_request: Request, { params }: { params: Promise<{ size: string }> }) {
  const { size } = await params;
  const maskable = size === "maskable";
  const pixels = maskable ? 512 : size === "192" ? 192 : 512;
  const ink = tokens.primitives.gray["900"];
  const paper = tokens.primitives.gray["0"];
  // A maskable icon keeps its mark inside the middle 80% so any shape the phone cuts it to still shows all of it.
  const mark = Math.round(pixels * (maskable ? 0.52 : 0.68));
  return new ImageResponse(
    (
      <div style={{ width: "100%", height: "100%", display: "flex", alignItems: "center", justifyContent: "center", background: ink, borderRadius: maskable ? 0 : pixels * 0.22 }}>
        <svg width={mark} height={mark} viewBox="0 0 32 32" fill="none">
          <path d="M5 8.5c3.4-1.2 7-0.8 11 1.4 4-2.2 7.6-2.6 11-1.4v15.6c-3.4-1.2-7-0.8-11 1.4-4-2.2-7.6-2.6-11-1.4z" stroke={paper} strokeWidth="1.8" strokeLinejoin="round" strokeLinecap="round" />
          <path d="M16 9.9v15.6" stroke={paper} strokeWidth="1.8" strokeLinecap="round" />
          <path d="M8.2 13.2c2-.4 4-.1 6 .8M8.2 17.4c2-.4 4-.1 6 .8M17.8 14c2-.9 4-1.2 6-.8" stroke={paper} strokeWidth="1.6" strokeLinecap="round" />
        </svg>
      </div>
    ),
    { width: pixels, height: pixels },
  );
}
