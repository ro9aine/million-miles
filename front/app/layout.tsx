import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Million Miles",
  description: "Next.js frontend for Million Miles",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
