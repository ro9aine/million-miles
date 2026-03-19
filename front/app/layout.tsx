import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Million Miles Inventory",
  description: "Carsensor-backed inventory dashboard with JWT auth",
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
