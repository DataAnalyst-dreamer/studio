'use client';

import { useState } from 'react';
import { summarizeContentAction } from '@/app/actions';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Textarea } from '@/components/ui/textarea';
import { useToast } from '@/hooks/use-toast';
import { Loader2 } from 'lucide-react';

export default function SummarizePage() {
  const [content, setContent] = useState('');
  const [summary, setSummary] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const { toast } = useToast();

  const handleSummarize = async () => {
    if (!content.trim()) {
      toast({
        variant: "destructive",
        title: "Input required",
        description: "Please enter some text to summarize.",
      });
      return;
    }
    setIsLoading(true);
    setSummary('');
    const result = await summarizeContentAction(content);
    setIsLoading(false);

    if (result.error) {
      toast({
        variant: "destructive",
        title: "Error",
        description: result.error,
      });
    } else {
      setSummary(result.summary || '');
    }
  };

  return (
    <div className="p-4 md:p-6 h-full flex flex-col gap-6">
      <div className="space-y-1">
        <h1 className="text-2xl font-bold">Content Summarization</h1>
        <p className="text-muted-foreground">
          Paste your text below and let Aura AI provide a concise summary.
        </p>
      </div>
      <div className="flex-1 grid gap-6 md:grid-cols-2">
        <div className="flex flex-col gap-4">
          <Textarea
            value={content}
            onChange={(e) => setContent(e.target.value)}
            placeholder="Paste your article, notes, or any long text here..."
            className="h-full min-h-[300px] flex-1"
            disabled={isLoading}
          />
          <Button onClick={handleSummarize} disabled={isLoading} className="w-full">
            {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Summarize
          </Button>
        </div>
        <Card className="flex flex-col">
          <CardHeader>
            <CardTitle>Summary</CardTitle>
            <CardDescription>The key points from your text.</CardDescription>
          </CardHeader>
          <CardContent className="flex-1">
            {isLoading ? (
              <div className="flex h-full items-center justify-center">
                 <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
              </div>
            ) : summary ? (
              <p className="whitespace-pre-wrap">{summary}</p>
            ) : (
              <div className="flex h-full items-center justify-center">
                <p className="text-muted-foreground">Your summary will appear here.</p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
