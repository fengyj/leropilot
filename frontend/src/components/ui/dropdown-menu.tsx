import { useCallback, useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { cn } from '../../utils/cn';

interface DropdownMenuProps {
  trigger: React.ReactNode;
  items: Array<{
    id: string;
    label: string;
    onClick: () => void;
    variant?: 'default' | 'danger';
    icon?: React.ReactNode;
  }>;
  align?: 'left' | 'right';
}

export function DropdownMenu({ trigger, items, align = 'right' }: DropdownMenuProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [menuStyle, setMenuStyle] = useState<{
    top: number;
    left?: number;
    right?: number;
  }>({
    top: 0,
  });
  const containerRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);

  // Update menu position
  const updateMenuPosition = useCallback(() => {
    if (triggerRef.current) {
      const rect = triggerRef.current.getBoundingClientRect();
      setMenuStyle({
        top: rect.bottom + window.scrollY + 8,
        [align === 'left' ? 'left' : 'right']:
          align === 'left' ? rect.left : window.innerWidth - rect.right,
      });
    }
  }, [align]);

  useEffect(() => {
    if (isOpen) {
      updateMenuPosition();
      window.addEventListener('scroll', updateMenuPosition);
      return () => window.removeEventListener('scroll', updateMenuPosition);
    }
  }, [isOpen, align, updateMenuPosition]);

  // Close menu when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      const target = event.target as Node;
      if (
        containerRef.current &&
        !containerRef.current.contains(target) &&
        triggerRef.current &&
        !triggerRef.current.contains(target)
      ) {
        setIsOpen(false);
      }
    }

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [isOpen]);

  // Close menu when pressing Escape
  useEffect(() => {
    function handleEscape(event: KeyboardEvent) {
      if (event.key === 'Escape' && isOpen) {
        setIsOpen(false);
      }
    }

    if (isOpen) {
      document.addEventListener('keydown', handleEscape);
      return () => document.removeEventListener('keydown', handleEscape);
    }
  }, [isOpen]);

  return (
    <div className="relative" ref={containerRef}>
      <button
        ref={triggerRef}
        onClick={() => setIsOpen(!isOpen)}
        className={cn(
          'text-content-secondary hover:text-content-primary hover:bg-surface-tertiary inline-flex h-9 items-center gap-2 rounded-lg px-3 py-2 transition-all focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:outline-none disabled:pointer-events-none disabled:opacity-50',
          isOpen && 'bg-surface-tertiary text-content-primary',
        )}
      >
        {trigger}
      </button>

      {isOpen &&
        createPortal(
          <div
            ref={containerRef}
            className="bg-surface-primary border-border-default animate-in fade-in zoom-in-95 fixed z-50 min-w-max rounded-lg border shadow-lg"
            style={{
              top: `${menuStyle.top}px`,
              left: menuStyle.left !== undefined ? `${menuStyle.left}px` : 'auto',
              right: menuStyle.right !== undefined ? `${menuStyle.right}px` : 'auto',
            }}
          >
            <div className="py-1">
              {items.map((item, index) => (
                <button
                  key={item.id}
                  onClick={() => {
                    item.onClick();
                    setIsOpen(false);
                  }}
                  className={cn(
                    'text-content-primary hover:bg-surface-tertiary flex w-full items-center gap-3 px-4 py-2.5 text-left text-sm transition-colors focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:outline-none focus-visible:ring-inset',
                    item.variant === 'danger' &&
                      'text-red-600 hover:bg-red-50/10 hover:text-red-700',
                    index > 0 && 'border-border-default border-t',
                  )}
                >
                  {item.icon && <span className="flex-shrink-0">{item.icon}</span>}
                  <span>{item.label}</span>
                </button>
              ))}
            </div>
          </div>,
          document.body,
        )}
    </div>
  );
}
