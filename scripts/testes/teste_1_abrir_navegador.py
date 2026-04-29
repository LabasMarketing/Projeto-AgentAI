from playwright.sync_api import sync_playwright

URL = "https://www.linkedin.com/jobs/view/4401468479/"

with sync_playwright() as p:
    context = p.chromium.launch_persistent_context(
        user_data_dir="browser_profiles/linkedin",
        headless=False,
        locale="pt-BR"
    )
    context.set_extra_http_headers({
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8"
    })
    page = context.new_page()
    page.goto(URL)

    input("Pressione ENTER para fechar...")

    context.close()