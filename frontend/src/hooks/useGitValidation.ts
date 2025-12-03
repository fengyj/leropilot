import { useState, useCallback } from 'react';

interface GitValidationResult {
  validation: string;
  isValidating: boolean;
  error: string | null;
  validate: (path: string) => Promise<void>;
  clear: () => void;
}

/**
 * Custom hook for Git path validation.
 *
 * Provides a unified interface for validating Git executable paths,
 * handling loading states, errors, and validation results.
 *
 * @returns Object containing validation state and control functions
 *
 * @example
 * ```tsx
 * const { validation, isValidating, error, validate } = useGitValidation();
 *
 * // Validate a path
 * await validate('/usr/bin/git');
 *
 * // Check results
 * if (validation) {
 *   console.log('Git version:', validation);
 * }
 * ```
 */
export const useGitValidation = (): GitValidationResult => {
  const [validation, setValidation] = useState('');
  const [isValidating, setIsValidating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const validate = useCallback(async (path: string) => {
    if (!path) {
      setValidation('');
      setError(null);
      return;
    }

    setIsValidating(true);
    setError(null);

    try {
      const response = await fetch('/api/tools/git/validate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();

      if (data.valid) {
        setValidation(data.version);
        setError(null);
      } else {
        setValidation('');
        setError(data.error || 'Invalid Git path');
      }
    } catch (err) {
      console.error('Failed to validate git path:', err);
      setError('Failed to validate Git path');
      setValidation('');
    } finally {
      setIsValidating(false);
    }
  }, []);

  const clear = useCallback(() => {
    setValidation('');
    setError(null);
  }, []);

  return {
    validation,
    isValidating,
    error,
    validate,
    clear,
  };
};
