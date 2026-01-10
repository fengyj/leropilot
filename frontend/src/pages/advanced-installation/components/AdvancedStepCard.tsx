import { ChevronDown, ChevronRight } from 'lucide-react';
import { Card, CardContent } from '../../../components/ui/card';
import { Button } from '../../../components/ui/button';
import { cn } from '../../../utils/cn';
import { CommandsEditor } from './CommandsEditor';

interface AdvancedStep {
  id: string;
  name: string;
  comment: string | null;
  commands: string[];
  status: 'pending' | 'running' | 'success' | 'error';
  logs: string[];
}

interface Props {
  step: AdvancedStep;
  index: number;
  isExpanded: boolean;
  onToggle: () => void;
  onCommandUpdate: (stepId: string, idx: number, value: string) => void;
  onAddCommand: (stepId: string) => void;
  onDeleteCommand: (stepId: string, idx: number) => void;
}

export function AdvancedStepCard({
  step,
  index,
  isExpanded,
  onToggle,
  onCommandUpdate,
  onAddCommand,
  onDeleteCommand,
}: Props) {
  return (
    <Card
      className={cn(
        'transition-all',
        step.status === 'running' && 'border-primary ring-1 ring-primary',
      )}
    >
      <div
        onClick={onToggle}
        onKeyDown={(e) => e.key === 'Enter' && onToggle()}
        role="button"
        tabIndex={0}
        className="border-border-default bg-surface-secondary/50 hover:bg-surface-secondary flex cursor-pointer items-center justify-between border-b p-4 transition-colors"
      >
        <div className="flex items-center gap-3">
          <span className="text-content-primary font-medium">
            {index + 1}. {step.name}
          </span>
        </div>

        <div className="flex items-center gap-2">
          <Button size="sm" variant="ghost" onClick={(e) => { e.stopPropagation(); onToggle(); }}>
            {isExpanded ? (
              <ChevronDown className="h-4 w-4" />
            ) : (
              <ChevronRight className="h-4 w-4" />
            )}
          </Button>
        </div>
      </div>

      {isExpanded && (
        <CardContent className="p-0">
          <div className="divide-border-default grid grid-cols-1 divide-y">
            {step.comment && (
              <div className="bg-surface-tertiary/50 border-border-default border-b p-4">
                <p className="text-content-secondary text-sm leading-relaxed">{step.comment}</p>
              </div>
            )}

            <CommandsEditor
              stepId={step.id}
              commands={step.commands}
              onChange={onCommandUpdate}
              onDelete={onDeleteCommand}
              onAdd={onAddCommand}
            />
          </div>
        </CardContent>
      )}
    </Card>
  );
}
