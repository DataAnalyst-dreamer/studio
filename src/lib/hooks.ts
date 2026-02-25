"use client";

import { useState, useEffect, useCallback } from 'react';
import type { Settings, Conversation } from './types';
import { useRouter } from 'next/navigation';

// Generic hook to sync state with localStorage
function useLocalStorage<T>(key: string, initialValue: T): [T, (value: T | ((val: T) => T)) => void] {
  const [storedValue, setStoredValue] = useState<T>(() => {
    if (typeof window === 'undefined') {
      return initialValue;
    }
    try {
      const item = window.localStorage.getItem(key);
      return item ? JSON.parse(item) : initialValue;
    } catch (error) {
      console.error(error);
      return initialValue;
    }
  });

  const setValue = (value: T | ((val: T) => T)) => {
    try {
      const valueToStore = value instanceof Function ? value(storedValue) : value;
      setStoredValue(valueToStore);
      if (typeof window !== 'undefined') {
        window.localStorage.setItem(key, JSON.stringify(valueToStore));
      }
    } catch (error) {
      console.error(error);
    }
  };

  useEffect(() => {
    const handleStorageChange = (e: StorageEvent) => {
      if (e.key === key) {
        try {
          setStoredValue(e.newValue ? JSON.parse(e.newValue) : initialValue);
        } catch (error) {
          console.error(error);
        }
      }
    };
    window.addEventListener('storage', handleStorageChange);
    return () => window.removeEventListener('storage', handleStorageChange);
  }, [key, initialValue]);

  return [storedValue, setValue];
}

// Hook for managing user settings
export function useSettings() {
  const [settings, setSettings] = useLocalStorage<Settings>('aura-ai-settings', {
    aiTone: 'formal',
    responseVerbosity: 'balanced',
  });

  return { settings, setSettings };
}

// Hook for managing chat history
export function useChatHistory() {
  const [conversations, setConversations] = useLocalStorage<Conversation[]>('aura-ai-conversations', []);
  const router = useRouter();

  const createNewChat = useCallback(() => {
    router.push('/chat');
  }, [router]);

  const getConversation = useCallback((id: string | undefined) => {
    if (!id) return undefined;
    return conversations.find(c => c.id === id);
  }, [conversations]);

  const saveConversation = useCallback((conversation: Conversation) => {
    setConversations(prev => {
      const index = prev.findIndex(c => c.id === conversation.id);
      if (index !== -1) {
        const newConversations = [...prev];
        newConversations[index] = conversation;
        return newConversations.sort((a, b) => b.createdAt - a.createdAt);
      }
      return [conversation, ...prev].sort((a, b) => b.createdAt - a.createdAt);
    });
  }, [setConversations]);

  const deleteConversation = useCallback((id: string) => {
    setConversations(prev => prev.filter(c => c.id !== id));
  }, [setConversations]);

  return {
    conversations,
    createNewChat,
    getConversation,
    saveConversation,
    deleteConversation,
  };
}
