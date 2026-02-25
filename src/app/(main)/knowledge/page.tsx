'use client';
import { useState, useRef, useEffect } from 'react';
import { getKnowledgeAnswer } from '@/app/actions';
import type { Message } from '@/lib/types';
import ChatMessage from '@/components/chat-message';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Send, CornerDownLeft, BrainCircuit } from 'lucide-react';
import { useToast } from '@/hooks/use-toast';

export default function KnowledgePage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const { toast } = useToast();
  const scrollAreaRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollAreaRef.current) {
      scrollAreaRef.current.scrollTo({
        top: scrollAreaRef.current.scrollHeight,
        behavior: 'smooth',
      });
    }
  }, [messages]);
  
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    const userMessage: Message = { id: `msg-${Date.now()}`, role: 'user', content: input };
    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);

    const result = await getKnowledgeAnswer(input);
    setIsLoading(false);

    if (result.error) {
      toast({
        variant: 'destructive',
        title: 'Error',
        description: result.error,
      });
      return;
    }

    const aiMessage: Message = { id: `msg-${Date.now() + 1}`, role: 'assistant', content: result.response || '' };
    setMessages((prev) => [...prev, aiMessage]);
  };

  return (
    <div className="flex h-[calc(100vh-2rem)] flex-col">
       <div className="p-4 md:p-6 border-b">
        <h1 className="text-2xl font-bold flex items-center gap-2"><BrainCircuit /> Knowledge Base Query</h1>
        <p className="text-muted-foreground">
          Ask questions to get information from the integrated knowledge base.
        </p>
      </div>
      <div className="flex-1 overflow-hidden">
        <ScrollArea className="h-full" ref={scrollAreaRef}>
          <div className="p-4">
            {messages.length === 0 ? (
              <div className="flex h-[calc(100vh-18rem)] items-center justify-center">
                <p className="text-muted-foreground">Ask about Genkit, Next.js, Firebase, and more.</p>
              </div>
            ) : (
              messages.map((msg) => <ChatMessage key={msg.id} message={msg} />)
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
            placeholder="e.g., What is Genkit?"
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
