import {
  ActionIcon,
  Alert,
  Anchor,
  Badge,
  Button,
  Code,
  Group,
  Loader,
  Modal,
  Select,
  Stack,
  Switch,
  Table,
  Text,
  TextInput,
  Title,
  Tooltip,
} from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import { notifications } from "@mantine/notifications";
import { IconHistory, IconPencil, IconPlus, IconTrash, IconUserMinus, IconUserPlus } from "@tabler/icons-react";
import { useState } from "react";
import { Link } from "react-router-dom";

import { useAgora, useCartoesPorId } from "../aoVivo/AoVivoProvider";
import { useDesvincular, useVincular } from "../api/atribuicoes";
import type { Cartao, Pulseira, StatusPulseira } from "../api/cliente";
import { usePesquisadores } from "../api/pesquisadores";
import {
  useAtualizarPulseira,
  useCadastrarPulseira,
  usePulseiras,
  useRemoverPulseira,
} from "../api/pulseiras";
import { HistoricoVinculos } from "../componentes/HistoricoVinculos";
import { normalizarMac } from "../util/mac";
import { formatarDataHora, haQuantoTempo } from "../util/tempo";
import { usePodeEditar } from "../sessao/sessao";

function erro(e: unknown) {
  notifications.show({ color: "red", title: "Erro", message: e instanceof Error ? e.message : String(e) });
}

/** Status ao vivo (WebSocket) quando a pulseira está ativa; senão, o da última consulta. */
type StatusLinha = Pick<Cartao, "online" | "fora_do_braco" | "ultimo_contato" | "ultimo_bpm" | "rssi">;

function BadgeStatus({ p, st }: { p: Pulseira; st?: StatusLinha | StatusPulseira | null }) {
  if (!p.ativa) return <Badge color="gray">desativada</Badge>;
  if (!st?.ultimo_contato) return <Badge color="gray" variant="light">sem dados</Badge>;
  if (!st.online) return <Badge color="orange" variant="light">sem sinal</Badge>;
  if (st.fora_do_braco) return <Badge color="yellow">fora do braço</Badge>;
  return <Badge color="green">online</Badge>;
}

/** Formulário de cadastro (sem `pulseira`) ou de edição do apelido. */
function FormPulseira({ pulseira, aoFechar }: { pulseira?: Pulseira; aoFechar: () => void }) {
  const [mac, setMac] = useState(pulseira?.mac ?? "");
  const [apelido, setApelido] = useState(pulseira?.apelido ?? "");
  const [tocado, setTocado] = useState(false);
  const cadastrar = useCadastrarPulseira();
  const atualizar = useAtualizarPulseira();
  const macNormalizado = normalizarMac(mac);
  const salvando = cadastrar.isPending || atualizar.isPending;

  async function salvar(e: React.FormEvent) {
    e.preventDefault();
    setTocado(true);
    try {
      if (pulseira) {
        await atualizar.mutateAsync({ id: pulseira.id, apelido: apelido || null });
      } else {
        if (!macNormalizado) return;
        await cadastrar.mutateAsync({ mac: macNormalizado, apelido: apelido || null });
        notifications.show({
          color: "green",
          message: `Pulseira ${macNormalizado} cadastrada. O servidor já passa a aceitar os dados dela.`,
        });
      }
      aoFechar();
    } catch (e) {
      erro(e);
    }
  }

  return (
    <form onSubmit={salvar}>
      <Stack>
        <TextInput
          label="MAC address"
          placeholder="A0:9E:1A:12:34:56"
          value={mac}
          onChange={(e) => setMac(e.currentTarget.value)}
          onBlur={() => setTocado(true)}
          disabled={!!pulseira}
          required
          error={tocado && !pulseira && !macNormalizado ? "Formato inválido (ex.: AA:BB:CC:DD:EE:FF)" : null}
          description={
            !pulseira && macNormalizado && macNormalizado !== mac ? `Será salvo como ${macNormalizado}` : undefined
          }
          data-autofocus={!pulseira || undefined}
        />
        <TextInput
          label="Apelido (opcional)"
          placeholder="Pulseira 03"
          value={apelido}
          maxLength={100}
          onChange={(e) => setApelido(e.currentTarget.value)}
          data-autofocus={!!pulseira || undefined}
        />
        <Group justify="flex-end">
          <Button variant="default" onClick={aoFechar}>
            Cancelar
          </Button>
          <Button type="submit" loading={salvando}>
            {pulseira ? "Salvar" : "Cadastrar"}
          </Button>
        </Group>
      </Stack>
    </form>
  );
}

