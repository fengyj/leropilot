import { useTranslation } from 'react-i18next';
import { 
  XCircle, 
  AlertTriangle, 
  CheckCircle2, 
  Info 
} from 'lucide-react';
import { Modal } from './modal';
import { Button } from './button';
import { cn } from '../../utils/cn';

export type MessageBoxType = 'info' | 'warning' | 'error' | 'success';
export type MessageBoxButtonType = 'ok' | 'ok-cancel' | 'yes-no';

interface MessageBoxProps {
  isOpen: boolean;
  onClose: () => void;
  type?: MessageBoxType;
  title?: string;
  message: string;
  description?: string;
  buttonType?: MessageBoxButtonType;
  onConfirm?: () => void;
  onCancel?: () => void;
  confirmText?: string;
  cancelText?: string;
  className?: string;
}

export function MessageBox({
  isOpen,
  onClose,
  type = 'info',
  title,
  message,
  description,
  buttonType = 'ok',
  onConfirm,
  onCancel,
  confirmText,
  cancelText,
  className,
}: MessageBoxProps) {
  const { t } = useTranslation();

  const getIcon = () => {
    switch (type) {
      case 'success':
        return <CheckCircle2 className="h-10 w-10 text-status-success" />;
      case 'warning':
        return <AlertTriangle className="h-10 w-10 text-status-warning" />;
      case 'error':
        return <XCircle className="h-10 w-10 text-status-danger" />;
      case 'info':
      default:
        return <Info className="h-10 w-10 text-primary" />;
    }
  };

  const getDefaultTitle = () => {
    switch (type) {
      case 'success':
        return t('common.success') || 'Success';
      case 'warning':
        return t('common.warning') || 'Warning';
      case 'error':
        return t('common.error') || 'Error';
      case 'info':
      default:
        return t('common.info') || 'Information';
    }
  };

  const handleConfirm = () => {
    if (onConfirm) {
      onConfirm();
    } else {
      onClose();
    }
  };

  const handleCancel = () => {
    if (onCancel) {
      onCancel();
    } else {
      onClose();
    }
  };

  const renderButtons = () => {
    const defaultConfirmText = buttonType === 'yes-no' ? t('common.yes') : t('common.confirm');
    const defaultCancelText = buttonType === 'yes-no' ? t('common.no') : t('common.cancel');

    return (
      <div className="flex justify-end gap-3 mt-6">
        {buttonType !== 'ok' && (
          <Button variant="secondary" onClick={handleCancel}>
            {cancelText || defaultCancelText}
          </Button>
        )}
        <Button
          variant={type === 'error' ? 'danger' : type === 'warning' ? 'danger' : 'primary'}
          onClick={handleConfirm}
        >
          {confirmText || defaultConfirmText}
        </Button>
      </div>
    );
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={title || getDefaultTitle()}
      className={cn("max-w-md", className)}
    >
      <div className="flex items-start gap-5 py-2">
        <div className="shrink-0">
          {getIcon()}
        </div>
        <div className="flex-1 space-y-2">
          <h3 className="text-lg font-semibold text-content-primary leading-tight">
            {message}
          </h3>
          {description && (
            <p className="text-sm text-content-secondary leading-relaxed">
              {description}
            </p>
          )}
        </div>
      </div>
      {renderButtons()}
    </Modal>
  );
}
