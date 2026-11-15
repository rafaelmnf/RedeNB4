import { Alert, Title } from "@mantine/core";

export function Dashboard() {
  return (
    <>
      <Title order={2} mb="md">
        Dashboard
      </Title>
      <Alert color="blue" title="Em construção">
        Os cards em tempo real chegam na etapa (c). Por enquanto, acompanhe as pulseiras na tela Pulseiras.
      </Alert>
    </>
  );
}
