import CodeMirror from '@uiw/react-codemirror';
import { javascript } from '@codemirror/lang-javascript';
import { oneDark } from '@codemirror/theme-one-dark';
import { EditorView } from '@codemirror/view';
import { useEffect, useState } from 'react';

interface CodeEditorProps {
  value: string;
  onChange?: (value: string) => void;
  language?: 'shell' | 'bash' | 'powershell' | 'javascript';
  readOnly?: boolean;
  height?: string;
  minHeight?: string;
  maxHeight?: string;
  placeholder?: string;
  className?: string;
}

export function CodeEditor({
  value,
  onChange,
  language,
  readOnly = false,
  height,
  minHeight,
  maxHeight = '400px',
  placeholder,
  className = '',
}: CodeEditorProps) {
  const [theme, setTheme] = useState<'light' | 'dark'>(() =>
    document.documentElement.classList.contains('dark') ? 'dark' : 'light',
  );

  // Detect theme from document
  useEffect(() => {
    // Watch for theme changes
    const observer = new MutationObserver((mutations) => {
      mutations.forEach((mutation) => {
        if (mutation.attributeName === 'class') {
          const isDark = document.documentElement.classList.contains('dark');
          setTheme(isDark ? 'dark' : 'light');
        }
      });
    });

    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['class'],
    });

    return () => observer.disconnect();
  }, []);

  const extensions = [EditorView.lineWrapping];

  if (language === 'javascript') {
    extensions.push(javascript());
  }

  if (readOnly) {
    extensions.push(EditorView.editable.of(false));
  }

  return (
    <div className={className}>
      <CodeMirror
        value={value}
        height={height}
        minHeight={minHeight}
        maxHeight={maxHeight}
        theme={theme === 'dark' ? oneDark : 'light'}
        extensions={extensions}
        onChange={onChange}
        placeholder={placeholder}
        basicSetup={{
          lineNumbers: true,
          highlightActiveLineGutter: !readOnly,
          highlightActiveLine: !readOnly,
          foldGutter: false,
          dropCursor: !readOnly,
          allowMultipleSelections: !readOnly,
          indentOnInput: !readOnly,
          bracketMatching: true,
          closeBrackets: !readOnly,
          autocompletion: false,
          rectangularSelection: !readOnly,
          crosshairCursor: !readOnly,
          highlightSelectionMatches: !readOnly,
          closeBracketsKeymap: !readOnly,
          searchKeymap: true,
          foldKeymap: false,
          completionKeymap: false,
          lintKeymap: false,
        }}
        className="border-border-default overflow-hidden rounded-md border"
      />
    </div>
  );
}
