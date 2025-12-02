import { useEffect, useRef } from 'react';

/**
 * Custom hook that runs an effect only once, even in React Strict Mode.
 *
 * Use this sparingly - prefer using AbortController with regular useEffect.
 * This is mainly for cases where cleanup isn't possible (e.g., EventSource).
 *
 * @param effect - The effect function to run once
 *
 * @example
 * ```tsx
 * useEffectOnce(() => {
 *   console.log('This runs only once, even in Strict Mode');
 * });
 * ```
 */
export function useEffectOnce(effect: () => void | (() => void)) {
  const hasRun = useRef(false);
  const cleanup = useRef<void | (() => void)>();
  const effectRef = useRef(effect);

  // Update the ref to latest effect in a separate effect
  useEffect(() => {
    effectRef.current = effect;
  });

  useEffect(() => {
    if (!hasRun.current) {
      hasRun.current = true;
      cleanup.current = effectRef.current();
    }

    return () => {
      if (cleanup.current) {
        cleanup.current();
      }
    };
  }, []);
}
