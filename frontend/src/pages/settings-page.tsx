import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { Save, RotateCcw, AlertCircle, CheckCircle2, Trash2, Plus, Sun, Moon, Monitor } from "lucide-react";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { cn } from "../utils/cn";
import { useTheme } from "../contexts/theme-context";

interface ToolSource {
  type: "bundled" | "custom";
  custom_path: string | null;
}

interface RepositorySource {
  name: string;
  url: string;
  is_default: boolean;
}

interface PyPIMirror {
  name: string;
  url: string;
  is_default: boolean;
}

interface AppConfig {
  server: {
    port: number;
    host: string;
    auto_open_browser: boolean;
  };
  ui: {
    theme: "system" | "light" | "dark";
    preferred_language: "en" | "zh";
  };
  paths: {
    data_dir: string;
    repos_dir: string | null;
    environments_dir: string | null;
    logs_dir: string | null;
    cache_dir: string | null;
  };
  tools: {
    git: ToolSource;
    uv: ToolSource;
  };
  repositories: {
    lerobot_sources: RepositorySource[];
    default_branch: string;
    default_version: string;
  };
  pypi: {
    mirrors: PyPIMirror[];
  };
  huggingface: {
    token: string;
    cache_dir: string;
  };
  advanced: {
    installation_timeout: number;
    log_level: "INFO" | "DEBUG" | "TRACE";
  };
}


// Helper to convert snake_case to camelCase for i18n keys
function toCamelCase(str: string): string {
  return str.replace(/_([a-z])/g, (g) => g[1].toUpperCase());
}

