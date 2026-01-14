import { useTranslation } from 'react-i18next';
import { useState } from 'react';
import { Save, RotateCcw } from 'lucide-react';
import { StatusBadge } from '../../components/ui/status-badge';
import { MessageBox } from '../../components/ui/message-box';
import { Button } from '../../components/ui/button';
import { PageContainer } from '../../components/ui/page-container';
import { cn } from '../../utils/cn';
import { useSettings } from './hooks/use-settings';
import { AppearanceSection } from './components/AppearanceSection';
import { LanguageSection } from './components/LanguageSection';
import { PathsSection } from './components/PathsSection';
import { GitSection } from './components/GitSection';

import { RepositoriesSection } from './components/RepositoriesSection';
import { PyPISection } from './components/PyPISection';
import { HuggingFaceSection } from './components/HuggingFaceSection';
import { AdvancedSection } from './components/AdvancedSection';
import { LoadingOverlay } from '../../components/ui/loading-overlay';

export function SettingsPage() {
  const { t } = useTranslation();
  const {
    config,
    savedConfig,
    setConfig,
    hasEnvironments,
    loading,
    saving,
    error,
    message,
    setMessage,
    saveConfig,
    resetConfig,
    hasUnsavedChanges,
    sectionHasUnsaved,
  } = useSettings();
  const [showResetDialog, setShowResetDialog] = useState(false);

  if (loading) {
    return (
      <div className="relative flex h-64 items-center justify-center">
        <LoadingOverlay message="Loading settings..." size="md" fancy className="rounded-lg" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-64 flex-col items-center justify-center gap-4">
        <div className="text-error-icon">Error loading settings: {error}</div>
        <Button onClick={() => window.location.reload()}>Retry</Button>
      </div>
    );
  }

  if (!config) {
    return (
      <div className="flex h-64 items-center justify-center">
        <div className="text-content-tertiary">No configuration loaded.</div>
      </div>
    );
  }

  // Prefer the hook-provided deep equality check for any changes
  const hasAnyChanges = hasUnsavedChanges();

  return (
    <PageContainer>
      {/* Header */}
      <div>
        <h1 className="text-content-primary text-2xl font-bold tracking-tight">
          {t('settings.title')}
        </h1>
        <p className="text-content-secondary">{t('settings.subtitle')}</p>
      </div>

      {/* Message */}
      {message && (
        <div
          className={cn(
            'flex items-center gap-3 rounded-lg border p-4',
            message.type === 'success'
              ? 'border-success-border bg-success-surface text-success-content'
              : 'border-error-border bg-error-surface text-error-content',
          )}
        >
          <StatusBadge variant={message.type === 'success' ? 'success' : 'error'}>
            {message.text}
          </StatusBadge>
        </div>
      )}

      {/* Settings Sections */}
      <AppearanceSection
        config={config}
        setConfig={setConfig}
        hasUnsavedChanges={sectionHasUnsaved('theme')}
      />

      <LanguageSection
        config={config}
        setConfig={setConfig}
        hasUnsavedChanges={sectionHasUnsaved('language')}
      />

      <PathsSection
        config={config}
        setConfig={setConfig}
        hasEnvironments={hasEnvironments}
      />

      <GitSection
        config={config}
        setConfig={setConfig}
        loadConfig={async () => {
          // Reload settings after git download
          window.location.reload();
        }}
        setMessage={setMessage}
      />

      <RepositoriesSection
        config={config}
        setConfig={setConfig}
        savedConfig={savedConfig}
      />

      <PyPISection config={config} setConfig={setConfig} />

      <HuggingFaceSection config={config} setConfig={setConfig} />

      <AdvancedSection config={config} setConfig={setConfig} />

      {/* Action Buttons */}
      <div className="border-border-default flex items-center justify-between border-t pt-6">
        <div className="flex items-center gap-3">
          <Button variant="secondary" onClick={() => setShowResetDialog(true)} disabled={saving}>
            <RotateCcw className="mr-2 h-4 w-4" />
            {t('settings.buttons.reset')}
          </Button>
        </div>

        <Button onClick={saveConfig} disabled={saving || !hasAnyChanges}>
          {saving ? (
            <>
              <div className="mr-2 h-4 w-4 animate-spin rounded-full border-2 border-primary-content border-t-transparent" />
              {t('settings.saving')}
            </>
          ) : (
            <>
              <Save className="mr-2 h-4 w-4" />
              {t('settings.buttons.save')}
            </>
          )}
        </Button>
      </div>

      <MessageBox
        isOpen={showResetDialog}
        onClose={() => setShowResetDialog(false)}
        type="warning"
        title={t('settings.buttons.reset')}
        message={t('settings.messages.resetConfirm')}
        buttonType="ok-cancel"
        onConfirm={async () => {
          setShowResetDialog(false);
          await resetConfig();
        }}
        onCancel={() => setShowResetDialog(false)}
      />
    </PageContainer>
  );
}