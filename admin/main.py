# Admin page for Garimpeiro: create, list, re-code and delete people.
#
# It runs ONLY on this PC (address 127.0.0.1 = "this computer"), so nobody else
# can open it. It uses the secret key from bot/.env, which never leaves the PC.
import os
import secrets
import sys
import urllib.error

import flet as ft

# Reuse the bot's database helper (it reads bot/.env for us).
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "bot"))
import db  # noqa: E402

PORT = 8551
# No look-alike characters (0/o, 1/l/i), so codes are easy to read out loud.
CODE_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"
CODE_LENGTH = 10


def new_code():
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))


def new_topic():
    return "garimpeiro-" + secrets.token_hex(8)


def list_people():
    return db._request(
        "GET",
        "people?select=id,name,code,ntfy_topic,tags(count),followed_categories(count)"
        "&order=created_at.asc",
    )


def create_person(name):
    """Insert a person. Retries if the random code/topic collides (very unlikely)."""
    for _ in range(5):
        body = {"name": name, "code": new_code(), "ntfy_topic": new_topic()}
        try:
            rows = db._request("POST", "people", body, prefer="return=representation")
            return rows[0]
        except urllib.error.HTTPError as error:
            if error.code != 409:  # 409 = code or topic already exists
                raise
    raise RuntimeError("Não consegui gerar um código único. Tente de novo.")


def change_code(person_id):
    code = new_code()
    db._request("PATCH", f"people?id=eq.{person_id}", {"code": code})
    return code


def delete_person(person_id):
    db._request("DELETE", f"people?id=eq.{person_id}")


def welcome_message(person):
    """Text you can paste into WhatsApp for the new person."""
    return (
        f"Oi, {person['name']}! Aqui está seu acesso ao Garimpeiro 🔎\n\n"
        f"1) Instale o app ntfy (Play Store) e assine o canal: {person['ntfy_topic']}\n"
        f"2) Instale o Garimpeiro (APK que vou te mandar)\n"
        f"3) Abra o Garimpeiro e digite seu código de acesso: {person['code']}\n\n"
        "Não passe o código nem o canal para ninguém."
    )


async def main(page: ft.Page):
    page.title = "Garimpeiro - Administração"
    page.padding = 20
    page.scroll = ft.ScrollMode.AUTO
    clipboard = ft.Clipboard()
    page.services.append(clipboard)

    list_area = ft.Column(spacing=10)
    name_field = ft.TextField(label="Nome da nova pessoa", expand=True)

    def toast(message):
        page.show_dialog(ft.SnackBar(ft.Text(message)))

    async def copy(text, what):
        await clipboard.set(text)
        toast(f"{what} copiado!")

    def refresh():
        try:
            people = list_people()
        except Exception as error:  # show any problem on screen instead of crashing
            list_area.controls = [ft.Text(f"Erro ao carregar: {error}", color=ft.Colors.RED)]
            page.update()
            return
        list_area.controls = [person_card(p) for p in people] or [ft.Text("Ninguém cadastrado ainda.")]
        page.update()

    def person_card(person):
        tags = person["tags"][0]["count"] if person["tags"] else 0
        cats = person["followed_categories"][0]["count"] if person["followed_categories"] else 0

        async def copy_message(e):
            await copy(welcome_message(person), "Mensagem")

        async def copy_code(e):
            await copy(person["code"], "Código")

        def ask_new_code(e):
            def confirm(e2):
                page.pop_dialog()
                try:
                    code = change_code(person["id"])
                except Exception as error:
                    toast(f"Erro: {error}")
                    return
                toast(f"Novo código de {person['name']}: {code}")
                refresh()

            page.show_dialog(ft.AlertDialog(
                modal=True,
                title=ft.Text("Trocar o código?"),
                content=ft.Text(f"O código antigo de {person['name']} para de funcionar."),
                actions=[ft.TextButton(content="Cancelar", on_click=lambda e2: page.pop_dialog()),
                         ft.FilledButton(content="Trocar", on_click=confirm)],
            ))

        def ask_delete(e):
            def confirm(e2):
                page.pop_dialog()
                try:
                    delete_person(person["id"])
                except Exception as error:
                    toast(f"Erro: {error}")
                    return
                toast(f"{person['name']} foi removido(a).")
                refresh()

            page.show_dialog(ft.AlertDialog(
                modal=True,
                title=ft.Text(f"Apagar {person['name']}?"),
                content=ft.Text("Apaga também as tags, categorias e o histórico dessa pessoa. "
                                "Não dá para desfazer."),
                actions=[ft.TextButton(content="Cancelar", on_click=lambda e2: page.pop_dialog()),
                         ft.FilledButton(content="Apagar", on_click=confirm)],
            ))

        return ft.Card(content=ft.Container(padding=15, content=ft.Column([
            ft.Text(person["name"], size=20, weight=ft.FontWeight.BOLD),
            ft.Text(f"Código de acesso: {person['code']}", selectable=True),
            ft.Text(f"Canal ntfy: {person['ntfy_topic']}", selectable=True),
            ft.Text(f"{tags} tag(s), {cats} categoria(s)", size=12),
            ft.Row([
                ft.Button(content="Copiar mensagem", on_click=copy_message),
                ft.OutlinedButton(content="Copiar código", on_click=copy_code),
                ft.OutlinedButton(content="Novo código", on_click=ask_new_code),
                ft.OutlinedButton(content="Apagar", on_click=ask_delete),
            ], wrap=True),
        ], spacing=6)))

    async def add_person(e):
        name = (name_field.value or "").strip()
        if not name:
            toast("Digite um nome.")
            return
        try:
            person = create_person(name)
        except Exception as error:
            toast(f"Erro: {error}")
            return
        name_field.value = ""
        await copy(welcome_message(person), f"Mensagem de boas-vindas de {name}")
        refresh()

    page.add(
        ft.Text("Garimpeiro - Administração", size=26, weight=ft.FontWeight.BOLD),
        ft.Text("Esta página só abre neste computador.", size=12),
        ft.Row([name_field, ft.FilledButton(content="Cadastrar", on_click=add_person)]),
        ft.Divider(),
        list_area,
    )
    refresh()


if __name__ == "__main__":
    ft.run(main, view=ft.AppView.WEB_BROWSER, host="127.0.0.1", port=PORT)
