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
  /** Set only on an answer taken from the community documents. */
  sources?: { section: string; document: string; community?: string }[];
}

export interface Step {
  number: number;
  title: string;
  description: string;
  icon: string;
}
