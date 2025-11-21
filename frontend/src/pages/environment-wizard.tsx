import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ChevronRight, Check, Info, AlertTriangle } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardFooter } from '../components/ui/card';
import { useWizardStore } from '../stores/environment-wizard-store';
import { cn } from '../utils/cn';

export function EnvironmentWizard() {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { step, setStep, config, updateConfig } = useWizardStore();
  const [isAdvancedOpen, setIsAdvancedOpen] = useState(false);

  const STEPS = [
    { id: 1, title: t('wizard.steps.source') },
    { id: 2, title: t('wizard.steps.hardware') },
    { id: 3, title: t('wizard.steps.robots') },
    { id: 4, title: t('wizard.steps.review') },
  ];

  const handleNext = () => {
    if (step < 4) setStep(step + 1);
    else navigate('/environments');
  };

  const handleBack = () => {
    if (step > 1) setStep(step - 1);
    else navigate('/environments');
  };

  return (
    <div className="mx-auto max-w-3xl space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-content-primary">{t('wizard.title')}</h1>
        <p className="text-content-secondary">{t('wizard.subtitle')}</p>
      </div>

      {/* Progress Steps */}
      <div className="relative flex justify-between">
        <div className="absolute top-1/2 h-0.5 w-full -translate-y-1/2 bg-border-default" />
        {STEPS.map((s) => (
          <div
            key={s.id}
            className="relative z-10 flex flex-col items-center gap-2 bg-surface-primary px-2"
          >
            <div
              className={cn(
                'flex h-8 w-8 items-center justify-center rounded-full border-2 text-sm font-bold transition-colors',
                step >= s.id
                  ? 'border-blue-600 bg-blue-600 text-white'
                  : 'border-border-default bg-surface-secondary text-content-tertiary',
              )}
            >
              {step > s.id ? <Check className="h-4 w-4" /> : s.id}
            </div>
            <span
              className={cn(
                'text-xs font-medium',
                step >= s.id ? 'text-blue-600 dark:text-blue-500' : 'text-content-tertiary',
              )}
            >
              {s.title}
            </span>
          </div>
        ))}
      </div>

      {/* Step Content */}
      <Card>
        <CardContent className="pt-6">
          {step === 1 && (
            <div className="space-y-6">
              <div className="space-y-4">
                <div className="text-sm font-medium text-content-primary">Repository Type</div>
                <div className="grid grid-cols-2 gap-4">
                  <button
                    onClick={() => updateConfig({ repoType: 'official' })}
                    className={cn(
                      'flex flex-col items-center gap-2 rounded-lg border p-4 transition-all',
                      config.repoType === 'official'
                        ? 'border-blue-600 bg-blue-600/10 text-blue-600 dark:text-blue-500'
                        : 'border-border-default bg-surface-secondary hover:border-border-subtle',
                    )}
                  >
                    <span className="font-bold">Official LeRobot</span>
                    <span className="text-xs text-content-secondary">Hugging Face</span>
                  </button>
                  <button
                    onClick={() => updateConfig({ repoType: 'custom' })}
                    className={cn(
                      'flex flex-col items-center gap-2 rounded-lg border p-4 transition-all',
                      config.repoType === 'custom'
                        ? 'border-blue-600 bg-blue-600/10 text-blue-600 dark:text-blue-500'
                        : 'border-border-default bg-surface-secondary hover:border-border-subtle',
                    )}
                  >
                    <span className="font-bold">Custom URL</span>
                    <span className="text-xs text-content-secondary">Git Repository</span>
                  </button>
                </div>
              </div>

              <div className="space-y-2">
                <div className="text-sm font-medium text-content-primary">Version / Tag</div>
                <select
                  className="w-full rounded-md border border-border-default bg-surface-secondary px-3 py-2 text-content-primary focus:border-blue-500 focus:outline-none"
                  value={config.version}
                  onChange={(e) => updateConfig({ version: e.target.value })}
                >
                  <option value="v2.0">v2.0 (Latest Stable)</option>
                  <option value="v1.0">v1.0</option>
                  <option value="main">main (Nightly)</option>
                </select>
              </div>
            </div>
          )}

          {step === 2 && (
            <div className="space-y-6">
              {/* Hardware Detection Card */}
              <div className="rounded-lg border border-info-border bg-info-surface p-4">
                <div className="flex items-start gap-3">
                  <Info className="mt-0.5 h-5 w-5 text-info-icon" />
                  <div>
                    <h3 className="font-medium text-info-content">Hardware Detected</h3>
                    <p className="text-sm text-info-content opacity-90">
                      NVIDIA RTX 4090 (Driver 535.12)
                    </p>
                  </div>
                </div>
              </div>

              <div className="space-y-2">
                <div className="text-sm font-medium text-content-primary">Python Version</div>
                <select
                  className="w-full rounded-md border border-border-default bg-surface-secondary px-3 py-2 text-content-primary focus:border-blue-500 focus:outline-none"
                  value={config.pythonVersion}
                  onChange={(e) => updateConfig({ pythonVersion: e.target.value })}
                >
                  <option value="3.10">3.10 (Recommended)</option>
                  <option value="3.11">3.11</option>
                </select>
              </div>

              <div className="space-y-2">
                <div className="text-sm font-medium text-content-primary">PyTorch Version</div>
                <div className="relative">
                  <select
                    className="w-full rounded-md border border-border-default bg-surface-secondary px-3 py-2 text-content-primary focus:border-blue-500 focus:outline-none"
                    value={config.torchVersion}
                    onChange={(e) => updateConfig({ torchVersion: e.target.value })}
                  >
                    <option value="2.1.2+cu121">2.1.2+cu121 (Recommended)</option>
                    <option value="2.4.0+cu121">2.4.0+cu121</option>
                    <option value="cpu">CPU Only</option>
                  </select>
                  <div className="absolute top-1/2 right-8 -translate-y-1/2">
                    <span className="rounded bg-success-surface px-2 py-0.5 text-xs font-medium text-success-icon">
                      Recommended
                    </span>
                  </div>
                </div>
                <p className="text-xs text-content-tertiary">
                  Compatible with your NVIDIA Driver and LeRobot v2.0.
                </p>
              </div>
            </div>
          )}

          {step === 3 && (
            <div className="space-y-4">
              <p className="text-sm text-content-secondary">
                Select the robots you want to support. This will install additional
                dependencies.
              </p>
              <div className="grid gap-3">
                {['aloha', 'pusht', 'xarm', 'stretch'].map((robot) => (
                  <label
                    key={robot}
                    className={cn(
                      'flex cursor-pointer items-center gap-3 rounded-lg border p-4 transition-colors',
                      config.selectedRobots.includes(robot)
                        ? 'border-blue-600 bg-blue-600/10'
                        : 'border-border-default bg-surface-secondary hover:bg-surface-tertiary',
                    )}
                  >
                    <input
                      type="checkbox"
                      className="h-4 w-4 rounded border-border-default bg-surface-secondary text-blue-600 focus:ring-blue-500"
                      checked={config.selectedRobots.includes(robot)}
                      onChange={(e) => {
                        if (e.target.checked) {
                          updateConfig({
                            selectedRobots: [...config.selectedRobots, robot],
                          });
                        } else {
                          updateConfig({
                            selectedRobots: config.selectedRobots.filter(
                              (r) => r !== robot,
                            ),
                          });
                        }
                      }}
                    />
                    <span className="font-medium text-content-primary capitalize">
                      {robot}
                    </span>
                  </label>
                ))}
              </div>
            </div>
          )}

          {step === 4 && (
            <div className="space-y-6">
              <div className="space-y-3 rounded-lg border border-border-default bg-surface-tertiary p-4">
                <h3 className="font-medium text-content-primary">Summary</h3>
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div className="text-content-tertiary">Repository</div>
                  <div className="text-content-primary">
                    {config.repoUrl} ({config.version})
                  </div>
                  <div className="text-content-tertiary">Python</div>
                  <div className="text-content-primary">{config.pythonVersion}</div>
                  <div className="text-content-tertiary">PyTorch</div>
                  <div className="text-content-primary">{config.torchVersion}</div>
                  <div className="text-content-tertiary">Robots</div>
                  <div className="text-content-primary">
                    {config.selectedRobots.length > 0
                      ? config.selectedRobots.join(', ')
                      : 'None'}
                  </div>
                </div>
              </div>

              <div className="flex gap-3 rounded-lg border border-warning-border bg-warning-surface p-4">
                <AlertTriangle className="h-5 w-5 shrink-0 text-warning-icon" />
                <p className="text-sm text-warning-content">
                  Note: This process requires an active internet connection to download
                  dependencies.
                </p>
              </div>

              <div>
                <button
                  onClick={() => setIsAdvancedOpen(!isAdvancedOpen)}
                  className="text-sm font-medium text-blue-600 hover:text-blue-500 dark:text-blue-500 dark:hover:text-blue-400"
                >
                  {isAdvancedOpen ? 'Hide' : 'Show'} Advanced: Edit Install Script
                </button>

                {isAdvancedOpen && (
                  <div className="mt-2 rounded-lg border border-border-default bg-surface-tertiary p-4 font-mono text-xs text-content-secondary">
                    <p># Generated Install Script</p>
                    <p>uv venv .venv --python {config.pythonVersion}</p>
                    <p>source .venv/bin/activate</p>
                    <p>uv pip install torch=={config.torchVersion}</p>
                    <p>cd src/lerobot</p>
                    <p>uv pip install -e .[{config.selectedRobots.join(',')}]</p>
                  </div>
                )}
              </div>
            </div>
          )}
        </CardContent>
        <CardFooter className="flex justify-between border-t border-border-default p-6">
          <Button variant="ghost" onClick={handleBack}>
            {step === 1 ? t('wizard.buttons.cancel') : t('wizard.buttons.back')}
          </Button>
          <Button onClick={handleNext}>
            {step === 4
              ? t('wizard.buttons.createEnvironment')
              : t('wizard.buttons.next')}
            {step < 4 && <ChevronRight className="ml-2 h-4 w-4" />}
          </Button>
        </CardFooter>
      </Card>
    </div>
  );
}
