"""Notas SOAP sintéticas para teste. Nenhum dado real de paciente, em nenhum caso."""

NOTA_COMPLETA = """#TELEMEDICINA#
-F: Paciente refere dor de garganta. Sem sinais de alarme.
-S: Refere odinofagia há 2 dias, de intensidade leve, sem piora progressiva.
Nega febre. Nega dispneia. Nega disfagia.
MUC: nega uso de medicações.
AP: nega comorbidades.
AF: irrelevante para o caso.
Alergia: nega alergia medicamentosa conhecida.
Hábitos: nega tabagismo e etilismo.
-O: Ectoscopia em tela: BEG, CHAAAE, consciente, orientado em tempo e espaço.
Sem sinais de esforço respiratório, fala não entrecortada.
-A: Infecção de vias aéreas superiores (CID: J06.9).
-P:
1. Dipirona 500mg, via oral, de 6/6h por 3 dias, se dor.
2. Hidratação abundante e repouso relativo.
3. Orientado sobre sinais de alarme: febre persistente, dispneia, disfagia.
4. Retorno agendado em 5 dias ou antes se piora. Orientado a procurar PS presencial se dispneia.
5. Não emitido atestado nesta consulta.
Paciente ciente e concordante com plano terapêutico.
Atendimento realizado via telemedicina, não sendo possível aferição de sinais vitais ou exame físico completo."""

NOTA_SEM_CID = NOTA_COMPLETA.replace(" (CID: J06.9)", "")

NOTA_SEM_CABECALHO = NOTA_COMPLETA.replace("#TELEMEDICINA#\n", "")

NOTA_SEM_ALARME = NOTA_COMPLETA.replace(
    "3. Orientado sobre sinais de alarme: febre persistente, dispneia, disfagia.\n", ""
)

NOTA_SEM_OBJETIVO = """#TELEMEDICINA#
-F: Paciente refere cefaleia. Sem sinais de alarme.
-S: Refere cefaleia há 1 dia. Nega febre.
MUC: nega uso de medicações.
AP: nega comorbidades.
AF: irrelevante para o caso.
Alergia: nega alergia medicamentosa conhecida.
Hábitos: nega tabagismo.
-A: Cefaleia tensional (CID: R51).
-P:
1. Dipirona 500mg via oral se dor.
3. Orientado sobre sinais de alarme: cefaleia súbita intensa.
Paciente ciente e concordante com plano terapêutico.
Atendimento realizado via telemedicina, não sendo possível aferição de sinais vitais."""

NOTA_FORMATACAO_SOLTA = """#telemedicina#
F : Paciente refere tosse.
 - s: Refere tosse seca há 3 dias. Nega febre.
-O : Ectoscopia em tela: BEG.
- A: Bronquite aguda (CID: J20.9).
-P:
1. Sintomáticos.
3. Orientado sobre sinais de alarme: dispneia.
Paciente ciente e concordante com plano terapêutico.
Atendimento realizado via telemedicina."""