export function SettingsPage() {
  const { t, i18n } = useTranslation();
  const { setTheme: setAppTheme } = useTheme();
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [savedConfig, setSavedConfig] = useState<AppConfig | null>(null);
  const [hasEnvironments, setHasEnvironments] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadConfig();
    checkEnvironments();

    // Cleanup: revert theme and language on unmount if not saved
    return () => {
      if (savedConfig && config) {
        if (savedConfig.ui.theme !== config.ui.theme) {
          setAppTheme(savedConfig.ui.theme);
        }
        if (savedConfig.ui.preferred_language !== config.ui.preferred_language) {
          i18n.changeLanguage(savedConfig.ui.preferred_language);
        }
      }
    };
  }, []);

  // Live preview: Apply theme changes immediately via ThemeProvider
  useEffect(() => {
    if (config?.ui.theme) {
      setAppTheme(config.ui.theme);
    }
  }, [config?.ui.theme, setAppTheme]);

  // Live preview: Apply language changes immediately
  useEffect(() => {
    if (config?.ui.preferred_language && config.ui.preferred_language !== i18n.language) {
      i18n.changeLanguage(config.ui.preferred_language);
    }
  }, [config?.ui.preferred_language, i18n]);

  const loadConfig = async () => {
    try {
      console.log("Loading config...");
      const response = await fetch("/api/config");
      if (!response.ok) throw new Error(`Failed to load config: ${response.statusText}`);
      const data = await response.json();
      console.log("Config loaded:", data);
      setConfig(data);
      setSavedConfig(data); // Store the saved config for comparison
    } catch (error) {
      console.error("Error loading config:", error);
      setError(error instanceof Error ? error.message : "Unknown error loading config");
      setMessage({ type: "error", text: t("settings.messages.saveError") });
    } finally {
      setLoading(false);
    }
  };

  const checkEnvironments = async () => {
    try {
      const response = await fetch("/api/config/has-environments");
      if (!response.ok) throw new Error("Failed to check environments");
      const data = await response.json();
      setHasEnvironments(data.has_environments);
    } catch (error) {
      console.error("Failed to check environments:", error);
    }
  };

  // Helper to check if a specific section has unsaved changes
  const hasUnsavedChanges = (section: 'theme' | 'language') => {
    if (!config || !savedConfig) return false;
    if (section === 'theme') {
      return config.ui.theme !== savedConfig.ui.theme;
    }
    if (section === 'language') {
      return config.ui.preferred_language !== savedConfig.ui.preferred_language;
    }
    return false;
  };

  const saveConfig = async () => {
    if (!config) return;
    
    setSaving(true);
    setMessage(null);
    
    try {
      const response = await fetch("/api/config", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(config),
      });
      
      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || "Failed to save config");
      }
      
      // Update saved config after successful save
      setSavedConfig(config);
      
      setMessage({ type: "success", text: t("settings.messages.saveSuccess") });
      
      // Language is already applied via live preview, no need to change again
      
      // Reload to get updated config
      await loadConfig();
      await checkEnvironments();
    } catch (error) {
      setMessage({ 
        type: "error", 
        text: error instanceof Error ? error.message : t("settings.messages.saveError") 
      });
    } finally {
      setSaving(false);
    }
  };

  const resetConfig = async () => {
    if (!confirm(t("settings.messages.resetConfirm"))) return;
    
    setSaving(true);
    setMessage(null);
    
    try {
      const response = await fetch("/api/config/reset", { method: "POST" });
      if (!response.ok) throw new Error("Failed to reset config");
      const data = await response.json();
      setConfig(data);
      setMessage({ type: "success", text: t("settings.messages.saveSuccess") });
    } catch (error) {
      setMessage({ type: "error", text: t("settings.messages.saveError") });
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-zinc-400">Loading settings...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-64 flex-col gap-4">
        <div className="text-red-400">Error loading settings: {error}</div>
        <Button onClick={loadConfig}>Retry</Button>
      </div>
    );
  }

  if (!config) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-zinc-400">No configuration loaded.</div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-zinc-900 dark:text-zinc-100">{t("settings.title")}</h1>
        <p className="text-zinc-600 dark:text-zinc-400">{t("settings.subtitle")}</p>
      </div>

      {/* Message */}
      {message && (
        <div
          className={cn(
            "flex items-center gap-3 rounded-lg border p-4",
            message.type === "success"
              ? "border-green-900/50 bg-green-900/20 text-green-100"
              : "border-red-900/50 bg-red-900/20 text-red-100"
          )}
        >
          {message.type === "success" ? (
            <CheckCircle2 className="h-5 w-5 text-green-500" />
          ) : (
            <AlertCircle className="h-5 w-5 text-red-500" />
          )}
          <span>{message.text}</span>
        </div>
      )}

      {/* Appearance */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>{t("settings.appearance.title")}</CardTitle>
              <p className="text-sm text-zinc-600 dark:text-zinc-400">{t("settings.appearance.description")}</p>
            </div>
            {hasUnsavedChanges('theme') && (
              <span className="text-xs text-amber-500 font-medium px-2 py-1 bg-amber-900/20 rounded border border-amber-900/50">
                {t("settings.unsavedChanges")}
              </span>
            )}
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">{t("settings.appearance.theme")}</label>
            <p className="text-xs text-zinc-600 dark:text-zinc-500 mb-3">{t("settings.appearance.themeDescription")}</p>
            <div className="grid grid-cols-3 gap-3">
              {(["system", "light", "dark"] as const).map((theme) => {
                const Icon = theme === "system" ? Monitor : theme === "light" ? Sun : Moon;
                return (
                  <button
                    key={theme}
                    onClick={() => setConfig({ ...config, ui: { ...config.ui, theme } })}
                    className={cn(
                      "flex flex-col items-center gap-2 rounded-lg border p-4 transition-all",
                      config.ui.theme === theme
                        ? "border-blue-600 bg-blue-600/10 text-blue-500"
                        : "border-zinc-300 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 text-zinc-600 dark:text-zinc-400 hover:border-zinc-400 dark:hover:border-zinc-700"
                    )}
                  >
                    <Icon className="h-5 w-5" />
                    <span className="text-sm font-medium">{t(`settings.appearance.${theme}`)}</span>
                  </button>
                );
              })}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Language */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>{t("settings.language.title")}</CardTitle>
              <p className="text-sm text-zinc-600 dark:text-zinc-400">{t("settings.language.description")}</p>
            </div>
            {hasUnsavedChanges('language') && (
              <span className="text-xs text-amber-500 font-medium px-2 py-1 bg-amber-900/20 rounded border border-amber-900/50">
                {t("settings.unsavedChanges")}
              </span>
            )}
          </div>
        </CardHeader>
        <CardContent>
          <div>
            <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">{t("settings.language.preferredLanguage")}</label>
            <select
              className="mt-2 w-full rounded-md border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2 text-zinc-900 dark:text-zinc-100 focus:border-blue-500 focus:outline-none"
              value={config.ui.preferred_language}
              onChange={(e) =>
                setConfig({ ...config, ui: { ...config.ui, preferred_language: e.target.value as "en" | "zh" } })
              }
            >
              <option value="en">English</option>
              <option value="zh">中文</option>
            </select>
          </div>
        </CardContent>
      </Card>

      {/* Paths */}
      <Card>
        <CardHeader>
          <CardTitle>{t("settings.paths.title")}</CardTitle>
          <p className="text-sm text-zinc-600 dark:text-zinc-400">{t("settings.paths.description")}</p>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Data Directory */}
          <div>
            <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">{t("settings.paths.dataDir")}</label>
            <p className="text-xs text-zinc-600 dark:text-zinc-500 mb-2">
              {t("settings.paths.dataDirDescription")}
              {hasEnvironments && ` ${t("settings.paths.dataDirLocked")}`}
            </p>
            <input
              type="text"
              className={cn(
                "w-full rounded-md border px-3 py-2 focus:border-blue-500 focus:outline-none",
                hasEnvironments
                  ? "border-zinc-300 dark:border-zinc-800 bg-zinc-200 dark:bg-zinc-900/50 text-zinc-500 dark:text-zinc-400 cursor-not-allowed opacity-60"
                  : "border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 text-zinc-900 dark:text-zinc-100"
              )}
              value={config.paths.data_dir}
              onChange={(e) =>
                setConfig({ ...config, paths: { ...config.paths, data_dir: e.target.value } })
              }
              disabled={hasEnvironments}
            />
          </div>

          {/* Read-only paths */}
          {(["repos_dir", "environments_dir", "logs_dir", "cache_dir"] as const).map((pathKey) => (
            <div key={pathKey}>
              <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
                {t(`settings.paths.${toCamelCase(pathKey)}`)}
              </label>
              <input
                type="text"
                className="mt-2 w-full rounded-md border border-zinc-300 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900/50 px-3 py-2 text-zinc-500 dark:text-zinc-400 cursor-not-allowed"
                value={config.paths[pathKey] || ""}
                disabled
                readOnly
              />
            </div>
          ))}


        </CardContent>
      </Card>

      {/* Tools */}
      <Card>
        <CardHeader>
          <CardTitle>{t("settings.tools.title")}</CardTitle>
          <p className="text-sm text-zinc-600 dark:text-zinc-400">{t("settings.tools.description")}</p>
        </CardHeader>
        <CardContent className="space-y-6">
          {(["git", "uv"] as const).map((tool) => (
            <div key={tool} className="space-y-3">
              <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">{t(`settings.tools.${tool}`)}</label>
              
              {/* Source selection */}
              <div className="flex gap-3">
                <button
                  onClick={() =>
                    setConfig({
                      ...config,
                      tools: { ...config.tools, [tool]: { type: "bundled", custom_path: "" } },
                    })
                  }
                  className={cn(
                    "flex-1 rounded-md border p-3 transition-all",
                    config.tools[tool].type === "bundled"
                      ? "border-blue-600 bg-blue-600/10 text-blue-500"
                      : "border-zinc-300 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 text-zinc-600 dark:text-zinc-400 hover:border-zinc-400 dark:hover:border-zinc-700"
                  )}
                >
                  {t("settings.tools.bundled")}
                </button>
                <button
                  onClick={() =>
                    setConfig({
                      ...config,
                      tools: { ...config.tools, [tool]: { ...config.tools[tool], type: "custom" } },
                    })
                  }
                  className={cn(
                    "flex-1 rounded-md border p-3 transition-all",
                    config.tools[tool].type === "custom"
                      ? "border-blue-600 bg-blue-600/10 text-blue-500"
                      : "border-zinc-300 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 text-zinc-600 dark:text-zinc-400 hover:border-zinc-400 dark:hover:border-zinc-700"
                  )}
                >
                  {t("settings.tools.custom")}
                </button>
              </div>

              {/* Custom path input */}
              {config.tools[tool].type === "custom" && (
                <input
                  type="text"
                  placeholder={t(`settings.tools.${tool}PathPlaceholder`)}
                  className="w-full rounded-md border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2 text-zinc-900 dark:text-zinc-100 focus:border-blue-500 focus:outline-none"
                  value={config.tools[tool].custom_path || ""}
                  onChange={(e) =>
                    setConfig({
                      ...config,
                      tools: { ...config.tools, [tool]: { ...config.tools[tool], custom_path: e.target.value } },
                    })
                  }
                />
              )}
            </div>
          ))}
        </CardContent>
      </Card>

      {/* LeRobot Repositories */}
      <Card>
        <CardHeader>
          <CardTitle>{t("settings.repositories.title")}</CardTitle>
          <p className="text-sm text-zinc-600 dark:text-zinc-400">{t("settings.repositories.description")}</p>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            {config.repositories.lerobot_sources.map((source, index) => (
              <div key={index} className="flex gap-2 items-start p-3 rounded-md border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900/50">
                <div className="flex-1 space-y-2">
                  <input
                    type="text"
                    placeholder={t("settings.repositories.name")}
                    className="w-full rounded-md border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2 text-zinc-900 dark:text-zinc-100 focus:border-blue-500 focus:outline-none disabled:opacity-50"
                    value={source.name}
                    onChange={(e) => {
                      const newSources = [...config.repositories.lerobot_sources];
                      newSources[index] = { ...source, name: e.target.value };
                      setConfig({ ...config, repositories: { ...config.repositories, lerobot_sources: newSources } });
                    }}
                    disabled={source.is_default}
                  />
                  <input
                    type="text"
                    placeholder={t("settings.repositories.url")}
                    className="w-full rounded-md border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2 text-zinc-900 dark:text-zinc-100 focus:border-blue-500 focus:outline-none disabled:opacity-50"
                    value={source.url}
                    onChange={(e) => {
                      const newSources = [...config.repositories.lerobot_sources];
                      newSources[index] = { ...source, url: e.target.value };
                      setConfig({ ...config, repositories: { ...config.repositories, lerobot_sources: newSources } });
                    }}
                    disabled={source.is_default}
                  />
                  {source.is_default && (
                    <span className="inline-flex items-center rounded-full bg-blue-50 px-2 py-1 text-xs font-medium text-blue-700 ring-1 ring-inset ring-blue-700/10 dark:bg-blue-400/10 dark:text-blue-400 dark:ring-blue-400/30">
                      {t("settings.repositories.default")}
                    </span>
                  )}
                </div>
                <div className="flex flex-col gap-2 items-end">
                  {!source.is_default && (
                    <div className="flex gap-2">
                      <button
                        onClick={() => {
                          const newSources = config.repositories.lerobot_sources.map((s, i) => ({
                            ...s,
                            is_default: i === index,
                          }));
                          setConfig({ ...config, repositories: { ...config.repositories, lerobot_sources: newSources } });
                        }}
                        className="p-2 rounded-md border border-zinc-300 dark:border-zinc-700 bg-zinc-100 dark:bg-zinc-900 text-zinc-600 dark:text-zinc-400 hover:bg-zinc-200 dark:hover:bg-zinc-800 hover:text-zinc-900 dark:hover:text-zinc-200 text-xs"
                        title={t("settings.repositories.setAsDefault")}
                      >
                        {t("settings.repositories.setAsDefault")}
                      </button>
                      <button
                        onClick={() => {
                          const newSources = config.repositories.lerobot_sources.filter((_, i) => i !== index);
                          setConfig({ ...config, repositories: { ...config.repositories, lerobot_sources: newSources } });
                        }}
                        className="p-2 rounded-md border border-zinc-300 dark:border-zinc-700 bg-zinc-100 dark:bg-zinc-900 text-red-600 dark:text-red-500 hover:bg-red-100 dark:hover:bg-red-900/20 hover:border-red-400 dark:hover:border-red-700"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
          <Button
            variant="secondary"
            onClick={() => {
              const newSources = [
                ...config.repositories.lerobot_sources,
                { name: "Custom", url: "", is_default: false },
              ];
              setConfig({ ...config, repositories: { ...config.repositories, lerobot_sources: newSources } });
            }}
          >
            <Plus className="mr-2 h-4 w-4" />
            {t("settings.repositories.addSource")}
          </Button>
        </CardContent>
      </Card>

      {/* PyPI Mirrors */}
      <Card>
        <CardHeader>
          <CardTitle>{t("settings.pypi.title")}</CardTitle>
          <p className="text-sm text-zinc-600 dark:text-zinc-400">{t("settings.pypi.description")}</p>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            {config.pypi.mirrors.map((mirror, index) => (
              <div key={index} className="flex gap-2 items-start p-3 rounded-md border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900/50">
                <div className="flex-1 space-y-2">
                  <input
                    type="text"
                    placeholder={t("settings.pypi.name")}
                    className="w-full rounded-md border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2 text-zinc-900 dark:text-zinc-100 focus:border-blue-500 focus:outline-none"
                    value={mirror.name}
                    onChange={(e) => {
                      const newMirrors = [...config.pypi.mirrors];
                      newMirrors[index] = { ...mirror, name: e.target.value };
                      setConfig({ ...config, pypi: { ...config.pypi, mirrors: newMirrors } });
                    }}
                  />
                  <input
                    type="text"
                    placeholder={t("settings.pypi.url")}
                    className="w-full rounded-md border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2 text-zinc-900 dark:text-zinc-100 focus:border-blue-500 focus:outline-none"
                    value={mirror.url}
                    onChange={(e) => {
                      const newMirrors = [...config.pypi.mirrors];
                      newMirrors[index] = { ...mirror, url: e.target.value };
                      setConfig({ ...config, pypi: { ...config.pypi, mirrors: newMirrors } });
                    }}
                  />
                  {mirror.is_default && (
                    <span className="inline-flex items-center rounded-full bg-blue-50 px-2 py-1 text-xs font-medium text-blue-700 ring-1 ring-inset ring-blue-700/10 dark:bg-blue-400/10 dark:text-blue-400 dark:ring-blue-400/30">
                      {t("settings.pypi.default")}
                    </span>
                  )}
                </div>
                <div className="flex flex-col gap-2 items-end">
                  {!mirror.is_default && (
                    <div className="flex gap-2">
                      <button
                        onClick={() => {
                          const newMirrors = config.pypi.mirrors.map((m, i) => ({
                            ...m,
                            is_default: i === index,
                          }));
                          setConfig({ ...config, pypi: { ...config.pypi, mirrors: newMirrors } });
                        }}
                        className="p-2 rounded-md border border-zinc-300 dark:border-zinc-700 bg-zinc-100 dark:bg-zinc-900 text-zinc-600 dark:text-zinc-400 hover:bg-zinc-200 dark:hover:bg-zinc-800 hover:text-zinc-900 dark:hover:text-zinc-200 text-xs"
                        title={t("settings.pypi.setAsDefault")}
                      >
                        {t("settings.pypi.setAsDefault")}
                      </button>
                      <button
                        onClick={() => {
                          const newMirrors = config.pypi.mirrors.filter((_, i) => i !== index);
                          setConfig({ ...config, pypi: { ...config.pypi, mirrors: newMirrors } });
                        }}
                        className="p-2 rounded-md border border-zinc-300 dark:border-zinc-700 bg-zinc-100 dark:bg-zinc-900 text-red-600 dark:text-red-500 hover:bg-red-100 dark:hover:bg-red-900/20 hover:border-red-400 dark:hover:border-red-700"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
          <Button
            variant="secondary"
            onClick={() => {
              const newMirrors = [...config.pypi.mirrors, { name: "Custom Mirror", url: "", is_default: false }];
              setConfig({ ...config, pypi: { ...config.pypi, mirrors: newMirrors } });
            }}
          >
            <Plus className="mr-2 h-4 w-4" />
            {t("settings.pypi.addMirror")}
          </Button>
        </CardContent>
      </Card>

      {/* Advanced */}
      <Card>
        <CardHeader>
          <CardTitle>{t("settings.advanced.title")}</CardTitle>
          <p className="text-sm text-zinc-600 dark:text-zinc-400">{t("settings.advanced.description")}</p>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">{t("settings.advanced.installationTimeout")}</label>
            <p className="text-xs text-zinc-600 dark:text-zinc-500 mb-2">{t("settings.advanced.installationTimeoutDescription")}</p>
            <input
              type="number"
              className="mt-2 w-full rounded-md border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2 text-zinc-900 dark:text-zinc-100 focus:border-blue-500 focus:outline-none"
              value={config.advanced.installation_timeout}
              onChange={(e) =>
                setConfig({ ...config, advanced: { ...config.advanced, installation_timeout: parseInt(e.target.value) } })
              }
            />
          </div>

          <div>
            <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">{t("settings.advanced.logLevel")}</label>
            <p className="text-xs text-zinc-600 dark:text-zinc-500 mb-2">{t("settings.advanced.logLevelDescription")}</p>
            <select
              className="mt-2 w-full rounded-md border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2 text-zinc-900 dark:text-zinc-100 focus:border-blue-500 focus:outline-none"
              value={config.advanced.log_level}
              onChange={(e) =>
                setConfig({
                  ...config,
                  advanced: { ...config.advanced, log_level: e.target.value as "INFO" | "DEBUG" | "TRACE" },
                })
              }
            >
              <option value="INFO">{t("settings.advanced.logLevelInfo")}</option>
              <option value="DEBUG">{t("settings.advanced.logLevelDebug")}</option>
              <option value="TRACE">{t("settings.advanced.logLevelTrace")}</option>
            </select>
          </div>
        </CardContent>
      </Card>

      {/* Actions */}
      <div className="flex justify-between border-t border-zinc-800 pt-6">
        <Button variant="ghost" onClick={resetConfig} disabled={saving}>
          <RotateCcw className="mr-2 h-4 w-4" />
          {t("settings.buttons.reset")}
        </Button>
        <Button onClick={saveConfig} disabled={saving}>
          <Save className="mr-2 h-4 w-4" />
          {saving ? "Saving..." : t("settings.buttons.save")}
        </Button>
      </div>
    </div>
  );
}
