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
}

export interface Step {
  number: number;
  title: string;
  description: string;
  icon: string;
}
