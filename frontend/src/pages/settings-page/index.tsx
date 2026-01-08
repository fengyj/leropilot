import { useTranslation } from 'react-i18next';
import { Save, RotateCcw, AlertCircle, CheckCircle2 } from 'lucide-react';
import { Button } from '../../components/ui/button';
import { PageContainer } from '../../components/ui/page-container';
import { cn } from '../../utils/cn';
import { useSettings } from './hooks/use-settings';
import { AppearanceSection } from './sections/AppearanceSection';
import { LanguageSection } from './sections/LanguageSection';
import { PathsSection } from './sections/PathsSection';
import { GitSection } from './sections/GitSection';

import { RepositoriesSection } from './sections/RepositoriesSection';
import { PyPISection } from './sections/PyPISection';
import { HuggingFaceSection } from './sections/HuggingFaceSection';
import { AdvancedSection } from './sections/AdvancedSection';

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
  } = useSettings();

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <div className="text-content-tertiary">Loading settings...</div>
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

  const hasAnyChanges =
    savedConfig && JSON.stringify(config) !== JSON.stringify(savedConfig);

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
          {message.type === 'success' ? (
            <CheckCircle2 className="text-success-icon h-5 w-5" />
          ) : (
            <AlertCircle className="text-error-icon h-5 w-5" />
          )}
          <span>{message.text}</span>
        </div>
      )}

      {/* Settings Sections */}
      <AppearanceSection
        config={config}
        setConfig={setConfig}
        hasUnsavedChanges={hasUnsavedChanges('theme')}
      />

      <LanguageSection
        config={config}
        setConfig={setConfig}
        hasUnsavedChanges={hasUnsavedChanges('language')}
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
        <Button variant="secondary" onClick={resetConfig} disabled={saving}>
          <RotateCcw className="mr-2 h-4 w-4" />
          {t('settings.buttons.reset')}
        </Button>
        <Button onClick={saveConfig} disabled={saving || !hasAnyChanges}>
          {saving ? (
            <>
              <div className="mr-2 h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
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
    </PageContainer>
  );
}
