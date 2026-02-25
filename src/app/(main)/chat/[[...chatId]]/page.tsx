'use client';
import { useChatHistory } from '@/lib/hooks';
import { ChatPanel } from '@/components/chat-panel';

export default function ChatPage({ params }: { params: { chatId?: string[] } }) {
  const chatId = params.chatId?.[0];
  const { getConversation } = useChatHistory();
  const initialConversation = getConversation(chatId);

  return <ChatPanel initialConversation={initialConversation} chatId={chatId} />;
}
