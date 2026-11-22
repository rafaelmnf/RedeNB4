import "@mantine/core/styles.css";
import "@mantine/notifications/styles.css";

import { MantineProvider, createTheme } from "@mantine/core";
import { Notifications } from "@mantine/notifications";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { RouterProvider, createBrowserRouter } from "react-router-dom";

import { AoVivoProvider } from "./aoVivo/AoVivoProvider";
import { Layout } from "./componentes/Layout";
import { Alertas } from "./paginas/Alertas";
import { Dashboard } from "./paginas/Dashboard";
import { DetalhePulseira } from "./paginas/DetalhePulseira";
import { Experimentos } from "./paginas/Experimentos";
import { Limites } from "./paginas/Limites";
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
      { path: "/pulseiras/:id", element: <DetalhePulseira /> },
      { path: "/pesquisadores", element: <Pesquisadores /> },
      { path: "/experimentos", element: <Experimentos /> },
      { path: "/alertas", element: <Alertas /> },
      { path: "/limites", element: <Limites /> },
    ],
  },
]);

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <MantineProvider theme={tema} defaultColorScheme="auto">
      <Notifications position="top-right" />
      <QueryClientProvider client={consultas}>
        {/* Uma conexão /ws/ao-vivo para o app inteiro */}
        <AoVivoProvider>
          <RouterProvider router={rotas} />
        </AoVivoProvider>
      </QueryClientProvider>
    </MantineProvider>
  </StrictMode>,
);
