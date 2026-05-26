import type { Metadata } from "next";
import { Providers } from "./providers";
import { Sidebar } from "@/components/layout/sidebar";
import "./globals.css";

export const metadata: Metadata = {
  title: "Opus Backtrader",
  description: "AI-powered quantitative trading system",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body>
        <Providers>
          <div className="flex min-h-screen">
            <Sidebar />
            <main className="ml-60 flex-1 p-6">{children}</main>
          </div>
        </Providers>
      </body>
    </html>
  );
}
