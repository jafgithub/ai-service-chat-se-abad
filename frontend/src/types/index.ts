import type { RequestTrace } from "@/components/chat/RequestJourney";

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
  /** Set when the assistant could not match the message to anything. Holds the
   *  original question so it can be asked again. */
  clarify?: string;
  /** The question this answer was to. */
  asked?: string;
  /** What kind of answer this is. A numbered line means something different in
   *  each: "1. Blocked drain cleared: from $89.00" is bookable, "1. Provide
   *  specifications" is step one of a procedure, and drawing them the same way
   *  is what made a resident ask what "book item 1" meant. */
  variant?: "services" | "plain";
  /** Where this answer came from and how long each stage took, measured on the
   *  server. Absent on an older backend or a failed request, and the screen
   *  simply shows nothing extra when it is. */
  trace?: RequestTrace;
}

export interface Step {
  number: number;
  title: string;
  description: string;
  icon: string;
}
