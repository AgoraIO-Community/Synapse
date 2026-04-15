import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "@tanstack/react-router";
import { StrictMode, startTransition } from "react";
import ReactDOM from "react-dom/client";
import { getRouter } from "./router";

const queryClient = new QueryClient();
const router = getRouter();

startTransition(() => {
  ReactDOM.createRoot(document.getElementById("app")!).render(
    <StrictMode>
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} />
      </QueryClientProvider>
    </StrictMode>,
  );
});
