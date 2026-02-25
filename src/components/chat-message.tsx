'use client';
import { cn } from '@/lib/utils';
import type { Message } from '@/lib/types';
import { Avatar, AvatarFallback, AvatarImage } from './ui/avatar';
import { placeholderImages } from '@/lib/placeholder-images';
import { Bot, User, Loader2 } from 'lucide-react';
import { memo } from 'react';

interface ChatMessageProps {
  message: Message;
  isLoading?: boolean;
}

const ChatMessage = memo(({ message, isLoading = false }: ChatMessageProps) => {
  const isUser = message.role === 'user';
  const aiAvatar = placeholderImages.find(img => img.id === 'ai-avatar');

  return (
    <div
      className={cn(
        'flex items-start gap-4 p-4',
        isUser ? 'justify-end' : ''
      )}
    >
      {!isUser && (
        <Avatar className="h-8 w-8">
          {aiAvatar ? <AvatarImage src={aiAvatar.imageUrl} alt={aiAvatar.description} /> : null}
          <AvatarFallback>
            <Bot />
          </AvatarFallback>
        </Avatar>
      )}
      <div
        className={cn(
          'max-w-[75%] rounded-lg p-3 text-sm animate-in fade-in',
          isUser
            ? 'bg-primary text-primary-foreground'
            : 'bg-muted'
        )}
      >
        {isLoading ? (
          <div className="flex items-center gap-2">
            <Loader2 className="h-4 w-4 animate-spin" />
            <span>Thinking...</span>
          </div>
        ) : (
          <p className="whitespace-pre-wrap">{message.content}</p>
        )}
      </div>
      {isUser && (
        <Avatar className="h-8 w-8">
          <AvatarFallback>
            <User />
          </AvatarFallback>
        </Avatar>
      )}
    </div>
  );
});
ChatMessage.displayName = 'ChatMessage';

export default ChatMessage;
