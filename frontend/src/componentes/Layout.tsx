import {
  ActionIcon,
  AppShell,
  Burger,
  Button,
  Group,
  Menu,
  Modal,
  NavLink,
  PasswordInput,
  Stack,
  Text,
  Title,
  Tooltip,
  useComputedColorScheme,
  useMantineColorScheme,
} from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import { notifications } from "@mantine/notifications";
import {
  IconAdjustments,
  IconBell,
  IconChevronDown,
  IconKey,
  IconListSearch,
  IconLogout,
  IconUserShield,
  IconDeviceWatch,
  IconFlask,
  IconLayoutDashboard,
  IconMoon,
  IconSun,
  IconUsers,
} from "@tabler/icons-react";
import { useState } from "react";
import { NavLink as LinkRouter, Outlet, useLocation, useNavigate } from "react-router-dom";

import { useSair, useTrocarSenha, useUsuario } from "../sessao/sessao";
import { BannerAlertas } from "./BannerAlertas";

const ITENS = [
  { para: "/", rotulo: "Dashboard", icone: IconLayoutDashboard },
  { para: "/pulseiras", rotulo: "Pulseiras", icone: IconDeviceWatch },
  { para: "/pesquisadores", rotulo: "Pesquisadores", icone: IconUsers },
  { para: "/experimentos", rotulo: "Experimentos", icone: IconFlask },
  { para: "/alertas", rotulo: "Alertas", icone: IconBell },
  { para: "/limites", rotulo: "Limites", icone: IconAdjustments },
  { para: "/usuarios", rotulo: "Usuários", icone: IconUserShield, soAdmin: true },
  { para: "/auditoria", rotulo: "Auditoria", icone: IconListSearch, soAdmin: true },
];

function FormTrocarSenha({ aoFechar }: { aoFechar: () => void }) {
  const [atual, setAtual] = useState("");
  const [nova, setNova] = useState("");
  const [repetida, setRepetida] = useState("");
  const trocar = useTrocarSenha();
  const diferentes = repetida.length > 0 && nova !== repetida;

  async function salvar(e: React.FormEvent) {
    e.preventDefault();
    if (diferentes) return;
    try {
      await trocar.mutateAsync({ senha_atual: atual, nova_senha: nova });
      notifications.show({ color: "green", message: "Senha trocada. Os outros navegadores foram desconectados." });
      aoFechar();
    } catch (e) {
      notifications.show({ color: "red", title: "Erro", message: e instanceof Error ? e.message : String(e) });
    }
  }

  return (
    <form onSubmit={salvar}>
      <Stack>
        <PasswordInput label="Senha atual" value={atual} onChange={(e) => setAtual(e.currentTarget.value)} required data-autofocus />
        <PasswordInput
          label="Nova senha"
          description="Mínimo de 8 caracteres"
          value={nova}
          onChange={(e) => setNova(e.currentTarget.value)}
          minLength={8}
          required
        />
        <PasswordInput
          label="Repita a nova senha"
          value={repetida}
          onChange={(e) => setRepetida(e.currentTarget.value)}
          error={diferentes ? "As senhas não conferem" : null}
          required
        />
        <Group justify="flex-end">
          <Button variant="default" onClick={aoFechar}>
            Cancelar
          </Button>
          <Button type="submit" loading={trocar.isPending} disabled={diferentes}>
            Trocar senha
          </Button>
        </Group>
      </Stack>
    </form>
  );
}

/** Nome e papel de quem está logado, com "Trocar senha" e "Sair". */
function MenuUsuario() {
  const usuario = useUsuario();
  const sair = useSair();
  const navegar = useNavigate();
  const [trocando, setTrocando] = useState(false);
  if (!usuario) return null;
  return (
    <>
      <Menu position="bottom-end">
        <Menu.Target>
          <Button variant="subtle" color="gray" rightSection={<IconChevronDown size={14} />}>
            <Stack gap={0} align="flex-end">
              <Text size="sm" fw={500} lh={1.2}>
                {usuario.nome}
              </Text>
              <Text size="xs" c="dimmed" lh={1.2}>
                {usuario.papel}
              </Text>
            </Stack>
          </Button>
        </Menu.Target>
        <Menu.Dropdown>
          <Menu.Label>{usuario.email}</Menu.Label>
          <Menu.Item leftSection={<IconKey size={14} />} onClick={() => setTrocando(true)}>
            Trocar senha
          </Menu.Item>
          <Menu.Item
            leftSection={<IconLogout size={14} />}
            color="red"
            onClick={() => sair.mutate(undefined, { onSettled: () => navegar("/login", { replace: true }) })}
          >
            Sair
          </Menu.Item>
        </Menu.Dropdown>
      </Menu>
      <Modal opened={trocando} onClose={() => setTrocando(false)} title="Trocar senha">
        {trocando && <FormTrocarSenha aoFechar={() => setTrocando(false)} />}
      </Modal>
    </>
  );
}

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
  const admin = useUsuario()?.papel === "admin";

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
          <Group gap="xs" wrap="nowrap">
            <MenuUsuario />
            <BotaoTema />
          </Group>
        </Group>
      </AppShell.Header>
      <AppShell.Navbar p="xs">
        {ITENS.filter((i) => admin || !i.soAdmin).map(({ para, rotulo, icone: Icone }) => (
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
        <BannerAlertas />
        <Outlet />
      </AppShell.Main>
    </AppShell>
  );
}
