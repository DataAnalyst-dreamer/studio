export type Message = {
  id: string;
  role: 'user' | 'assistant';
  content: string;
};

export type Conversation = {
  id: string;
  title: string;
  messages: Message[];
  createdAt: number;
};

export type Settings = {
  aiTone: 'formal' | 'casual' | 'witty';
  responseVerbosity: 'concise' | 'detailed' | 'balanced';
};
