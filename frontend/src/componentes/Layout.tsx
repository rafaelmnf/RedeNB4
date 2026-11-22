import {
  ActionIcon,
  AppShell,
  Burger,
  Group,
  NavLink,
  Title,
  Tooltip,
  useComputedColorScheme,
  useMantineColorScheme,
} from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import { IconDeviceWatch, IconFlask, IconLayoutDashboard, IconMoon, IconSun, IconUsers } from "@tabler/icons-react";
import { NavLink as LinkRouter, Outlet, useLocation } from "react-router-dom";

const ITENS = [
  { para: "/", rotulo: "Dashboard", icone: IconLayoutDashboard },
  { para: "/pulseiras", rotulo: "Pulseiras", icone: IconDeviceWatch },
  { para: "/pesquisadores", rotulo: "Pesquisadores", icone: IconUsers },
  { para: "/experimentos", rotulo: "Experimentos", icone: IconFlask },
];

/** Alterna claro/escuro. O Mantine guarda a escolha no localStorage; até o primeiro
 * clique o tema segue o do sistema. */
function BotaoTema() {
  const { setColorScheme } = useMantineColorScheme();
  const escuro = useComputedColorScheme("light") === "dark";
  const rotulo = escuro ? "Usar tema claro" : "Usar tema escuro";
  return (
    <Tooltip label={rotulo}>
      <ActionIcon variant="default" size="lg" aria-label={rotulo} onClick={() => setColorScheme(escuro ? "light" : "dark")}>
        {escuro ? <IconSun size={18} /> : <IconMoon size={18} />}
      </ActionIcon>
    </Tooltip>
  );
}

export function Layout() {
  const [aberto, { toggle, close }] = useDisclosure();
  const { pathname } = useLocation();

  return (
    <AppShell
      header={{ height: 56 }}
      navbar={{ width: 220, breakpoint: "sm", collapsed: { mobile: !aberto } }}
      padding="md"
    >
      <AppShell.Header>
        <Group h="100%" px="md" justify="space-between" wrap="nowrap">
          <Group wrap="nowrap">
            <Burger opened={aberto} onClick={toggle} hiddenFrom="sm" size="sm" />
            <Title order={4}>RedeNB4 · Monitoramento de BPM</Title>
          </Group>
          <BotaoTema />
        </Group>
      </AppShell.Header>
      <AppShell.Navbar p="xs">
        {ITENS.map(({ para, rotulo, icone: Icone }) => (
          <NavLink
            key={para}
            component={LinkRouter}
            to={para}
            label={rotulo}
            leftSection={<Icone size={18} />}
            active={para === "/" ? pathname === "/" : pathname.startsWith(para)}
            onClick={close}
          />
        ))}
      </AppShell.Navbar>
      <AppShell.Main>
        <Outlet />
      </AppShell.Main>
    </AppShell>
  );
}
