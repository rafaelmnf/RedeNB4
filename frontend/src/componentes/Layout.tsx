import { AppShell, Burger, Group, NavLink, Title } from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import { IconDeviceWatch, IconLayoutDashboard } from "@tabler/icons-react";
import { NavLink as LinkRouter, Outlet, useLocation } from "react-router-dom";

const ITENS = [
  { para: "/", rotulo: "Dashboard", icone: IconLayoutDashboard },
  { para: "/pulseiras", rotulo: "Pulseiras", icone: IconDeviceWatch },
];

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
        <Group h="100%" px="md">
          <Burger opened={aberto} onClick={toggle} hiddenFrom="sm" size="sm" />
          <Title order={4}>RedeNB4 · Monitoramento de BPM</Title>
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
