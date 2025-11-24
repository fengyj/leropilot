import CodeMirror, { ReactCodeMirrorRef } from '@uiw/react-codemirror';
import { oneDark } from '@codemirror/theme-one-dark';
import { EditorView } from '@codemirror/view';
import { useEffect, useState, useRef } from 'react';

interface LogViewerProps {
  logs: string[];
  height?: string;
  minHeight?: string;
  maxHeight?: string;
  autoScroll?: boolean;
  className?: string;
}

export function LogViewer({
  logs,
  height,
  minHeight,
  maxHeight = '400px',
  autoScroll = true,
  className = '',
}: LogViewerProps) {
  const [theme, setTheme] = useState<'light' | 'dark'>(() =>
    document.documentElement.classList.contains('dark') ? 'dark' : 'light',
  );
  const editorRef = useRef<ReactCodeMirrorRef>(null);

  // Detect theme from document
  useEffect(() => {
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

  // Auto-scroll to bottom when logs change
  useEffect(() => {
    if (autoScroll && editorRef.current) {
      const view = editorRef.current.view;
      if (view) {
        const lastLine = view.state.doc.lines;
        const pos = view.state.doc.line(lastLine).to;
        view.dispatch({
          selection: { anchor: pos, head: pos },
          scrollIntoView: true,
        });
      }
    }
  }, [logs, autoScroll]);

  const logContent = logs.join('\n');

  const extensions = [EditorView.editable.of(false), EditorView.lineWrapping];

  return (
    <div className={className}>
      <CodeMirror
        ref={editorRef}
        value={logContent}
        height={height}
        minHeight={minHeight}
        maxHeight={maxHeight}
        theme={theme === 'dark' ? oneDark : 'light'}
        extensions={extensions}
        basicSetup={{
          lineNumbers: false,
          highlightActiveLineGutter: false,
          highlightActiveLine: false,
          foldGutter: false,
          dropCursor: false,
          allowMultipleSelections: false,
          indentOnInput: false,
          bracketMatching: false,
          closeBrackets: false,
          autocompletion: false,
          rectangularSelection: false,
          crosshairCursor: false,
          highlightSelectionMatches: false,
          closeBracketsKeymap: false,
          searchKeymap: true,
          foldKeymap: false,
          completionKeymap: false,
          lintKeymap: false,
        }}
        className="border-border-default overflow-hidden rounded-md border font-mono text-xs"
      />
    </div>
  );
}
