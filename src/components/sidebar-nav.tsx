'use client';

import { useState } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import {
  MessageSquare,
  BookText,
  BrainCircuit,
  Settings,
  Plus,
  Trash2,
  MoreHorizontal,
} from 'lucide-react';
import {
  Sidebar,
  SidebarContent,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuItem,
  SidebarMenuButton,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupLabel,
  SidebarMenuAction,
} from '@/components/ui/sidebar';
import { Logo } from '@/components/icons';
import { useChatHistory } from '@/lib/hooks';
import { SettingsDialog } from '@/components/settings-dialog';
import { Button } from './ui/button';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from './ui/dropdown-menu';

const navItems = [
  { href: '/chat', icon: MessageSquare, label: 'Interactive Chat' },
  { href: '/knowledge', icon: BrainCircuit, label: 'Knowledge Base' },
  { href: '/summarize', icon: BookText, label: 'Content Summarization' },
];

export function SidebarNav() {
  const pathname = usePathname();
  const router = useRouter();
  const { conversations, createNewChat, deleteConversation } = useChatHistory();
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);

  const handleDelete = (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    deleteConversation(id);
    if (pathname.includes(id)) {
      router.push('/chat');
    }
  };

  return (
    <>
      <Sidebar>
        <SidebarHeader>
          <div className="flex items-center gap-2">
            <Logo className="size-6 text-primary" />
            <span className="text-lg font-semibold">Aura AI</span>
          </div>
        </SidebarHeader>
        <SidebarContent>
          <SidebarGroup>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuButton
                  onClick={createNewChat}
                  variant="outline"
                  size="sm"
                  className="w-full justify-center"
                >
                  <Plus className="size-4" />
                  New Chat
                </SidebarMenuButton>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarGroup>

          <SidebarGroup>
            <SidebarGroupLabel>Tools</SidebarGroupLabel>
            <SidebarMenu>
              {navItems.map((item) => (
                <SidebarMenuItem key={item.href}>
                  <SidebarMenuButton
                    onClick={() => router.push(item.href)}
                    isActive={pathname.startsWith(item.href)}
                    tooltip={{ children: item.label, side: 'right' }}
                  >
                    <item.icon />
                    <span>{item.label}</span>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroup>

          <SidebarGroup className="flex-1 overflow-auto">
            <SidebarGroupLabel>Conversation History</SidebarGroupLabel>
            <SidebarMenu>
              {conversations.map((conv) => (
                <SidebarMenuItem key={conv.id}>
                  <SidebarMenuButton
                    onClick={() => router.push(`/chat/${conv.id}`)}
                    isActive={pathname.endsWith(conv.id)}
                    tooltip={{ children: conv.title, side: 'right' }}
                  >
                    <MessageSquare />
                    <span>{conv.title}</span>
                  </SidebarMenuButton>
                   <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                         <SidebarMenuAction showOnHover>
                            <MoreHorizontal />
                         </SidebarMenuAction>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent>
                         <DropdownMenuItem onClick={(e) => handleDelete(e, conv.id)} className="text-destructive">
                            <Trash2 className="mr-2 h-4 w-4" />
                            Delete
                         </DropdownMenuItem>
                      </DropdownMenuContent>
                   </DropdownMenu>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroup>
        </SidebarContent>

        <SidebarFooter>
          <SidebarMenu>
            <SidebarMenuItem>
              <SidebarMenuButton
                onClick={() => setIsSettingsOpen(true)}
                tooltip={{ children: 'Settings', side: 'right' }}
              >
                <Settings />
                <span>Settings</span>
              </SidebarMenuButton>
            </SidebarMenuItem>
          </SidebarMenu>
        </SidebarFooter>
      </Sidebar>
      <SettingsDialog open={isSettingsOpen} onOpenChange={setIsSettingsOpen} />
    </>
  );
}
