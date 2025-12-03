import { Card, CardContent, CardHeader, CardTitle } from '../../../components/ui/card';
import type { AppConfig } from '../types';

interface HuggingFaceSectionProps {
  config: AppConfig;
  setConfig: (config: AppConfig) => void;
}

export function HuggingFaceSection({ config, setConfig }: HuggingFaceSectionProps) {
  // const { t } = useTranslation();

  // If huggingface config is missing, initialize it
  if (!config.huggingface) {
    return null;
  }

  return (
    <Card>
      <CardHeader>
        <div className="space-y-1.5">
          <CardTitle>HuggingFace</CardTitle>
          <p className="text-content-secondary text-sm">
            Configure HuggingFace Hub settings.
          </p>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <label
            htmlFor="hf-token"
            className="text-content-secondary text-xs font-medium uppercase"
          >
            Token
          </label>
          <input
            id="hf-token"
            type="password"
            className="border-border-default bg-surface-secondary text-content-primary w-full rounded-md border px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
            value={config.huggingface.token || ''}
            onChange={(e) =>
              setConfig({
                ...config,
                huggingface: {
                  ...config.huggingface!,
                  token: e.target.value,
                },
              })
            }
            placeholder="hf_..."
          />
          <p className="text-content-tertiary text-xs">
            Optional: Access token for private repositories or higher rate limits.
          </p>
        </div>

        <div className="space-y-2">
          <label
            htmlFor="hf-cache-dir"
            className="text-content-secondary text-xs font-medium uppercase"
          >
            Cache Directory
          </label>
          <input
            id="hf-cache-dir"
            type="text"
            className="border-border-default bg-surface-secondary text-content-primary w-full rounded-md border px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
            value={config.huggingface.cache_dir || ''}
            onChange={(e) =>
              setConfig({
                ...config,
                huggingface: {
                  ...config.huggingface!,
                  cache_dir: e.target.value,
                },
              })
            }
            placeholder="Default system cache"
          />
        </div>
      </CardContent>
    </Card>
  );
}
