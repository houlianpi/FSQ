import { useEffect, useRef, useState } from 'react';
import { AlertCircle, ChevronDown, ChevronRight, FileCode2, FileText, Folder, FolderOpen, RefreshCw } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { controlPlaneClient, toApiError } from '../../api/controlPlaneClient';
import type { ApiErrorBody, WorkspaceEntriesResponse, WorkspaceEntry, WorkspaceFileResponse } from '../../api/types';

interface WorkspaceBrowserProps { workspaceName: string }

function formatBytes(bytes: number | null): string {
  if (bytes === null) return 'Directory';
  if (bytes < 1024) return `${bytes} B`;
  return `${(bytes / 1024).toFixed(bytes < 10240 ? 1 : 0)} KB`;
}

function TreeEntry({ entry, depth, expanded, childrenByPath, loadingPaths, selectedPath, onDirectory, onFile }: {
  entry: WorkspaceEntry;
  depth: number;
  expanded: Set<string>;
  childrenByPath: Record<string, WorkspaceEntriesResponse>;
  loadingPaths: Set<string>;
  selectedPath: string | null;
  onDirectory: (path: string) => void;
  onFile: (path: string) => void;
}) {
  const isDirectory = entry.kind === 'directory';
  const isExpanded = expanded.has(entry.path);
  const Icon = isDirectory ? (isExpanded ? FolderOpen : Folder) : entry.name.toLowerCase().endsWith('.md') ? FileText : FileCode2;
  return <li>
    <button
      className="cp-tree-entry"
      style={{ paddingLeft: `${10 + depth * 18}px` }}
      type="button"
      aria-expanded={isDirectory ? isExpanded : undefined}
      aria-current={!isDirectory && selectedPath === entry.path ? 'true' : undefined}
      onClick={() => isDirectory ? onDirectory(entry.path) : onFile(entry.path)}
    >
      {isDirectory ? (isExpanded ? <ChevronDown aria-hidden="true" /> : <ChevronRight aria-hidden="true" />) : <span className="cp-tree-spacer" />}
      <Icon aria-hidden="true" /><span>{entry.name}</span>
    </button>
    {isDirectory && isExpanded && <ul>
      {loadingPaths.has(entry.path) && <li className="cp-tree-state" style={{ paddingLeft: `${30 + depth * 18}px` }}>Loading…</li>}
      {!loadingPaths.has(entry.path) && childrenByPath[entry.path]?.entries.length === 0 && <li className="cp-tree-state" style={{ paddingLeft: `${30 + depth * 18}px` }}>Empty directory</li>}
      {childrenByPath[entry.path]?.entries.map((child) => <TreeEntry key={child.path} entry={child} depth={depth + 1} expanded={expanded} childrenByPath={childrenByPath} loadingPaths={loadingPaths} selectedPath={selectedPath} onDirectory={onDirectory} onFile={onFile} />)}
    </ul>}
  </li>;
}

