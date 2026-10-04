import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { Splash } from "./_components/Splash";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Hawk — Convene a panel of AI models",
  description:
    "Several AI models debate your coding question in rounds, vote Approve or Reject, and one of them writes the verdict.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        <Splash />
        {children}
      </body>
    </html>
  );
}
