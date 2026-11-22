import { Alert, Badge, Group, Loader, SegmentedControl, SimpleGrid, Text, Title } from "@mantine/core";
import { useState } from "react";
import { Link } from "react-router-dom";

import { useCartoes, useConexao } from "../aoVivo/AoVivoProvider";
import { CardPulseira, estadoDoCartao } from "../componentes/CardPulseira";

const JANELAS = [
  { value: "60", label: "1 min" },
  { value: "300", label: "5 min" },
  { value: "900", label: "15 min" },
];
const CHAVE_JANELA = "dashboard.janela";

function janelaSalva(): string {
  try {
    const v = localStorage.getItem(CHAVE_JANELA);
    if (v && JANELAS.some((j) => j.value === v)) return v;
  } catch {
    // armazenamento indisponível (janela privada etc.)
  }
  return "300";
}

export function BadgeConexao() {
  const conexao = useConexao();
  if (conexao === "ao_vivo") return <Badge color="green" variant="dot">Ao vivo</Badge>;
  if (conexao === "conectando") return <Badge color="gray" variant="dot">Conectando…</Badge>;
  return (
    <Badge color="orange" variant="dot">
      Reconectando…
    </Badge>
  );
}

export function Dashboard() {
  const cartoes = useCartoes();
  const conexao = useConexao();
  const [janela, setJanela] = useState(janelaSalva);

  function trocarJanela(v: string) {
    setJanela(v);
    try {
      localStorage.setItem(CHAVE_JANELA, v);
    } catch {
      // ignora
    }
  }

  const contagem = { online: 0, offline: 0, sem_dados: 0 };
  for (const c of cartoes) {
    const e = estadoDoCartao(c);
    if (e === "sem_dados") contagem.sem_dados++;
    else if (e === "offline") contagem.offline++;
    else contagem.online++;
  }

  return (
    <>
      <Group justify="space-between" mb="md" gap="sm">
        <Group gap="sm">
          <Title order={2}>Dashboard</Title>
          <BadgeConexao />
        </Group>
        <Group gap="md">
          <Text size="sm" c="dimmed">
            {contagem.online} online · {contagem.offline} sem sinal · {contagem.sem_dados} sem dados
          </Text>
          <SegmentedControl size="xs" data={JANELAS} value={janela} onChange={trocarJanela} />
        </Group>
      </Group>

      {conexao === "conectando" && cartoes.length === 0 && <Loader />}
      {conexao !== "conectando" && cartoes.length === 0 && (
        <Alert color="blue" title="Nenhuma pulseira ativa">
          Cadastre ou ative uma pulseira na tela <Link to="/pulseiras">Pulseiras</Link>. Os cards aparecem aqui sem
          recarregar.
        </Alert>
      )}

      <SimpleGrid cols={{ base: 1, sm: 2, lg: 3, xl: 4 }}>
        {cartoes.map((c) => (
          <CardPulseira key={c.pulseira_id} c={c} janelaS={Number(janela)} />
        ))}
      </SimpleGrid>
    </>
  );
}
