import { HomeShellPage, NewbroShellProvider } from "./NewbroShell";

export default function App() {
  return (
    <NewbroShellProvider>
      <HomeShellPage onNavigate={() => {}} />
    </NewbroShellProvider>
  );
}
