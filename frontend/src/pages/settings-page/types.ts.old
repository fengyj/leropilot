/**
 * Type definitions for Settings Page
 *
 * These types are now derived from the auto-generated OpenAPI types.
 */

import { components } from '../../types/api';

// Re-export generated types
export type ToolSource = components['schemas']['ToolSource'];
export type RepositorySource = components['schemas']['RepositorySource'];
export type PyPIMirror = components['schemas']['PyPIMirror'];

// AppConfig from API might have optional fields, but in the UI we expect them to be present
// as we load the full config. We use Required to enforce this.
type GeneratedAppConfig = components['schemas']['AppConfig-Output'];

export interface AppConfig {
  server: Required<NonNullable<GeneratedAppConfig['server']>>;
  ui: Required<NonNullable<GeneratedAppConfig['ui']>>;
  paths: Required<NonNullable<GeneratedAppConfig['paths']>>;
  tools: {
    git: ToolSource;
  };
  repositories: {
    lerobot_sources: RepositorySource[];
  };
  pypi: {
    mirrors: PyPIMirror[];
  };
  advanced: Required<NonNullable<GeneratedAppConfig['advanced']>>;
  huggingface?: components['schemas']['HuggingFaceConfig'];
}
