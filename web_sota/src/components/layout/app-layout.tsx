import { useCallback, useEffect, useRef, useState } from 'react';
import { Sidebar } from './sidebar';
import { Topbar } from './topbar';
import { useConnection } from '@/store/connection';
import { useZoom } from '@/lib/useZoom';
import { API_BASE } from '@/lib/api';
// import { Toaster } from '@/components/ui/toaster';

const BACKOFF = [1, 2, 4, 8, 16, 30];

interface AppLayoutProps {
    children: React.ReactNode;
}

export function AppLayout({ children }: AppLayoutProps) {
    useZoom();
    const [collapsed, setCollapsed] = useState(false);
    const attemptRef = useRef(0);
    const timerRef = useRef<ReturnType<typeof setTimeout>>(undefined);

    const tick = useCallback(async () => {
        try {
            const r = await fetch(`${API_BASE}/api/v1/health`, { signal: AbortSignal.timeout(5000) });
            if (r.ok) { useConnection.setState({ state: "connected" }); attemptRef.current = 0; }
            else useConnection.setState({ state: "offline", lastError: `HTTP ${r.status}` });
        } catch (e) {
            useConnection.setState({ state: "offline", lastError: (e as Error).message });
        }
        attemptRef.current = Math.min(++attemptRef.current, BACKOFF.length - 1);
        timerRef.current = setTimeout(tick, BACKOFF[attemptRef.current] * 1000);
    }, []);

    useEffect(() => {
        tick();
        (async () => {
            try {
                const { listen } = await import("@tauri-apps/api/event");
                const unlisten = await listen<string>("backend-status", (event) => {
                    if (event.payload === "ready") useConnection.setState({ state: "connected" });
                    else if (event.payload?.startsWith("error:")) useConnection.setState({ state: "error", lastError: event.payload });
                });
                return () => { unlisten(); clearTimeout(timerRef.current); };
            } catch { return () => clearTimeout(timerRef.current); }
        })();
        return () => clearTimeout(timerRef.current);
    }, [tick]);

    // Persist sidebar state
    useEffect(() => {
        const stored = localStorage.getItem('sidebar-collapsed');
        if (stored !== null) setCollapsed(stored === 'true');
    }, []);

    const handleToggle = () => {
        const newState = !collapsed;
        setCollapsed(newState);
        localStorage.setItem('sidebar-collapsed', String(newState));
    };

    return (
        <div className="flex min-h-screen flex-col bg-slate-950 text-slate-50 font-sans selection:bg-emerald-500/30">
            <div className="flex flex-1 overflow-hidden">
                <Sidebar collapsed={collapsed} onToggle={handleToggle} />
                <div className="flex flex-1 flex-col overflow-hidden">
                    <Topbar />
                    <main className="flex-1 overflow-y-auto p-6 scroll-smooth">
                        <div className="mx-auto max-w-7xl animate-in fade-in duration-500">
                            {children}
                        </div>
                    </main>
                </div>
            </div>
            {/* <Toaster /> */}
        </div>
    );
}
