import { Trash2, Plus } from 'lucide-react';
import { Button } from '../../../components/ui/button';
import { CodeEditor } from '../../../components/code-editor';
import { useTranslation } from 'react-i18next';

interface CommandsEditorProps {
  stepId: string;
  commands: string[];
  onChange: (stepId: string, index: number, value: string) => void;
  onDelete: (stepId: string, index: number) => void;
  onAdd: (stepId: string) => void;
}

export function CommandsEditor({ stepId, commands, onChange, onDelete, onAdd }: CommandsEditorProps) {
  const { t } = useTranslation();

  return (
    <div className="space-y-3 p-4">
      <div className="mb-2 flex items-center justify-between">
        <span className="text-content-tertiary text-xs font-medium">{t('wizard.advanced.commands')}</span>
      </div>

      {commands.map((command, cmdIndex) => (
        <div key={`command-${stepId}-${cmdIndex}`} className="flex items-start gap-2">
          <div className="min-w-0 flex-1 space-y-1">
            <label htmlFor={`command-${stepId}-${cmdIndex}`} className="text-content-secondary text-xs font-medium">
              {t('wizard.advanced.commandLabel', { number: cmdIndex + 1 })}
            </label>
            <CodeEditor
              id={`command-${stepId}-${cmdIndex}`}
              name={`command_${stepId}_${cmdIndex}`}
              value={command}
              onChange={(value) => onChange(stepId, cmdIndex, value)}
              language="shell"
              height="auto"
              minHeight="40px"
              maxHeight="200px"
              placeholder={t('wizard.advanced.commandPlaceholder')}
            />
          </div>
          <button
            onClick={() => onDelete(stepId, cmdIndex)}
            className="mt-6 focus-visible:ring-primary rounded p-1 text-content-tertiary transition-colors hover:bg-surface-tertiary hover:text-error-icon focus-visible:ring-2 focus-visible:outline-none"
            title={t('wizard.advanced.deleteCommand')}
          >
            <Trash2 className="text-content-tertiary hover:text-error-icon h-4 w-4" />
          </button>
        </div>
      ))}

      <Button variant="ghost" size="sm" onClick={() => onAdd(stepId)} className="mt-2 w-full">
        <Plus className="mr-2 h-4 w-4" />
        {t('wizard.advanced.addCommand')}
      </Button>
    </div>
  );
}
