import {
  Navigate,
  Route,
  BrowserRouter as Router,
  Routes,
} from "react-router-dom";
import { AppLayout } from "@/components/layout/app-layout";
import { Actions } from "@/pages/actions";
import { Chat } from "@/pages/chat";
import { Compare } from "@/pages/compare";
import { Dashboard } from "@/pages/dashboard";
import { Help } from "@/pages/help";
import { Inbox } from "@/pages/inbox";
import Logs from "@/pages/logs";
import { Settings } from "@/pages/settings";
import { Skills } from "@/pages/skills";
import { Sync } from "@/pages/sync";
import { Tools } from "@/pages/tools";

function App() {
  return (
    <Router>
      <AppLayout>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/compare" element={<Compare />} />
          <Route path="/sync" element={<Sync />} />
          <Route path="/chat" element={<Chat />} />
          <Route path="/tools" element={<Tools />} />
          <Route path="/actions" element={<Actions />} />
          <Route path="/inbox" element={<Inbox />} />
          <Route path="/skills" element={<Skills />} />
          <Route path="/logs" element={<Logs />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="/help" element={<Help />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AppLayout>
    </Router>
  );
}

export default App;
