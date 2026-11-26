import { Alert, Button, Card, Center, PasswordInput, Stack, Text, TextInput, Title } from "@mantine/core";
import { useState } from "react";
import { Navigate, useNavigate, useSearchParams } from "react-router-dom";

import { useEntrar, useSessao } from "../sessao/sessao";

export function Login() {
  const { data: usuario } = useSessao();
  const entrar = useEntrar();
  const navegar = useNavigate();
  const [params] = useSearchParams();
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const volta = params.get("volta");
  const destino = volta && volta.startsWith("/") && !volta.startsWith("/login") ? volta : "/";

  if (usuario) return <Navigate to={destino} replace />;

  async function enviar(e: React.FormEvent) {
    e.preventDefault();
    try {
      await entrar.mutateAsync({ email, senha });
      navegar(destino, { replace: true });
    } catch {
      // a mensagem aparece abaixo (entrar.error)
    }
  }

  return (
    <Center mih="100vh" p="md">
      <Card withBorder radius="md" p="xl" w={380} component="form" onSubmit={enviar}>
        <Stack>
          <div>
            <Title order={3}>RedeNB4</Title>
            <Text size="sm" c="dimmed">
              Monitoramento de BPM
            </Text>
          </div>
          <TextInput
            label="E-mail CNPEM"
            type="email"
            autoComplete="username"
            value={email}
            onChange={(e) => setEmail(e.currentTarget.value)}
            required
            data-autofocus
            autoFocus
          />
          <PasswordInput
            label="Senha"
            autoComplete="current-password"
            value={senha}
            onChange={(e) => setSenha(e.currentTarget.value)}
            required
          />
          {entrar.error && (
            <Alert color="red" variant="light">
              {entrar.error.message}
            </Alert>
          )}
          <Button type="submit" loading={entrar.isPending} fullWidth>
            Entrar
          </Button>
          <Text size="xs" c="dimmed">
            Esqueceu a senha? Peça a um administrador para redefini-la.
          </Text>
        </Stack>
      </Card>
    </Center>
  );
}
