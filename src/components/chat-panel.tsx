'use client';
import { useState, useEffect, useRef } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { useChatHistory } from '@/lib/hooks';
import type { Message, Conversation } from '@/lib/types';
import { getChatResponse } from '@/app/actions';
import { ScrollArea } from './ui/scroll-area';
import { Input } from './ui/input';
import { Button } from './ui/button';
import { Send, CornerDownLeft } from 'lucide-react';
import ChatMessage from './chat-message';
import { useToast } from '@/hooks/use-toast';

interface ChatPanelProps {
  initialConversation?: Conversation;
  chatId?: string;
}

export function ChatPanel({ initialConversation, chatId }: ChatPanelProps) {
  const [conversation, setConversation] = useState<Conversation>(
    initialConversation || {
      id: chatId || `chat-${Date.now()}`,
      title: 'New Chat',
      messages: [],
      createdAt: Date.now(),
    }
  );
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const { saveConversation } = useChatHistory();
  const router = useRouter();
  const scrollAreaRef = useRef<HTMLDivElement>(null);
  const { toast } = useToast();

  useEffect(() => {
    if (scrollAreaRef.current) {
      scrollAreaRef.current.scrollTo({
        top: scrollAreaRef.current.scrollHeight,
        behavior: 'smooth',
      });
    }
  }, [conversation.messages]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    const userMessage: Message = { id: `msg-${Date.now()}`, role: 'user', content: input };
    const updatedMessages = [...conversation.messages, userMessage];

    const updatedConversation = {
      ...conversation,
      messages: updatedMessages,
      ...(conversation.title === 'New Chat' && { title: input.substring(0, 30) })
    };
    
    setConversation(updatedConversation);
    setInput('');
    setIsLoading(true);

    const result = await getChatResponse(input);

    setIsLoading(false);

    if (result.error) {
      toast({
        variant: "destructive",
        title: "Error",
        description: result.error,
      });
      // Optionally remove the user message if the call fails
      setConversation(prev => ({
        ...prev,
        messages: prev.messages.slice(0, -1)
      }));
      return;
    }

    const aiMessage: Message = { id: `msg-${Date.now() + 1}`, role: 'assistant', content: result.response || '' };
    
    const finalConversation = {
        ...updatedConversation,
        messages: [...updatedConversation.messages, aiMessage]
    };
    
    setConversation(finalConversation);
    saveConversation(finalConversation);

    if (!chatId) {
      router.replace(`/chat/${finalConversation.id}`);
    }
  };

  return (
    <div className="flex h-[calc(100vh-2rem)] flex-col">
      <div className="flex-1 overflow-hidden">
        <ScrollArea className="h-full" ref={scrollAreaRef}>
          <div className="p-4">
            {conversation.messages.length === 0 ? (
              <div className="flex h-[calc(100vh-10rem)] items-center justify-center">
                <p className="text-muted-foreground">Start a conversation with Aura AI.</p>
              </div>
            ) : (
              conversation.messages.map((msg) => (
                <ChatMessage key={msg.id} message={msg} />
              ))
            )}
            {isLoading && (
              <ChatMessage message={{ id: 'loading', role: 'assistant', content: '' }} isLoading={true} />
            )}
          </div>
        </ScrollArea>
      </div>
      <div className="border-t p-4">
        <form onSubmit={handleSubmit} className="relative">
          <Input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask Aura AI anything..."
            className="pr-20"
            disabled={isLoading}
          />
          <div className="absolute inset-y-0 right-2 flex items-center gap-x-2">
            <kbd className="hidden h-5 select-none items-center gap-1 rounded border bg-muted px-1.5 font-mono text-[10px] font-medium text-muted-foreground opacity-100 md:flex">
              <CornerDownLeft className="size-3" />
            </kbd>
            <Button type="submit" size="icon" disabled={isLoading || !input.trim()}>
              <Send className="h-4 w-4" />
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
