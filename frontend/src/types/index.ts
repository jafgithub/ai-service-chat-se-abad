export interface ProductCategory {
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

export interface OrderDetails {
  name: string;
  phone: string;
  email: string;
  items: OrderItem[];
  category?: string;
}

export interface OrderItem {
  product: string;
  quantity: number;
  unit: string;
}

export interface Step {
  number: number;
  title: string;
  description: string;
  icon: string;
}
