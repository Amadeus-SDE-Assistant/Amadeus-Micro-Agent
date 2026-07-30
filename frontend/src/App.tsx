import { ChatWindow } from "./components/ChatWindow";
import { UploadPanel } from "./components/UploadPanel";

export default function App() {
  return (
    <div className="shell">
      <header className="masthead">
        <h1 className="wordmark">Amadeus</h1>
        <span className="tagline">your job-search companion</span>
      </header>
      <ChatWindow />
      <UploadPanel />
    </div>
  );
}
