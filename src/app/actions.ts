'use server';

import { chatResponse } from '@/ai/flows/chat-response-flow';
import { summarizeContent } from '@/ai/flows/summarize-content-flow';
import { knowledgeBaseQuery } from '@/ai/flows/knowledge-base-query-flow';
import type { Message } from '@/lib/types';
import { z } from 'zod';

const getZodSchema = (schemaType: 'chat' | 'summarize' | 'knowledge') => {
  switch (schemaType) {
    case 'chat':
      return z.object({
        query: z.string().min(1),
        history: z.array(z.object({
          role: z.enum(['user', 'assistant']),
          content: z.string(),
        }))
      });
    case 'summarize':
      return z.object({
        content: z.string().min(1),
      });
    case 'knowledge':
       return z.object({
        query: z.string().min(1),
        history: z.array(z.object({
          role: z.enum(['user', 'assistant']),
          content: z.string(),
        }))
      });
  }
}

export async function getChatResponse(query: string) {
  const validatedQuery = getZodSchema('chat').pick({query: true}).safeParse({ query });
  if (!validatedQuery.success) {
    return { error: 'Invalid query' };
  }

  try {
    // Note: The history is not currently used by the prompt but is included for future extension.
    const result = await chatResponse({ query: validatedQuery.data.query });
    return { response: result.response };
  } catch (e) {
    console.error(e);
    return { error: 'Failed to get response from AI.' };
  }
}

export async function summarizeContentAction(content: string) {
  const validatedContent = getZodSchema('summarize').safeParse({ content });

  if (!validatedContent.success) {
    return { error: 'Invalid content' };
  }

  try {
    const result = await summarizeContent({ textContent: validatedContent.data.content });
    return { summary: result.summary };
  } catch (e) {
    console.error(e);
    return { error: 'Failed to summarize content.' };
  }
}


export async function getKnowledgeAnswer(query: string) {
    const validatedQuery = getZodSchema('knowledge').pick({query: true}).safeParse({ query });

  if (!validatedQuery.success) {
    return { error: 'Invalid query' };
  }
  
  try {
    const result = await knowledgeBaseQuery({ query: validatedQuery.data.query });
    return { response: result.answer };
  } catch (e) {
    console.error(e);
    return { error: 'Failed to get answer from knowledge base.' };
  }
}
