import {
  ActionIcon,
  Alert,
  Badge,
  Button,
  Card,
  Group,
  Loader,
  Modal,
  MultiSelect,
  SegmentedControl,
  Select,
  SimpleGrid,
  Stack,
  Table,
  Text,
  Textarea,
  TextInput,
  Title,
  Tooltip,
} from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import { notifications } from "@mantine/notifications";
import { IconBuilding, IconFlagCheck, IconPencil, IconPlus, IconTrash } from "@tabler/icons-react";
import { useMemo, useState } from "react";

import type { Experimento, Laboratorio, SituacaoExperimento } from "../api/cliente";
import {
  useAtualizarExperimento,
  useCriarExperimento,
  useEncerrarExperimento,
  useExperimentos,
  useRemoverExperimento,
} from "../api/experimentos";
import {
  useAtualizarLaboratorio,
  useCadastrarLaboratorio,
  useLaboratorios,
  useRemoverLaboratorio,
} from "../api/laboratorios";
import { usePesquisadores } from "../api/pesquisadores";
import { deInputLocal, formatarDataHora, paraInputLocal } from "../util/tempo";
import { usePodeEditar } from "../sessao/sessao";

function erro(e: unknown) {
  notifications.show({ color: "red", title: "Erro", message: e instanceof Error ? e.message : String(e) });
}

const SITUACOES: Record<SituacaoExperimento, { rotulo: string; cor: string }> = {
  agendado: { rotulo: "Agendado", cor: "blue" },
  em_andamento: { rotulo: "Em andamento", cor: "teal" },
  encerrado: { rotulo: "Encerrado", cor: "gray" },
};

