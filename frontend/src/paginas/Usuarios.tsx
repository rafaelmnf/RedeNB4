import {
  ActionIcon,
  Alert,
  Badge,
  Button,
  Group,
  Loader,
  Menu,
  Modal,
  PasswordInput,
  Select,
  Stack,
  Switch,
  Table,
  Text,
  TextInput,
  Title,
} from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { IconDots, IconKey, IconLogout, IconPencil, IconPlus } from "@tabler/icons-react";
import { useState } from "react";

import type { Usuario } from "../api/cliente";
import {
  useAtualizarUsuario,
  useCriarUsuario,
  useEncerrarSessoes,
  useRedefinirSenha,
  useUsuarios,
} from "../api/usuarios";
import { useUsuario } from "../sessao/sessao";
import { formatarDataHora } from "../util/tempo";

function erro(e: unknown) {
  notifications.show({ color: "red", title: "Erro", message: e instanceof Error ? e.message : String(e) });
}

const PAPEIS = [
  { value: "leitor", label: "Leitor (vê tudo e reconhece alertas)" },
  { value: "admin", label: "Admin (edita tudo)" },
];

/** Cadastro (sem `usuario`) ou edição de nome e papel. */
function FormUsuario({ usuario, aoFechar }: { usuario?: Usuario; aoFechar: () => void }) {
  const [email, setEmail] = useState(usuario?.email ?? "");
  const [nome, setNome] = useState(usuario?.nome ?? "");
  const [papel, setPapel] = useState<string>(usuario?.papel ?? "leitor");
  const [senha, setSenha] = useState("");
  const criar = useCriarUsuario();
  const atualizar = useAtualizarUsuario();

  async function salvar(e: React.FormEvent) {
    e.preventDefault();
    try {
      if (usuario) await atualizar.mutateAsync({ id: usuario.id, nome, papel: papel as Usuario["papel"] });
      else await criar.mutateAsync({ email, nome, papel: papel as Usuario["papel"], senha });
      notifications.show({ color: "green", message: `${nome.trim()} salvo.` });
      aoFechar();
    } catch (e) {
      erro(e);
    }
  }

  return (
    <form onSubmit={salvar}>
      <Stack>
        <TextInput
          label="E-mail CNPEM (login)"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.currentTarget.value)}
          disabled={!!usuario}
          required
          data-autofocus={!usuario || undefined}
        />
        <TextInput
          label="Nome"
          value={nome}
          onChange={(e) => setNome(e.currentTarget.value)}
          required
          data-autofocus={!!usuario || undefined}
        />
        <Select label="Papel" data={PAPEIS} value={papel} onChange={(v) => v && setPapel(v)} allowDeselect={false} />
        {!usuario && (
          <PasswordInput
            label="Senha inicial"
            description="Mínimo de 8 caracteres. A pessoa pode trocar depois em 'Trocar senha'."
            value={senha}
            onChange={(e) => setSenha(e.currentTarget.value)}
            minLength={8}
            required
          />
        )}
        <Group justify="flex-end">
          <Button variant="default" onClick={aoFechar}>
            Cancelar
          </Button>
          <Button type="submit" loading={criar.isPending || atualizar.isPending}>
            {usuario ? "Salvar" : "Criar usuário"}
          </Button>
        </Group>
      </Stack>
    </form>
  );
}

function FormSenha({ usuario, aoFechar }: { usuario: Usuario; aoFechar: () => void }) {
  const [senha, setSenha] = useState("");
  const redefinir = useRedefinirSenha();
  async function salvar(e: React.FormEvent) {
    e.preventDefault();
    try {
      await redefinir.mutateAsync({ id: usuario.id, senha });
      notifications.show({ color: "green", message: `Senha de ${usuario.nome} redefinida. Ela precisa entrar de novo.` });
      aoFechar();
    } catch (e) {
      erro(e);
    }
  }
  return (
    <form onSubmit={salvar}>
      <Stack>
        <PasswordInput
          label={`Nova senha de ${usuario.nome}`}
          description="Mínimo de 8 caracteres. As sessões abertas dessa pessoa são encerradas."
          value={senha}
          onChange={(e) => setSenha(e.currentTarget.value)}
          minLength={8}
          required
          data-autofocus
        />
        <Group justify="flex-end">
          <Button variant="default" onClick={aoFechar}>
            Cancelar
          </Button>
          <Button type="submit" loading={redefinir.isPending}>
            Redefinir senha
          </Button>
        </Group>
      </Stack>
    </form>
  );
}

