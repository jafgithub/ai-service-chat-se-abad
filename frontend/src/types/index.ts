import type { CommunityOption, DocumentResult } from "@/lib/api";

export interface ServiceCategory {
  id: string;
  title: string;
  description: string;
  icon: string;
  color: string;
  chatScope: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
  /** The documents this answer came out of, listed under it. Kept on the
   *  message rather than in one place on the page so scrolling back to an
   *  earlier answer still shows what it was based on. */
  documents?: DocumentResult[];
  /** Set when the assistant could not tell whether the question was about the
   *  community or a service. Holds the original question, so a button can ask
   *  it again down the side it names. */
  clarify?: string;
  /** The communities to choose between, the first time somebody asks about the
   *  rules and we do not know where they live. */
  pick?: CommunityOption[];
  /** A rules question this community had nothing on. Carries the community so
   *  the reply can offer somewhere to go rather than ending on "not here". */
  missedIn?: string;
  /** The question this answer was to, so "Change" can ask it again against a
   *  different community rather than making them retype it. */
  asked?: string;
  /** Whose documents answered, so the block can say so and offer to change it. */
  community?: string;
  /** What kind of answer this is. A numbered line means something different in
   *  each: "1. Blocked drain cleared: from $89.00" is bookable, "1. Provide
   *  specifications" is step one of a procedure, and drawing them the same way
   *  is what made a resident ask what "book item 1" meant. */
  variant?: "services" | "documents" | "plain";
}

export interface Step {
  number: number;
  title: string;
  description: string;
  icon: string;
}
