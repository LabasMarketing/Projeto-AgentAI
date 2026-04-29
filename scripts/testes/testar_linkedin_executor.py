from scripts.candidatura.linkedin_easy_apply_executor import LinkedInEasyApplyExecutor

vaga = {
    "url_vaga": "https://www.linkedin.com/jobs/view/4387503227/?alternateChannel=search&eBP=BUDGET_EXHAUSTED_JOB&trk=d_flagship3_job_collections_discovery_landing&refId=bmdA%2BY6rAscueEtDpJmqIw%3D%3D&trackingId=mX6gr9Iis73Jh3K%2BL5fVcg%3D%3D",
    "empresa": "GFT Technologies Brasil",
    "titulo_vaga": "Banco de Talentos GFT - QA Automação"
}

executor = LinkedInEasyApplyExecutor(headless=False)
resultado = executor.executar(vaga)

print(resultado)