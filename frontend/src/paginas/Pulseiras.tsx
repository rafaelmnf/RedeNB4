import {
  ActionIcon,
  Alert,
  Badge,
  Button,
  Code,
  Group,
  Loader,
  Modal,
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
import { IconPencil, IconPlus, IconTrash } from "@tabler/icons-react";
import { useState } from "react";

import type { Pulseira } from "../api/cliente";
import {
  useAtualizarPulseira,
  useCadastrarPulseira,
  usePulseiras,
  useRemoverPulseira,
} from "../api/pulseiras";
import { normalizarMac } from "../util/mac";
import { formatarDataHora, haQuantoTempo } from "../util/tempo";

function erro(e: unknown) {
  notifications.show({ color: "red", title: "Erro", message: e instanceof Error ? e.message : String(e) });
}

function BadgeStatus({ p }: { p: Pulseira }) {
  if (!p.ativa) return <Badge color="gray">desativada</Badge>;
  const st = p.status;
  if (!st?.ultimo_contato) return <Badge color="gray" variant="light">sem dados</Badge>;
  if (!st.online) return <Badge color="orange" variant="light">offline</Badge>;
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

export function Pulseiras() {
  const { data, isLoading, error } = usePulseiras();
  const atualizar = useAtualizarPulseira();
  const remover = useRemoverPulseira();
  const [modalAberto, modal] = useDisclosure(false);
  const [editando, setEditando] = useState<Pulseira | undefined>();
  const [removendo, setRemovendo] = useState<Pulseira | undefined>();

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
            ? "Pulseira removida. Ela tinha leituras, então o histórico foi preservado."
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
        <Button leftSection={<IconPlus size={16} />} onClick={abrirNova}>
          Cadastrar pulseira
        </Button>
      </Group>

      {isLoading && <Loader />}
      {error && <Alert color="red">{error.message}</Alert>}
      {data && data.length === 0 && (
        <Alert color="blue" title="Nenhuma pulseira cadastrada">
          Cadastre o MAC de uma pulseira (ou rode o simulador com <Code>uv run redenb4 simular --cadastrar</Code>).
        </Alert>
      )}

      {data && data.length > 0 && (
        <Table.ScrollContainer minWidth={760}>
          <Table striped highlightOnHover verticalSpacing="sm">
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Apelido</Table.Th>
                <Table.Th>MAC</Table.Th>
                <Table.Th>Status</Table.Th>
                <Table.Th>Último BPM</Table.Th>
                <Table.Th>Último contato</Table.Th>
                <Table.Th>RSSI</Table.Th>
                <Table.Th>Ativa</Table.Th>
                <Table.Th />
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {data.map((p) => (
                <Table.Tr key={p.id}>
                  <Table.Td>{p.apelido ?? <Text c="dimmed">—</Text>}</Table.Td>
                  <Table.Td>
                    <Code>{p.mac}</Code>
                  </Table.Td>
                  <Table.Td>
                    <BadgeStatus p={p} />
                  </Table.Td>
                  <Table.Td>{p.status?.ultimo_bpm ?? "—"}</Table.Td>
                  <Table.Td>
                    <Tooltip label={formatarDataHora(p.status?.ultimo_contato)}>
                      <span>{haQuantoTempo(p.status?.ultimo_contato)}</span>
                    </Tooltip>
                  </Table.Td>
                  <Table.Td>{p.status?.rssi != null ? `${p.status.rssi} dBm` : "—"}</Table.Td>
                  <Table.Td>
                    <Switch
                      checked={p.ativa}
                      aria-label={p.ativa ? "Desativar" : "Ativar"}
                      onChange={(e) =>
                        atualizar.mutate({ id: p.id, ativa: e.currentTarget.checked }, { onError: erro })
                      }
                    />
                  </Table.Td>
                  <Table.Td>
                    <Group gap={4} wrap="nowrap">
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
                    </Group>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      )}

      <Modal opened={modalAberto} onClose={modal.close} title={editando ? "Editar pulseira" : "Cadastrar pulseira"}>
        <FormPulseira key={editando?.id ?? "nova"} pulseira={editando} aoFechar={modal.close} />
      </Modal>

      <Modal opened={!!removendo} onClose={() => setRemovendo(undefined)} title="Remover pulseira">
        <Stack>
          <Text>
            Remover <b>{removendo?.apelido ?? removendo?.mac}</b>? O servidor deixa de aceitar os dados dela. Se ela
            tiver leituras gravadas, o histórico é preservado.
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
