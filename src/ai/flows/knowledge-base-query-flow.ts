'use server';
/**
 * @fileOverview A Genkit flow for querying an integrated knowledge base.
 *
 * - knowledgeBaseQuery - A function that handles queries to a knowledge base.
 * - KnowledgeBaseQueryInput - The input type for the knowledgeBaseQuery function.
 * - KnowledgeBaseQueryOutput - The return type for the knowledgeBaseQuery function.
 */

import {ai} from '@/ai/genkit';
import {z} from 'genkit';

// Input Schema
const KnowledgeBaseQueryInputSchema = z.object({
  query: z.string().describe('The user\'s question about a specific topic.'),
});
export type KnowledgeBaseQueryInput = z.infer<typeof KnowledgeBaseQueryInputSchema>;

// Output Schema
const KnowledgeBaseQueryOutputSchema = z.object({
  answer: z.string().describe('The informed answer to the user\'s question based on the knowledge base context.'),
});
export type KnowledgeBaseQueryOutput = z.infer<typeof KnowledgeBaseQueryOutputSchema>;

// --- Tool Definition ---
// This tool simulates searching a knowledge base. In a real application,
// this would interact with a database, vector store, or external API.
const searchKnowledgeBase = ai.defineTool(
  {
    name: 'searchKnowledgeBase',
    description: 'Searches the integrated knowledge base for information relevant to the user\'s query.',
    inputSchema: z.object({
      topic: z.string().describe('The topic or keywords to search for in the knowledge base.'),
    }),
    outputSchema: z.string().describe('Relevant information retrieved from the knowledge base.'),
  },
  async (input) => {
    // Simulate knowledge base content based on common topics
    const simulatedKnowledge: Record<string, string> = {
      'genkit': 'Genkit is an open-source framework for building AI-powered applications. It provides tools for orchestrating AI models, defining flows, and integrating with various AI providers. Key features include flow definition, prompt templating, tool calling, and observability.',
      'next.js': 'Next.js is a React framework for building full-stack web applications. It enables React features like server-side rendering and static site generation. It also supports API routes for backend functionality, making it suitable for building robust web services.',
      'firebase': 'Firebase is a platform developed by Google for creating mobile and web applications. It offers a variety of services including authentication, real-time database (Firestore), cloud storage, cloud functions, and hosting. It simplifies backend development for developers.',
      'aura ai': 'Aura AI is an AI-powered application featuring an interactive chat interface, knowledge base query tool, content summarization, conversation history, and personalized preferences. It leverages Next.js for the frontend and Genkit for AI functionalities.',
      'llm': 'LLM stands for Large Language Model. These are advanced AI models trained on vast amounts of text data, capable of understanding, generating, and translating human-like text. They are foundational for many AI applications, including chatbots and content generation.',
      'default': 'The knowledge base contains information about various software frameworks, AI technologies, and the Aura AI application itself. Please specify a more precise topic for better results.'
    };

    const topicLower = input.topic.toLowerCase();
    for (const key in simulatedKnowledge) {
      if (topicLower.includes(key)) {
        return simulatedKnowledge[key];
      }
    }
    return simulatedKnowledge['default'];
  }
);

// --- Prompt Definition ---
const knowledgeBaseQueryPrompt = ai.definePrompt({
  name: 'knowledgeBaseQueryPrompt',
  input: { schema: KnowledgeBaseQueryInputSchema },
  output: { schema: KnowledgeBaseQueryOutputSchema },
  tools: [searchKnowledgeBase],
  system: `You are an AI assistant named Aura AI, part of an advanced AI application. Your primary function is to answer user questions accurately and concisely by searching an integrated knowledge base.

  When a user asks a question, first determine the core topic or keywords. Then, you MUST use the \`searchKnowledgeBase\` tool to retrieve relevant information.
  After retrieving information, synthesize it into a clear, direct answer to the user's original question.
  If the tool does not provide sufficient information to answer the question, politely state that you cannot provide a definitive answer based on the available knowledge and suggest rephrasing the question or asking about a different topic.
  Do not make up information. Base your answers strictly on the knowledge provided by the tool.`,
  prompt: `User's question: {{{query}}}`,
});

// --- Flow Definition ---
const knowledgeBaseQueryFlow = ai.defineFlow(
  {
    name: 'knowledgeBaseQueryFlow',
    inputSchema: KnowledgeBaseQueryInputSchema,
    outputSchema: KnowledgeBaseQueryOutputSchema,
  },
  async (input) => {
    const { output } = await knowledgeBaseQueryPrompt(input);
    return output!;
  }
);

export async function knowledgeBaseQuery(input: KnowledgeBaseQueryInput): Promise<KnowledgeBaseQueryOutput> {
  return knowledgeBaseQueryFlow(input);
}
