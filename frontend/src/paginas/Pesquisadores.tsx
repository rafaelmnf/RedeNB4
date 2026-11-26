import {
  ActionIcon,
  Alert,
  Badge,
  Button,
  Group,
  Loader,
  Modal,
  Stack,
  Switch,
  Table,
  Text,
  Textarea,
  TextInput,
  Title,
  Tooltip,
} from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import { notifications } from "@mantine/notifications";
import { IconPencil, IconPlus, IconTrash } from "@tabler/icons-react";
import { useState } from "react";

import type { Pesquisador } from "../api/cliente";
import {
  useAtualizarPesquisador,
  useCadastrarPesquisador,
  usePesquisadores,
  useRemoverPesquisador,
} from "../api/pesquisadores";
import { formatarData, formatarDataHora } from "../util/tempo";
import { usePodeEditar } from "../sessao/sessao";

function erro(e: unknown) {
  notifications.show({ color: "red", title: "Erro", message: e instanceof Error ? e.message : String(e) });
}

// Data local (não UTC), para o limite do campo de nascimento.
const HOJE = new Date(Date.now() - new Date().getTimezoneOffset() * 60_000).toISOString().slice(0, 10);

/** Formulário de cadastro (sem `pesquisador`) ou de edição. */
function FormPesquisador({ pesquisador, aoFechar }: { pesquisador?: Pesquisador; aoFechar: () => void }) {
  const [nome, setNome] = useState(pesquisador?.nome ?? "");
  const [email, setEmail] = useState(pesquisador?.email ?? "");
  const [nascimento, setNascimento] = useState(pesquisador?.data_nascimento ?? "");
  const [observacoes, setObservacoes] = useState(pesquisador?.observacoes ?? "");
  const cadastrar = useCadastrarPesquisador();
  const atualizar = useAtualizarPesquisador();

  async function salvar(e: React.FormEvent) {
    e.preventDefault();
    const dados = {
      nome,
      email,
      data_nascimento: nascimento || null,
      observacoes: observacoes || null,
    };
    try {
      if (pesquisador) await atualizar.mutateAsync({ id: pesquisador.id, ...dados });
      else await cadastrar.mutateAsync(dados);
      notifications.show({ color: "green", message: `${nome.trim()} ${pesquisador ? "atualizado(a)" : "cadastrado(a)"}.` });
      aoFechar();
    } catch (e) {
      erro(e);
    }
  }

  return (
    <form onSubmit={salvar}>
      <Stack>
        <TextInput
          label="Nome"
          value={nome}
          maxLength={150}
          required
          onChange={(e) => setNome(e.currentTarget.value)}
          data-autofocus
        />
        <TextInput
          label="E-mail CNPEM"
          type="email"
          placeholder="fulano.silva@cnpem.br"
          value={email}
          maxLength={254}
          required
          onChange={(e) => setEmail(e.currentTarget.value)}
        />
        <TextInput
          label="Data de nascimento (opcional)"
          type="date"
          max={HOJE}
          value={nascimento}
          onChange={(e) => setNascimento(e.currentTarget.value)}
        />
        <Textarea
          label="Observações (opcional)"
          autosize
          minRows={2}
          maxLength={2000}
          value={observacoes}
          onChange={(e) => setObservacoes(e.currentTarget.value)}
        />
        <Group justify="flex-end">
          <Button variant="default" onClick={aoFechar}>
            Cancelar
          </Button>
          <Button type="submit" loading={cadastrar.isPending || atualizar.isPending}>
            {pesquisador ? "Salvar" : "Cadastrar"}
          </Button>
        </Group>
      </Stack>
    </form>
  );
}

