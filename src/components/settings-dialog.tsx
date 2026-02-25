'use client';

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useSettings } from '@/lib/hooks';
import type { Settings } from '@/lib/types';

interface SettingsDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function SettingsDialog({ open, onOpenChange }: SettingsDialogProps) {
  const { settings, setSettings } = useSettings();

  const handleToneChange = (value: Settings['aiTone']) => {
    setSettings((prev) => ({ ...prev, aiTone: value }));
  };

  const handleVerbosityChange = (value: Settings['responseVerbosity']) => {
    setSettings((prev) => ({ ...prev, responseVerbosity: value }));
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[425px]">
        <DialogHeader>
          <DialogTitle>Personalized Preferences</DialogTitle>
          <DialogDescription>
            Adjust the AI's behavior to your liking. These settings are saved locally.
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 py-4">
          <div className="grid grid-cols-4 items-center gap-4">
            <Label htmlFor="ai-tone" className="text-right">
              AI Tone
            </Label>
            <Select
              defaultValue={settings.aiTone}
              onValueChange={handleToneChange}
            >
              <SelectTrigger id="ai-tone" className="col-span-3">
                <SelectValue placeholder="Select a tone" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="formal">Formal</SelectItem>
                <SelectItem value="casual">Casual</SelectItem>
                <SelectItem value="witty">Witty</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="grid grid-cols-4 items-center gap-4">
            <Label htmlFor="verbosity" className="text-right">
              Verbosity
            </Label>
            <Select
              defaultValue={settings.responseVerbosity}
              onValueChange={handleVerbosityChange}
            >
              <SelectTrigger id="verbosity" className="col-span-3">
                <SelectValue placeholder="Select verbosity" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="concise">Concise</SelectItem>
                <SelectItem value="balanced">Balanced</SelectItem>
                <SelectItem value="detailed">Detailed</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