/** Escolhe quem vai usar a pulseira: só pesquisadores ativos e sem pulseira. */
function FormVincular({ pulseira, aoFechar }: { pulseira: Pulseira; aoFechar: () => void }) {
  const { data: pesquisadores, isLoading } = usePesquisadores();
  const vincular = useVincular();
  const [escolhido, setEscolhido] = useState<string | null>(null);
  const livres = (pesquisadores ?? []).filter((p) => p.ativo && !p.atribuicao);

  async function salvar(e: React.FormEvent) {
    e.preventDefault();
    if (!escolhido) return;
    try {
      const a = await vincular.mutateAsync({ pulseira_id: pulseira.id, pesquisador_id: Number(escolhido) });
      notifications.show({ color: "green", message: `${a.pulseira} agora está com ${a.pesquisador}.` });
      aoFechar();
    } catch (e) {
      erro(e);
    }
  }

  if (isLoading) return <Loader />;
  if (livres.length === 0) {
    return (
      <Alert color="blue" title="Ninguém disponível">
        Todos os pesquisadores ativos já estão com uma pulseira, ou não há nenhum cadastrado.{" "}
        <Link to="/pesquisadores">Cadastrar pesquisador</Link>
      </Alert>
    );
  }
  return (
    <form onSubmit={salvar}>
      <Stack>
        <Select
          label="Quem vai usar a pulseira"
          placeholder="Escolha o pesquisador"
          data={livres.map((p) => ({ value: String(p.id), label: `${p.nome} (${p.email})` }))}
          value={escolhido}
          onChange={setEscolhido}
          searchable
          nothingFoundMessage="Ninguém encontrado"
          required
          data-autofocus
        />
        <Text size="sm" c="dimmed">
          O vínculo começa agora. As leituras de BPM passam a ser registradas para essa pessoa até você desvincular.
        </Text>
        <Group justify="flex-end">
          <Button variant="default" onClick={aoFechar}>
            Cancelar
          </Button>
          <Button type="submit" loading={vincular.isPending} disabled={!escolhido}>
            Vincular
          </Button>
        </Group>
      </Stack>
    </form>
  );
}

