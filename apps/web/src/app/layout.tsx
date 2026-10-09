import type { Metadata } from "next";
import "@fontsource/manrope/400.css";
import "@fontsource/manrope/500.css";
import "@fontsource/manrope/600.css";
import "@fontsource/manrope/700.css";
import "@fontsource/manrope/800.css";
import "./globals.css";
import { AppProvider } from "@/components/system";
export const metadata: Metadata = {
  title: {
    default: "EPISIGHT — Dari sinyal menuju pemahaman",
    template: "%s · EPISIGHT",
  },
  description:
    "Investigation copilot untuk episode integrity. Telusuri episode, sumber bukti, dan brief untuk peninjauan manusia.",
};
export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="id" data-scroll-behavior="smooth">
      <body>
        <AppProvider>{children}</AppProvider>
      </body>
    </html>
  );
}