export function Pesquisadores() {
  const podeEditar = usePodeEditar();
  const { data, isLoading, error } = usePesquisadores();
  const atualizar = useAtualizarPesquisador();
  const remover = useRemoverPesquisador();
  const [modalAberto, modal] = useDisclosure(false);
  const [editando, setEditando] = useState<Pesquisador | undefined>();
  const [removendo, setRemovendo] = useState<Pesquisador | undefined>();

  function alternarAtivo(p: Pesquisador, ativo: boolean) {
    atualizar.mutate(
      { id: p.id, ativo },
      {
        onError: erro,
        onSuccess: () => {
          if (!ativo && p.atribuicao) {
            notifications.show({ message: `Vínculo de ${p.nome} com ${p.atribuicao.pulseira} encerrado.` });
          }
        },
      },
    );
  }

  async function confirmarRemocao() {
    if (!removendo) return;
    try {
      await remover.mutateAsync(removendo.id);
      notifications.show({ color: "green", message: `${removendo.nome} excluído(a).` });
      setRemovendo(undefined);
    } catch (e) {
      erro(e);
    }
  }

  return (
    <>
      <Group justify="space-between" mb="md">
        <Title order={2}>Pesquisadores</Title>
        {podeEditar && (
          <Button
            leftSection={<IconPlus size={16} />}
            onClick={() => {
              setEditando(undefined);
              modal.open();
            }}
          >
            Cadastrar pesquisador
          </Button>
        )}
      </Group>

      {isLoading && <Loader />}
      {error && <Alert color="red">{error.message}</Alert>}
      {data && data.length === 0 && (
        <Alert color="blue" title="Nenhum pesquisador cadastrado">
          Cadastre as pessoas que vão usar as pulseiras. Depois, vincule cada pulseira a quem está com ela na tela
          Pulseiras.
        </Alert>
      )}

      {data && data.length > 0 && (
        <Table.ScrollContainer minWidth={720}>
          <Table striped highlightOnHover verticalSpacing="sm">
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Nome</Table.Th>
                <Table.Th>E-mail</Table.Th>
                <Table.Th>Nascimento</Table.Th>
                <Table.Th>Pulseira</Table.Th>
                <Table.Th>Ativo</Table.Th>
                <Table.Th />
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {data.map((p) => (
                <Table.Tr key={p.id}>
                  <Table.Td>
                    <Tooltip label={p.observacoes} disabled={!p.observacoes} multiline maw={320}>
                      <span>{p.nome}</span>
                    </Tooltip>
                  </Table.Td>
                  <Table.Td>{p.email}</Table.Td>
                  <Table.Td>{formatarData(p.data_nascimento)}</Table.Td>
                  <Table.Td>
                    {p.atribuicao ? (
                      <Tooltip label={`Desde ${formatarDataHora(p.atribuicao.inicio)}`}>
                        <Badge variant="light">{p.atribuicao.pulseira}</Badge>
                      </Tooltip>
                    ) : (
                      <Text c="dimmed" size="sm">
                        —
                      </Text>
                    )}
                  </Table.Td>
                  <Table.Td>
                    <Switch
                      checked={p.ativo}
                      disabled={!podeEditar}
                      aria-label={p.ativo ? "Desativar" : "Ativar"}
                      onChange={(e) => alternarAtivo(p, e.currentTarget.checked)}
                    />
                  </Table.Td>
                  <Table.Td>
                    <Group gap={4} wrap="nowrap" display={podeEditar ? undefined : "none"}>
                      <ActionIcon
                        variant="subtle"
                        aria-label="Editar"
                        onClick={() => {
                          setEditando(p);
                          modal.open();
                        }}
                      >
                        <IconPencil size={16} />
                      </ActionIcon>
                      <ActionIcon variant="subtle" color="red" aria-label="Excluir" onClick={() => setRemovendo(p)}>
                        <IconTrash size={16} />
                      </ActionIcon>
                    </Group>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      )}

      <Modal
        opened={modalAberto}
        onClose={modal.close}
        title={editando ? "Editar pesquisador" : "Cadastrar pesquisador"}
      >
        <FormPesquisador key={editando?.id ?? "novo"} pesquisador={editando} aoFechar={modal.close} />
      </Modal>

      <Modal opened={!!removendo} onClose={() => setRemovendo(undefined)} title="Excluir pesquisador">
        <Stack>
          <Text>
            Excluir <b>{removendo?.nome}</b>? Só é possível para quem nunca usou pulseira. Quem já tem histórico de BPM
            deve ser desativado.
          </Text>
          <Group justify="flex-end">
            <Button variant="default" onClick={() => setRemovendo(undefined)}>
              Cancelar
            </Button>
            <Button color="red" loading={remover.isPending} onClick={confirmarRemocao}>
              Excluir
            </Button>
          </Group>
        </Stack>
      </Modal>
    </>
  );
}