export function WorkspaceBrowser({ workspaceName }: WorkspaceBrowserProps) {
  const [root, setRoot] = useState<WorkspaceEntriesResponse | null>(null);
  const [childrenByPath, setChildrenByPath] = useState<Record<string, WorkspaceEntriesResponse>>({});
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [loadingPaths, setLoadingPaths] = useState<Set<string>>(new Set());
  const [treeError, setTreeError] = useState<ApiErrorBody | null>(null);
  const [file, setFile] = useState<WorkspaceFileResponse | null>(null);
  const [fileError, setFileError] = useState<ApiErrorBody | null>(null);
  const [fileLoading, setFileLoading] = useState(false);
  const [fileTab, setFileTab] = useState<'preview' | 'code'>('preview');
  const [requestedFilePath, setRequestedFilePath] = useState<string | null>(null);
  const activeRequests = useRef<Set<AbortController>>(new Set());
  const activeFileRequest = useRef<AbortController | null>(null);

  const trackedController = () => {
    const controller = new AbortController();
    activeRequests.current.add(controller);
    return controller;
  };

  const loadRoot = () => {
    setTreeError(null);
    setRoot(null);
    const controller = trackedController();
    controlPlaneClient.workspaceEntries(workspaceName, '', controller.signal).then((response) => {
      if (!controller.signal.aborted) setRoot(response);
    }).catch((error) => {
      if (controller.signal.aborted) return;
      setTreeError(toApiError(error));
    }).finally(() => activeRequests.current.delete(controller));
    return controller;
  };

  useEffect(() => {
    setChildrenByPath({});
    setExpanded(new Set());
    setLoadingPaths(new Set());
    setFile(null);
    setFileError(null);
    setFileLoading(false);
    setRequestedFilePath(null);
    const controller = loadRoot();
    return () => {
      controller.abort();
      activeRequests.current.forEach((request) => request.abort());
      activeRequests.current.clear();
      activeFileRequest.current = null;
    };
  }, [workspaceName]);

  const onDirectory = (path: string) => {
    if (expanded.has(path)) {
      setExpanded((current) => { const next = new Set(current); next.delete(path); return next; });
      return;
    }
    setExpanded((current) => new Set(current).add(path));
    if (childrenByPath[path] || loadingPaths.has(path)) return;
    setLoadingPaths((current) => new Set(current).add(path));
    const controller = trackedController();
    controlPlaneClient.workspaceEntries(workspaceName, path, controller.signal).then((response) => {
      if (!controller.signal.aborted) setChildrenByPath((current) => ({ ...current, [path]: response }));
    }).catch((error) => { if (!controller.signal.aborted) setTreeError(toApiError(error)); }).finally(() => {
      activeRequests.current.delete(controller);
      if (!controller.signal.aborted) setLoadingPaths((current) => { const next = new Set(current); next.delete(path); return next; });
    });
  };

  const onFile = (path: string) => {
    activeFileRequest.current?.abort();
    setFileLoading(true);
    setFileError(null);
    setFile(null);
    setRequestedFilePath(path);
    const controller = trackedController();
    activeFileRequest.current = controller;
    controlPlaneClient.workspaceFile(workspaceName, path, controller.signal).then((response) => {
      if (controller.signal.aborted || activeFileRequest.current !== controller) return;
      setFile(response);
      setFileTab(response.presentation === 'markdown' ? 'preview' : 'code');
    }).catch((error) => { if (!controller.signal.aborted) setFileError(toApiError(error)); }).finally(() => {
      activeRequests.current.delete(controller);
      if (activeFileRequest.current === controller) {
        activeFileRequest.current = null;
        if (!controller.signal.aborted) setFileLoading(false);
      }
    });
  };

  return <section className="cp-workspace-browser" aria-labelledby="workspace-files-heading">
    <header><div><span className="cp-kicker">Read only</span><h2 id="workspace-files-heading">Workspace files</h2></div><span>Only cases and knowledge are exposed</span></header>
    <div className="cp-browser-grid">
      <div className="cp-tree-pane" aria-label="Workspace file tree">
        {treeError && <div className="cp-inline-error"><AlertCircle aria-hidden="true" /><span><strong>{treeError.message}</strong><small>{treeError.action}</small></span><button className="cp-icon-button" type="button" aria-label="Retry workspace files" onClick={loadRoot}><RefreshCw aria-hidden="true" /></button></div>}
        {!root && !treeError && <p className="cp-pane-state">Loading workspace files…</p>}
        {root && <ul className="cp-tree-root">{root.entries.map((entry) => <TreeEntry key={entry.path} entry={entry} depth={0} expanded={expanded} childrenByPath={childrenByPath} loadingPaths={loadingPaths} selectedPath={file?.path ?? null} onDirectory={onDirectory} onFile={onFile} />)}</ul>}
      </div>
      <div className="cp-file-pane">
        {!file && !fileError && !fileLoading && <div className="cp-file-empty"><FileText aria-hidden="true" /><strong>Select a text file</strong><span>Preview workspace knowledge or inspect authored cases without exposing private configuration.</span></div>}
        {fileLoading && <p className="cp-pane-state">Loading file…</p>}
        {fileError && <div className="cp-file-empty cp-file-empty--error"><AlertCircle aria-hidden="true" /><strong>{fileError.message}</strong><span>{fileError.action}</span>{requestedFilePath && <button className="button" type="button" onClick={() => onFile(requestedFilePath)}><RefreshCw aria-hidden="true" />Retry file</button>}</div>}
        {file && <>
          <div className="cp-file-toolbar">
            <div className="cp-file-breadcrumb"><span>{file.path.split('/').slice(0, -1).join(' / ')}</span><strong>{file.name}</strong></div>
            <span>{file.lineCount} lines · {formatBytes(file.size)}</span>
          </div>
          {file.presentation === 'markdown' && <div className="cp-file-tabs" role="tablist" aria-label="Markdown presentation"><button type="button" role="tab" aria-selected={fileTab === 'preview'} onClick={() => setFileTab('preview')}>Preview</button><button type="button" role="tab" aria-selected={fileTab === 'code'} onClick={() => setFileTab('code')}>Code</button></div>}
          <div className="cp-file-content">
            {file.presentation === 'markdown' && fileTab === 'preview' ? <article className="cp-markdown"><ReactMarkdown skipHtml>{file.content}</ReactMarkdown></article> : <pre><code>{file.content}</code></pre>}
          </div>
        </>}
      </div>
    </div>
  </section>;
}