export function Usuarios() {
  const { data, isLoading, error } = useUsuarios();
  const eu = useUsuario();
  const atualizar = useAtualizarUsuario();
  const encerrar = useEncerrarSessoes();
  const [editando, setEditando] = useState<Usuario | "novo" | undefined>();
  const [senhaDe, setSenhaDe] = useState<Usuario | undefined>();

  return (
    <>
      <Group justify="space-between" mb="md">
        <Title order={2}>Usuários</Title>
        <Button leftSection={<IconPlus size={16} />} onClick={() => setEditando("novo")}>
          Criar usuário
        </Button>
      </Group>
      <Text size="sm" c="dimmed" mb="md">
        A sessão não expira: depois de entrar, a pessoa fica logada até clicar em “Sair”. Para cortar o acesso de
        alguém, desative o usuário, redefina a senha ou use “Sair de todos os dispositivos”.
      </Text>

      {isLoading && <Loader />}
      {error && <Alert color="red">{error.message}</Alert>}
      {data && (
        <Table.ScrollContainer minWidth={760}>
          <Table striped highlightOnHover verticalSpacing="sm">
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Nome</Table.Th>
                <Table.Th>E-mail</Table.Th>
                <Table.Th>Papel</Table.Th>
                <Table.Th>Último login</Table.Th>
                <Table.Th>Ativo</Table.Th>
                <Table.Th />
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {data.map((u) => (
                <Table.Tr key={u.id}>
                  <Table.Td>
                    {u.nome}
                    {u.id === eu?.id && (
                      <Text span size="xs" c="dimmed">
                        {" "}
                        (você)
                      </Text>
                    )}
                  </Table.Td>
                  <Table.Td>{u.email}</Table.Td>
                  <Table.Td>
                    <Badge color={u.papel === "admin" ? "teal" : "gray"} variant="light">
                      {u.papel}
                    </Badge>
                  </Table.Td>
                  <Table.Td>{formatarDataHora(u.ultimo_login)}</Table.Td>
                  <Table.Td>
                    <Switch
                      checked={u.ativo}
                      disabled={u.id === eu?.id}
                      aria-label={u.ativo ? "Desativar" : "Ativar"}
                      onChange={(e) => atualizar.mutate({ id: u.id, ativo: e.currentTarget.checked }, { onError: erro })}
                    />
                  </Table.Td>
                  <Table.Td>
                    <Group gap={4} wrap="nowrap">
                      <ActionIcon variant="subtle" aria-label="Editar" onClick={() => setEditando(u)}>
                        <IconPencil size={16} />
                      </ActionIcon>
                      <Menu position="bottom-end">
                        <Menu.Target>
                          <ActionIcon variant="subtle" color="gray" aria-label="Mais ações">
                            <IconDots size={16} />
                          </ActionIcon>
                        </Menu.Target>
                        <Menu.Dropdown>
                          <Menu.Item leftSection={<IconKey size={14} />} onClick={() => setSenhaDe(u)}>
                            Redefinir senha
                          </Menu.Item>
                          <Menu.Item
                            leftSection={<IconLogout size={14} />}
                            disabled={u.id === eu?.id}
                            onClick={() =>
                              encerrar.mutate(u.id, {
                                onError: erro,
                                onSuccess: () =>
                                  notifications.show({ message: `${u.nome} foi desconectado(a) de todos os navegadores.` }),
                              })
                            }
                          >
                            Sair de todos os dispositivos
                          </Menu.Item>
                        </Menu.Dropdown>
                      </Menu>
                    </Group>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      )}

      <Modal
        opened={!!editando}
        onClose={() => setEditando(undefined)}
        title={editando === "novo" ? "Criar usuário" : "Editar usuário"}
      >
        {editando && (
          <FormUsuario
            key={editando === "novo" ? "novo" : editando.id}
            usuario={editando === "novo" ? undefined : editando}
            aoFechar={() => setEditando(undefined)}
          />
        )}
      </Modal>
      <Modal opened={!!senhaDe} onClose={() => setSenhaDe(undefined)} title="Redefinir senha">
        {senhaDe && <FormSenha usuario={senhaDe} aoFechar={() => setSenhaDe(undefined)} />}
      </Modal>
    </>
  );
}
