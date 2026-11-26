import type { QueryClient } from "@tanstack/react-query";

/** Os cadastros se afetam (ex.: desativar encerra o vínculo; o total de experimentos
 * aparece no laboratório; o nome do pesquisador aparece no experimento). */
export function invalidarCadastros(qc: QueryClient) {
  for (const chave of ["pulseiras", "pesquisadores", "atribuicoes", "laboratorios", "experimentos"]) {
    qc.invalidateQueries({ queryKey: [chave] });
  }
}
