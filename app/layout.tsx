import type { Metadata } from "next";
import { Geist } from "next/font/google";
import "./globals.css";
import { AppNav } from "@/components/AppNav";
import { SessionProvider } from "@/context/SessionContext";
import { Providers } from "./providers";
import { cn } from "@/lib/utils";

const geist = Geist({
  subsets: ["latin"],
  variable: "--font-sans",
});

export const metadata: Metadata = {
  title: "Billions — B-Roll Viewer",
  description: "B-roll selection viewer for Billions documentary pipeline",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={cn("dark", geist.variable)} suppressHydrationWarning>
      <body className="app-shell antialiased">
        <Providers>
          <SessionProvider>
            <AppNav />
            {children}
          </SessionProvider>
        </Providers>
      </body>
    </html>
  );
}
