import type { Metadata } from "next";
import { DiscussionApp } from "./DiscussionApp";

export const metadata: Metadata = {
  title: "Discussion — Hawk",
  description: "Ask the panel a question and watch the models think, vote, and conclude.",
};

export default function DiscussionPage() {
  return <DiscussionApp />;
}
