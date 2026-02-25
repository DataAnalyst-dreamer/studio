'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { LayoutDashboard, Building2 } from 'lucide-react';
import { cn } from '@/lib/utils';

const navItems = [
  { href: '/', label: '대시보드', icon: LayoutDashboard },
  { href: '/real-estate', label: '부동산 분석', icon: Building2 },
];

export default function BottomNav() {
  const pathname = usePathname();

  return (
    <nav className="fixed bottom-0 left-0 right-0 h-16 bg-card border-t border-border shadow-t-lg z-50">
      <div className="flex justify-around items-center h-full max-w-lg mx-auto">
        {navItems.map((item) => {
          const isActive = pathname === item.href;
          return (
            <Link key={item.href} href={item.href} className="flex-1 flex flex-col items-center justify-center text-sm gap-1">
                <item.icon
                  className={cn(
                    'h-6 w-6 transition-colors',
                    isActive ? 'text-primary' : 'text-muted-foreground'
                  )}
                />
                <span
                  className={cn(
                    'text-xs transition-colors',
                     isActive ? 'text-primary font-semibold' : 'text-muted-foreground'
                  )}
                >
                  {item.label}
                </span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
