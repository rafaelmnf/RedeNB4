import "@mantine/core/styles.css";
import "@mantine/notifications/styles.css";

import { MantineProvider, createTheme } from "@mantine/core";
import { Notifications } from "@mantine/notifications";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { RouterProvider, createBrowserRouter } from "react-router-dom";

import { Layout } from "./componentes/Layout";
import { Dashboard } from "./paginas/Dashboard";
import { Pesquisadores } from "./paginas/Pesquisadores";
import { Pulseiras } from "./paginas/Pulseiras";

const tema = createTheme({ primaryColor: "teal" });

const consultas = new QueryClient({
  defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } },
});

const rotas = createBrowserRouter([
  {
    element: <Layout />,
    children: [
      { path: "/", element: <Dashboard /> },
      { path: "/pulseiras", element: <Pulseiras /> },
      { path: "/pesquisadores", element: <Pesquisadores /> },
    ],
  },
]);

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <MantineProvider theme={tema} defaultColorScheme="auto">
      <Notifications position="top-right" />
      <QueryClientProvider client={consultas}>
        <RouterProvider router={rotas} />
      </QueryClientProvider>
    </MantineProvider>
  </StrictMode>,
);
