import { Alert, Badge, Loader, Table, Text } from "@mantine/core";

import { useAtribuicoes } from "../api/atribuicoes";
import { formatarDataHora } from "../util/tempo";

/** Quem usou a pulseira e quando. */
export function HistoricoVinculos({ pulseiraId }: { pulseiraId: number }) {
  const { data, isLoading, error } = useAtribuicoes({ pulseira_id: pulseiraId });
  if (isLoading) return <Loader />;
  if (error) return <Alert color="red">{error.message}</Alert>;
  if (!data?.length) return <Text c="dimmed">Esta pulseira ainda não foi usada por ninguém.</Text>;
  return (
    <Table striped>
      <Table.Thead>
        <Table.Tr>
          <Table.Th>Pesquisador</Table.Th>
          <Table.Th>Início</Table.Th>
          <Table.Th>Fim</Table.Th>
        </Table.Tr>
      </Table.Thead>
      <Table.Tbody>
        {data.map((a) => (
          <Table.Tr key={a.id}>
            <Table.Td>{a.pesquisador}</Table.Td>
            <Table.Td>{formatarDataHora(a.inicio)}</Table.Td>
            <Table.Td>{a.fim ? formatarDataHora(a.fim) : <Badge color="teal">em uso</Badge>}</Table.Td>
          </Table.Tr>
        ))}
      </Table.Tbody>
    </Table>
  );
}
