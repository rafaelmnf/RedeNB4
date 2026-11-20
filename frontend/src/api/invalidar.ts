import type { QueryClient } from "@tanstack/react-query";

/** Pulseiras, pesquisadores e vínculos se afetam (ex.: desativar encerra o vínculo). */
export function invalidarCadastros(qc: QueryClient) {
  for (const chave of ["pulseiras", "pesquisadores", "atribuicoes"]) {
    qc.invalidateQueries({ queryKey: [chave] });
  }
}
