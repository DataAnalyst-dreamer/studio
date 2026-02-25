'use server';
/**
 * @fileOverview This file implements a Genkit flow for generating AI chat responses.
 *
 * - chatResponse - A function that handles generating an AI response to a user query.
 * - ChatResponseInput - The input type for the chatResponse function.
 * - ChatResponseOutput - The return type for the chatResponse function.
 */

import { ai } from '@/ai/genkit';
import { z } from 'genkit';

const ChatResponseInputSchema = z.object({
  query: z.string().describe('The user\'s text query for the AI.'),
});
export type ChatResponseInput = z.infer<typeof ChatResponseInputSchema>;

const ChatResponseOutputSchema = z.object({
  response: z.string().describe('The AI-generated text response.'),
});
export type ChatResponseOutput = z.infer<typeof ChatResponseOutputSchema>;

export async function chatResponse(input: ChatResponseInput): Promise<ChatResponseOutput> {
  return chatResponseFlow(input);
}

const prompt = ai.definePrompt({
  name: 'chatResponsePrompt',
  input: { schema: ChatResponseInputSchema },
  output: { schema: ChatResponseOutputSchema },
  prompt: `You are Aura AI, a helpful and engaging AI assistant.

User query: {{{query}}}

Respond to the user's query thoughtfully and comprehensively.`,
});

const chatResponseFlow = ai.defineFlow(
  {
    name: 'chatResponseFlow',
    inputSchema: ChatResponseInputSchema,
    outputSchema: ChatResponseOutputSchema,
  },
  async (input) => {
    const { output } = await prompt(input);
    return output!;
  }
);
