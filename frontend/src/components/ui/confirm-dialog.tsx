import { useTranslation } from 'react-i18next';
import { Button } from './button';
import { Modal } from './modal';

interface ConfirmDialogProps {
  isOpen: boolean;
  title: string;
  message: string;
  confirmText?: string;
  cancelText?: string;
  onConfirm: () => void;
  onCancel: () => void;
  variant?: 'danger' | 'default';
}

export function ConfirmDialog({
  isOpen,
  title,
  message,
  confirmText,
  cancelText,
  onConfirm,
  onCancel,
  variant = 'default',
}: ConfirmDialogProps) {
  const { t } = useTranslation();

  return (
    <Modal
      isOpen={isOpen}
      onClose={onCancel}
      title={title}
      className="max-w-md max-h-min"
    >
      <div className="flex flex-col gap-6">
        <p className="text-content-secondary text-sm">{message}</p>

        <div className="flex justify-end gap-3">
          <Button variant="secondary" onClick={onCancel}>
            {cancelText || t('common.cancel')}
          </Button>
          <Button
            variant={variant === 'danger' ? 'danger' : 'primary'}
            onClick={onConfirm}
          >
            {confirmText || t('common.confirm')}
          </Button>
        </div>
      </div>
    </Modal>
  );
}