// ------------------------------------------------------------------ laboratórios
function GerenciarLaboratorios() {
  const podeEditar = usePodeEditar();
  const { data, isLoading } = useLaboratorios();
  const cadastrar = useCadastrarLaboratorio();
  const atualizar = useAtualizarLaboratorio();
  const remover = useRemoverLaboratorio();
  const [nome, setNome] = useState("");
  const [descricao, setDescricao] = useState("");
  const [editando, setEditando] = useState<Laboratorio | undefined>();

  function limpar() {
    setNome("");
    setDescricao("");
    setEditando(undefined);
  }

  async function salvar(e: React.FormEvent) {
    e.preventDefault();
    try {
      const dados = { nome, descricao: descricao || null };
      if (editando) await atualizar.mutateAsync({ id: editando.id, ...dados });
      else await cadastrar.mutateAsync(dados);
      limpar();
    } catch (e) {
      erro(e);
    }
  }

  return (
    <Stack>
      <form onSubmit={salvar} style={{ display: podeEditar ? undefined : "none" }}>
        <Stack gap="xs">
          <TextInput
            label={editando ? `Renomear ${editando.nome}` : "Novo laboratório"}
            placeholder="Laboratório de Biologia"
            value={nome}
            maxLength={150}
            required
            onChange={(e) => setNome(e.currentTarget.value)}
            data-autofocus
          />
          <TextInput
            placeholder="Descrição (opcional)"
            value={descricao}
            maxLength={2000}
            onChange={(e) => setDescricao(e.currentTarget.value)}
          />
          <Group justify="flex-end">
            {editando && (
              <Button variant="default" onClick={limpar}>
                Cancelar edição
              </Button>
            )}
            <Button type="submit" loading={cadastrar.isPending || atualizar.isPending}>
              {editando ? "Salvar" : "Adicionar"}
            </Button>
          </Group>
        </Stack>
      </form>

      {isLoading && <Loader />}
      {data && data.length > 0 && (
        <Table striped>
          <Table.Tbody>
            {data.map((lab) => (
              <Table.Tr key={lab.id}>
                <Table.Td>
                  <Text fw={500}>{lab.nome}</Text>
                  {lab.descricao && (
                    <Text size="xs" c="dimmed">
                      {lab.descricao}
                    </Text>
                  )}
                </Table.Td>
                <Table.Td>
                  <Text size="sm" c="dimmed">
                    {lab.total_experimentos} experimento(s)
                  </Text>
                </Table.Td>
                <Table.Td>
                  <Group gap={4} wrap="nowrap" justify="flex-end" display={podeEditar ? undefined : "none"}>
                    <ActionIcon
                      variant="subtle"
                      aria-label="Editar"
                      onClick={() => {
                        setEditando(lab);
                        setNome(lab.nome);
                        setDescricao(lab.descricao ?? "");
                      }}
                    >
                      <IconPencil size={16} />
                    </ActionIcon>
                    <Tooltip label={lab.total_experimentos ? "Tem experimentos: não pode ser excluído" : "Excluir"}>
                      <ActionIcon
                        variant="subtle"
                        color="red"
                        aria-label="Excluir"
                        disabled={lab.total_experimentos > 0}
                        onClick={() => remover.mutate(lab.id, { onError: erro })}
                      >
                        <IconTrash size={16} />
                      </ActionIcon>
                    </Tooltip>
                  </Group>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}
    </Stack>
  );
}

// ------------------------------------------------------------------ experimento
function FormExperimento({
  experimento,
  laboratorioPadrao,
  aoFechar,
}: {
  experimento?: Experimento;
  laboratorioPadrao?: number;
  aoFechar: () => void;
}) {
  const { data: laboratorios } = useLaboratorios();
  const { data: pesquisadores } = usePesquisadores();
  const criar = useCriarExperimento();
  const atualizar = useAtualizarExperimento();

  const [laboratorio, setLaboratorio] = useState<string | null>(
    experimento ? String(experimento.laboratorio_id) : laboratorioPadrao ? String(laboratorioPadrao) : null,
  );
  const [nome, setNome] = useState(experimento?.nome ?? "");
  const [descricao, setDescricao] = useState(experimento?.descricao ?? "");
  const [inicio, setInicio] = useState(paraInputLocal(experimento?.inicio ?? new Date().toISOString()));
  const [fim, setFim] = useState(paraInputLocal(experimento?.fim));
  const [participantes, setParticipantes] = useState<string[]>(
    experimento?.participantes.map((p) => String(p.id)) ?? [],
  );

  // Ativos podem ser adicionados; quem já participa continua aparecendo mesmo desativado.
  const opcoes = useMemo(
    () =>
      (pesquisadores ?? [])
        .filter((p) => p.ativo || participantes.includes(String(p.id)))
        .map((p) => ({ value: String(p.id), label: p.ativo ? p.nome : `${p.nome} (desativado)` })),
    [pesquisadores, participantes],
  );
  const fimInvalido = !!fim && !!inicio && fim <= inicio;

  async function salvar(e: React.FormEvent) {
    e.preventDefault();
    if (!laboratorio || fimInvalido) return;
    const dados = {
      laboratorio_id: Number(laboratorio),
      nome,
      descricao: descricao || null,
      inicio: deInputLocal(inicio)!,
      fim: deInputLocal(fim),
      participantes: participantes.map(Number),
    };
    try {
      if (experimento) await atualizar.mutateAsync({ id: experimento.id, ...dados });
      else await criar.mutateAsync(dados);
      notifications.show({ color: "green", message: `Experimento ${nome.trim()} salvo.` });
      aoFechar();
    } catch (e) {
      erro(e);
    }
  }

  return (
    <form onSubmit={salvar}>
      <Stack>
        <Select
          label="Laboratório"
          data={(laboratorios ?? []).map((l) => ({ value: String(l.id), label: l.nome }))}
          value={laboratorio}
          onChange={setLaboratorio}
          required
          searchable
        />
        <TextInput
          label="Nome do experimento"
          value={nome}
          maxLength={200}
          required
          onChange={(e) => setNome(e.currentTarget.value)}
          data-autofocus
        />
        <Textarea
          label="Descrição"
          autosize
          minRows={3}
          maxLength={5000}
          value={descricao}
          onChange={(e) => setDescricao(e.currentTarget.value)}
        />
        <Group grow align="flex-start">
          <TextInput
            label="Início"
            type="datetime-local"
            value={inicio}
            required
            onChange={(e) => setInicio(e.currentTarget.value)}
          />
          <TextInput
            label="Fim (opcional)"
            type="datetime-local"
            value={fim}
            min={inicio}
            onChange={(e) => setFim(e.currentTarget.value)}
            error={fimInvalido ? "O fim deve ser depois do início" : null}
          />
        </Group>
        <MultiSelect
          label="Pessoas envolvidas"
          placeholder={participantes.length ? undefined : "Escolha os pesquisadores"}
          data={opcoes}
          value={participantes}
          onChange={setParticipantes}
          searchable
          clearable
          nothingFoundMessage="Ninguém encontrado"
        />
        <Group justify="flex-end">
          <Button variant="default" onClick={aoFechar}>
            Cancelar
          </Button>
          <Button type="submit" loading={criar.isPending || atualizar.isPending} disabled={fimInvalido}>
            {experimento ? "Salvar" : "Criar experimento"}
          </Button>
        </Group>
      </Stack>
    </form>
  );
}

function CardExperimento({
  e,
  aoEditar,
  aoExcluir,
}: {
  e: Experimento;
  aoEditar: () => void;
  aoExcluir: () => void;
}) {
  const encerrar = useEncerrarExperimento();
  const podeEditar = usePodeEditar();
  const sit = SITUACOES[e.situacao];
  return (
    <Card withBorder padding="md" radius="md">
      <Group justify="space-between" wrap="nowrap" align="flex-start">
        <Stack gap={2}>
          <Text fw={600}>{e.nome}</Text>
          <Text size="xs" c="dimmed">
            {formatarDataHora(e.inicio)} → {e.fim ? formatarDataHora(e.fim) : "sem fim definido"}
          </Text>
        </Stack>
        <Badge color={sit.cor} variant="light" style={{ flexShrink: 0 }}>
          {sit.rotulo}
        </Badge>
      </Group>
      {e.descricao && (
        <Text size="sm" mt="sm" style={{ whiteSpace: "pre-line" }} lineClamp={4}>
          {e.descricao}
        </Text>
      )}
      <Group gap={6} mt="sm">
        {e.participantes.length === 0 ? (
          <Text size="sm" c="dimmed">
            Nenhuma pessoa envolvida
          </Text>
        ) : (
          e.participantes.map((p) => (
            <Badge key={p.id} variant="outline" color={p.ativo ? "teal" : "gray"} tt="none">
              {p.nome}
            </Badge>
          ))
        )}
      </Group>
      <Group gap={4} mt="sm" justify="flex-end" display={podeEditar ? undefined : "none"}>
        {e.situacao === "em_andamento" && (
          <Tooltip label="Encerrar agora">
            <ActionIcon
              variant="subtle"
              color="orange"
              aria-label="Encerrar"
              loading={encerrar.isPending}
              onClick={() => encerrar.mutate(e.id, { onError: erro })}
            >
              <IconFlagCheck size={16} />
            </ActionIcon>
          </Tooltip>
        )}
        <ActionIcon variant="subtle" aria-label="Editar" onClick={aoEditar}>
          <IconPencil size={16} />
        </ActionIcon>
        <ActionIcon variant="subtle" color="red" aria-label="Excluir" onClick={aoExcluir}>
          <IconTrash size={16} />
        </ActionIcon>
      </Group>
    </Card>
  );
}

// ------------------------------------------------------------------ página
export function Experimentos() {
  const podeEditar = usePodeEditar();
  const { data: laboratorios, isLoading: carregandoLabs } = useLaboratorios();
  const [filtroLab, setFiltroLab] = useState<string | null>(null);
  const [filtroSit, setFiltroSit] = useState<string>("todos");
  const { data, isLoading, error } = useExperimentos({
    laboratorio_id: filtroLab ? Number(filtroLab) : undefined,
    situacao: filtroSit === "todos" ? undefined : (filtroSit as SituacaoExperimento),
  });
  const remover = useRemoverExperimento();
  const [labsAberto, labs] = useDisclosure(false);
  const [formAberto, form] = useDisclosure(false);
  const [editando, setEditando] = useState<Experimento | undefined>();
  const [excluindo, setExcluindo] = useState<Experimento | undefined>();

  const grupos = useMemo(() => {
    const porLab = new Map<string, Experimento[]>();
    for (const e of data ?? []) porLab.set(e.laboratorio, [...(porLab.get(e.laboratorio) ?? []), e]);
    return [...porLab.entries()].sort(([a], [b]) => a.localeCompare(b, "pt-BR"));
  }, [data]);

  async function confirmarExclusao() {
    if (!excluindo) return;
    try {
      await remover.mutateAsync(excluindo.id);
      notifications.show({ message: `Experimento ${excluindo.nome} excluído.` });
      setExcluindo(undefined);
    } catch (e) {
      erro(e);
    }
  }

  const semLaboratorios = !carregandoLabs && (laboratorios ?? []).length === 0;

  return (
    <>
      <Group justify="space-between" mb="md">
        <Title order={2}>Experimentos</Title>
        <Group gap="xs">
          <Button variant="default" leftSection={<IconBuilding size={16} />} onClick={labs.open}>
            Laboratórios
          </Button>
          <Button
            leftSection={<IconPlus size={16} />}
            display={podeEditar ? undefined : "none"}
            disabled={semLaboratorios}
            onClick={() => {
              setEditando(undefined);
              form.open();
            }}
          >
            Novo experimento
          </Button>
        </Group>
      </Group>

      {semLaboratorios ? (
        <Alert color="blue" title="Nenhum laboratório cadastrado">
          Cadastre o primeiro laboratório no botão <b>Laboratórios</b>. Depois, crie os experimentos de cada um.
        </Alert>
      ) : (
        <Group mb="md" gap="sm">
          <Select
            placeholder="Todos os laboratórios"
            data={(laboratorios ?? []).map((l) => ({ value: String(l.id), label: l.nome }))}
            value={filtroLab}
            onChange={setFiltroLab}
            clearable
            w={260}
          />
          <SegmentedControl
            value={filtroSit}
            onChange={setFiltroSit}
            data={[
              { value: "todos", label: "Todos" },
              { value: "em_andamento", label: "Em andamento" },
              { value: "agendado", label: "Agendados" },
              { value: "encerrado", label: "Encerrados" },
            ]}
          />
        </Group>
      )}

      {isLoading && <Loader />}
      {error && <Alert color="red">{error.message}</Alert>}
      {data && data.length === 0 && !semLaboratorios && (
        <Text c="dimmed">Nenhum experimento encontrado com esses filtros.</Text>
      )}

      <Stack gap="xl">
        {grupos.map(([lab, experimentos]) => (
          <div key={lab}>
            <Title order={4} mb="sm">
              {lab}
            </Title>
            <SimpleGrid cols={{ base: 1, md: 2, xl: 3 }}>
              {experimentos.map((e) => (
                <CardExperimento
                  key={e.id}
                  e={e}
                  aoEditar={() => {
                    setEditando(e);
                    form.open();
                  }}
                  aoExcluir={() => setExcluindo(e)}
                />
              ))}
            </SimpleGrid>
          </div>
        ))}
      </Stack>

      <Modal opened={labsAberto} onClose={labs.close} title="Laboratórios" size="lg">
        <GerenciarLaboratorios />
      </Modal>

      <Modal
        opened={formAberto}
        onClose={form.close}
        title={editando ? "Editar experimento" : "Novo experimento"}
        size="lg"
      >
        <FormExperimento
          key={editando?.id ?? "novo"}
          experimento={editando}
          laboratorioPadrao={filtroLab ? Number(filtroLab) : undefined}
          aoFechar={form.close}
        />
      </Modal>

      <Modal opened={!!excluindo} onClose={() => setExcluindo(undefined)} title="Excluir experimento">
        <Stack>
          <Text>
            Excluir <b>{excluindo?.nome}</b>? A lista de participantes também é apagada. Os pesquisadores e as leituras
            de BPM não são afetados.
          </Text>
          <Group justify="flex-end">
            <Button variant="default" onClick={() => setExcluindo(undefined)}>
              Cancelar
            </Button>
            <Button color="red" loading={remover.isPending} onClick={confirmarExclusao}>
              Excluir
            </Button>
          </Group>
        </Stack>
      </Modal>
    </>
  );
}
