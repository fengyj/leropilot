import { useEffect, useMemo } from 'react';
import { createPortal } from 'react-dom';
import { X } from 'lucide-react';
import { cn } from '../../utils/cn';

interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
  className?: string;
  contentClassName?: string;
}

// Global stack to track open modals and manage scroll lock
const activeModals: object[] = [];

export function Modal({ isOpen, onClose, title, children, className, contentClassName }: ModalProps) {
  const modalId = useMemo(() => ({}), []);

  // Handle escape key and body scroll lock
  useEffect(() => {
    if (!isOpen) return;

    activeModals.push(modalId);
    if (activeModals.length === 1) {
      document.body.style.overflow = 'hidden';
    }

    const handleEscape = (e: KeyboardEvent) => {
      // Only the last modal in the stack (the topmost one) handles the Escape key
      if (e.key === 'Escape' && activeModals[activeModals.length - 1] === modalId) {
        onClose();
      }
    };

    window.addEventListener('keydown', handleEscape);

    return () => {
      const index = activeModals.indexOf(modalId);
      if (index > -1) {
        activeModals.splice(index, 1);
      }
      if (activeModals.length === 0) {
        document.body.style.overflow = 'unset';
      }
      window.removeEventListener('keydown', handleEscape);
    };
  }, [isOpen, onClose, modalId]);

  if (!isOpen) return null;

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-surface-primary/50 backdrop-blur-sm p-4">
      <div 
        className={cn(
          "bg-surface-primary border-border-strong w-full max-w-lg rounded-lg border shadow-lg flex flex-col max-h-[90vh]",
          className
        )}
      >
        <div className="flex items-center justify-between border-b border-border-default p-4">
          <h2 className="text-lg font-semibold text-content-primary">{title}</h2>
          <button
            onClick={onClose}
            className="text-content-secondary hover:text-content-primary rounded-sm opacity-70 ring-offset-background transition-opacity hover:opacity-100 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
          >
            <X className="h-4 w-4" />
            <span className="sr-only">Close</span>
          </button>
        </div>
        <div className={cn("flex-1 overflow-y-auto p-4", contentClassName)}>
          {children}
        </div>
      </div>
    </div>,
    document.body
  );
}
