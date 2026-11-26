import { Alert, Code, Group, Loader, SegmentedControl, Select, Table, Text, Title, Tooltip } from "@mantine/core";
import { useMemo, useState } from "react";

import { useAcoesAuditoria, useAuditoria, useUsuarios } from "../api/usuarios";
import { formatarDataHora } from "../util/tempo";

const PERIODOS = [
  { value: "24", label: "24 h" },
  { value: "168", label: "7 dias" },
  { value: "720", label: "30 dias" },
];

/** "pulseira.editar" -> "pulseira · editar" (mais fácil de ler na tabela). */
function rotuloAcao(acao: string): string {
  return acao.replace(".", " · ").replaceAll("_", " ");
}

function resumo(detalhes: Record<string, unknown> | null | undefined): string {
  if (!detalhes) return "";
  return Object.entries(detalhes)
    .map(([k, v]) => `${k}: ${typeof v === "object" ? JSON.stringify(v) : String(v)}`)
    .join(" · ");
}

export function Auditoria() {
  const [usuario, setUsuario] = useState<string | null>(null);
  const [acao, setAcao] = useState<string | null>(null);
  const [horas, setHoras] = useState("168");
  const de = useMemo(() => new Date(Date.now() - Number(horas) * 3600_000).toISOString(), [horas]);
  const { data, isLoading, error } = useAuditoria({
    usuario_id: usuario ? Number(usuario) : undefined,
    acao: acao ?? undefined,
    de,
  });
  const usuarios = useUsuarios();
  const acoes = useAcoesAuditoria();
  const grupos = useMemo(
    () => [...new Set((acoes.data ?? []).map((a) => a.split(".")[0]))].map((g) => ({ value: g, label: g })),
    [acoes.data],
  );

  return (
    <>
      <Group justify="space-between" mb="md">
        <Title order={2}>Auditoria</Title>
        <SegmentedControl size="xs" data={PERIODOS} value={horas} onChange={setHoras} />
      </Group>
      <Group mb="md">
        <Select
          placeholder="Todos os usuários"
          data={(usuarios.data ?? []).map((u) => ({ value: String(u.id), label: u.nome }))}
          value={usuario}
          onChange={setUsuario}
          clearable
          w={240}
        />
        <Select
          placeholder="Todas as ações"
          data={grupos}
          value={acao}
          onChange={setAcao}
          clearable
          w={200}
        />
      </Group>

      {isLoading && <Loader />}
      {error && <Alert color="red">{error.message}</Alert>}
      {data && data.length === 0 && <Text c="dimmed">Nada registrado com esses filtros.</Text>}
      {data && data.length > 0 && (
        <Table.ScrollContainer minWidth={820}>
          <Table striped verticalSpacing="xs">
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Quando</Table.Th>
                <Table.Th>Quem</Table.Th>
                <Table.Th>Ação</Table.Th>
                <Table.Th>Item</Table.Th>
                <Table.Th>Detalhes</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {data.map((r) => (
                <Table.Tr key={r.id}>
                  <Table.Td style={{ whiteSpace: "nowrap" }}>{formatarDataHora(r.ts)}</Table.Td>
                  <Table.Td>
                    {r.usuario ? (
                      <Tooltip label={r.email}>
                        <span>{r.usuario}</span>
                      </Tooltip>
                    ) : (
                      <Text size="sm" c="dimmed">
                        {r.acao === "login.falhou" ? "(desconhecido)" : "(sistema)"}
                      </Text>
                    )}
                  </Table.Td>
                  <Table.Td>
                    <Text size="sm" c={r.acao.endsWith("falhou") ? "red" : undefined}>
                      {rotuloAcao(r.acao)}
                    </Text>
                  </Table.Td>
                  <Table.Td>{r.entidade ? `${r.entidade}${r.entidade_id != null ? ` #${r.entidade_id}` : ""}` : "—"}</Table.Td>
                  <Table.Td>
                    {r.detalhes ? (
                      <Code style={{ whiteSpace: "pre-wrap" }}>{resumo(r.detalhes)}</Code>
                    ) : (
                      <Text size="sm" c="dimmed">
                        —
                      </Text>
                    )}
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      )}
    </>
  );
}