export function Pulseiras() {
  const podeEditar = usePodeEditar();
  const { data, isLoading, error } = usePulseiras();
  const aoVivo = useCartoesPorId();
  useAgora(); // "há X s" atualiza sozinho
  const atualizar = useAtualizarPulseira();
  const remover = useRemoverPulseira();
  const [modalAberto, modal] = useDisclosure(false);
  const [editando, setEditando] = useState<Pulseira | undefined>();
  const [removendo, setRemovendo] = useState<Pulseira | undefined>();
  const [vinculando, setVinculando] = useState<Pulseira | undefined>();
  const [desvinculando, setDesvinculando] = useState<Pulseira | undefined>();
  const [historico, setHistorico] = useState<Pulseira | undefined>();
  const desvincular = useDesvincular();

  async function confirmarDesvinculo() {
    if (!desvinculando?.atribuicao) return;
    try {
      await desvincular.mutateAsync(desvinculando.atribuicao.id);
      notifications.show({ message: `${desvinculando.apelido ?? desvinculando.mac} não está mais vinculada.` });
      setDesvinculando(undefined);
    } catch (e) {
      erro(e);
    }
  }

  function alternarAtiva(p: Pulseira, ativa: boolean) {
    atualizar.mutate(
      { id: p.id, ativa },
      {
        onError: erro,
        onSuccess: () => {
          if (!ativa && p.atribuicao) {
            notifications.show({ message: `Vínculo com ${p.atribuicao.pesquisador} encerrado.` });
          }
        },
      },
    );
  }

  function abrirNova() {
    setEditando(undefined);
    modal.open();
  }

  async function confirmarRemocao() {
    if (!removendo) return;
    try {
      const { resultado } = await remover.mutateAsync(removendo.id);
      notifications.show({
        color: "green",
        message:
          resultado === "arquivada"
            ? "Pulseira removida. Ela tinha histórico, então ele foi preservado."
            : "Pulseira excluída.",
      });
      setRemovendo(undefined);
    } catch (e) {
      erro(e);
    }
  }

  return (
    <>
      <Group justify="space-between" mb="md">
        <Title order={2}>Pulseiras</Title>
        {podeEditar && (
          <Button leftSection={<IconPlus size={16} />} onClick={abrirNova}>
            Cadastrar pulseira
          </Button>
        )}
      </Group>

      {isLoading && <Loader />}
      {error && <Alert color="red">{error.message}</Alert>}
      {data && data.length === 0 && (
        <Alert color="blue" title="Nenhuma pulseira cadastrada">
          Cadastre o MAC de uma pulseira (ou rode o simulador com <Code>uv run redenb4 simular --cadastrar</Code>).
        </Alert>
      )}

      {data && data.length > 0 && (
        <Table.ScrollContainer minWidth={900}>
          <Table striped highlightOnHover verticalSpacing="sm">
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Apelido</Table.Th>
                <Table.Th>MAC</Table.Th>
                <Table.Th>Pesquisador</Table.Th>
                <Table.Th>Status</Table.Th>
                <Table.Th>Último BPM</Table.Th>
                <Table.Th>Último contato</Table.Th>
                <Table.Th>RSSI</Table.Th>
                <Table.Th>Ativa</Table.Th>
                <Table.Th />
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {data.map((p) => {
                const st = aoVivo.get(p.id) ?? p.status;
                return (
                  <Table.Tr key={p.id}>
                    <Table.Td>
                      <Anchor component={Link} to={`/pulseiras/${p.id}`}>
                        {p.apelido ?? "(sem apelido)"}
                      </Anchor>
                    </Table.Td>
                    <Table.Td>
                      <Code>{p.mac}</Code>
                    </Table.Td>
                    <Table.Td>
                      {p.atribuicao ? (
                        <Tooltip label={`Desde ${formatarDataHora(p.atribuicao.inicio)}`}>
                          <span>{p.atribuicao.pesquisador}</span>
                        </Tooltip>
                      ) : (
                        <Text c="dimmed" size="sm">
                          Não vinculada
                        </Text>
                      )}
                    </Table.Td>
                    <Table.Td>
                      <BadgeStatus p={p} st={st} />
                    </Table.Td>
                    <Table.Td>{st?.ultimo_bpm ?? "—"}</Table.Td>
                    <Table.Td>
                      <Tooltip label={formatarDataHora(st?.ultimo_contato)}>
                        <span>{haQuantoTempo(st?.ultimo_contato)}</span>
                      </Tooltip>
                    </Table.Td>
                    <Table.Td>{st?.rssi != null ? `${Math.round(st.rssi)} dBm` : "—"}</Table.Td>
                    <Table.Td>
                      <Switch
                        checked={p.ativa}
                        disabled={!podeEditar}
                        aria-label={p.ativa ? "Desativar" : "Ativar"}
                        onChange={(e) => alternarAtiva(p, e.currentTarget.checked)}
                      />
                    </Table.Td>
                    <Table.Td>
                      <Group gap={4} wrap="nowrap">
                        {!podeEditar ? null : p.atribuicao ? (
                          <Tooltip label="Desvincular">
                            <ActionIcon
                              variant="subtle"
                              color="orange"
                              aria-label="Desvincular"
                              onClick={() => setDesvinculando(p)}
                            >
                              <IconUserMinus size={16} />
                            </ActionIcon>
                          </Tooltip>
                        ) : (
                          <Tooltip label={p.ativa ? "Vincular a um pesquisador" : "Ative a pulseira para vincular"}>
                            <ActionIcon
                              variant="subtle"
                              aria-label="Vincular"
                              disabled={!p.ativa}
                              onClick={() => setVinculando(p)}
                            >
                              <IconUserPlus size={16} />
                            </ActionIcon>
                          </Tooltip>
                        )}
                        <Tooltip label="Histórico de uso">
                          <ActionIcon variant="subtle" color="gray" aria-label="Histórico" onClick={() => setHistorico(p)}>
                            <IconHistory size={16} />
                          </ActionIcon>
                        </Tooltip>
                        {podeEditar && (
                          <>
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
                            <ActionIcon variant="subtle" color="red" aria-label="Remover" onClick={() => setRemovendo(p)}>
                              <IconTrash size={16} />
                            </ActionIcon>
                          </>
                        )}
                      </Group>
                    </Table.Td>
                  </Table.Tr>
                );
              })}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      )}

      <Modal opened={modalAberto} onClose={modal.close} title={editando ? "Editar pulseira" : "Cadastrar pulseira"}>
        <FormPulseira key={editando?.id ?? "nova"} pulseira={editando} aoFechar={modal.close} />
      </Modal>

      <Modal
        opened={!!vinculando}
        onClose={() => setVinculando(undefined)}
        title={`Vincular ${vinculando?.apelido ?? vinculando?.mac ?? ""}`}
      >
        {vinculando && <FormVincular pulseira={vinculando} aoFechar={() => setVinculando(undefined)} />}
      </Modal>

      <Modal opened={!!desvinculando} onClose={() => setDesvinculando(undefined)} title="Desvincular pulseira">
        <Stack>
          <Text>
            Encerrar o uso de <b>{desvinculando?.apelido ?? desvinculando?.mac}</b> por{" "}
            <b>{desvinculando?.atribuicao?.pesquisador}</b>? As leituras seguintes deixam de ser registradas para essa
            pessoa. O histórico do período fica guardado.
          </Text>
          <Group justify="flex-end">
            <Button variant="default" onClick={() => setDesvinculando(undefined)}>
              Cancelar
            </Button>
            <Button color="orange" loading={desvincular.isPending} onClick={confirmarDesvinculo}>
              Desvincular
            </Button>
          </Group>
        </Stack>
      </Modal>

      <Modal
        opened={!!historico}
        onClose={() => setHistorico(undefined)}
        title={`Histórico de uso: ${historico?.apelido ?? historico?.mac ?? ""}`}
        size="lg"
      >
        {historico && <HistoricoVinculos pulseiraId={historico.id} />}
      </Modal>

      <Modal opened={!!removendo} onClose={() => setRemovendo(undefined)} title="Remover pulseira">
        <Stack>
          <Text>
            Remover <b>{removendo?.apelido ?? removendo?.mac}</b>? O servidor deixa de aceitar os dados dela. Se ela
            tiver leituras ou já tiver sido usada por alguém, o histórico é preservado.
          </Text>
          <Group justify="flex-end">
            <Button variant="default" onClick={() => setRemovendo(undefined)}>
              Cancelar
            </Button>
            <Button color="red" loading={remover.isPending} onClick={confirmarRemocao}>
              Remover
            </Button>
          </Group>
        </Stack>
      </Modal>
    </>
  );
}
