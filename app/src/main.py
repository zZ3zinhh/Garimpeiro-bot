# Garimpeiro app: lets each person manage their own tags and categories.
# The screens are in Portuguese because friends and family use them.
import asyncio
from datetime import datetime

import flet as ft

import api
from settings import APP_NAME

CATEGORY_LABELS = {
    "computers": "Informática",
    "games": "Games",
    "phones": "Celulares",
    "electronics": "Eletrônicos",
}
REASON_LABELS = {
    "absurd": "🔥 Promoção absurda",
    "normal": "🔔 Sua tag",
    "category": "💸 Categoria",
}
TAB_TAGS, TAB_CATEGORIES, TAB_RECENT, TAB_ALERTS = 0, 1, 2, 3


# ---------- small helpers ----------

async def call(function, *args):
    """Runs a slow function (internet) in the background so the screen doesn't freeze."""
    return await asyncio.to_thread(function, *args)


def parse_number(text):
    """'3.000,50' -> 3000.5 | '3000' -> 3000.0 | '' -> None | 'abc' -> None"""
    text = (text or "").strip().replace("R$", "").replace(" ", "")
    if not text:
        return None
    if "," in text:  # Brazilian format: dot = thousands, comma = decimals
        text = text.replace(".", "").replace(",", ".")
    elif "." in text and len(text.rsplit(".", 1)[1]) == 3:  # '3.000' means three thousand
        text = text.replace(".", "")
    try:
        return float(text)
    except ValueError:
        return None


def number_to_text(value):
    """3000.0 -> '3000' | 2574.5 -> '2574,5' | None -> ''"""
    if value is None:
        return ""
    if float(value) == int(value):
        return str(int(value))
    return str(value).replace(".", ",")


def brl(value):
    """2574.5 -> 'R$ 2.574,50'"""
    if value is None:
        return ""
    text = f"{float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return "R$ " + text


def tag_summary(tag):
    parts = []
    if tag.get("max_price"):
        parts.append(f"até {brl(tag['max_price'])}")
    if tag.get("absurd_alert") and tag.get("market_price"):
        limit = tag.get("limit_pct") or 50
        parts.append(f"🔥 absurda: até {brl(tag['market_price'] * limit / 100)}")
    if tag.get("blocked_words"):
        parts.append("sem: " + ", ".join(tag["blocked_words"]))
    return " · ".join(parts) or "Qualquer preço"


def category_summary(category):
    parts = []
    if category.get("min_discount_pct"):
        parts.append(f"desconto ≥ {number_to_text(category['min_discount_pct'])}% (Promobit)")
    if category.get("min_temperature"):
        parts.append(f"temperatura ≥ {category['min_temperature']}° (Pelando)")
    return " · ".join(parts)


def format_date(iso_text):
    try:
        return datetime.fromisoformat(iso_text).astimezone().strftime("%d/%m %H:%M")
    except (ValueError, TypeError):
        return ""


# ---------- the app ----------

class GarimpeiroApp:
    def __init__(self, page: ft.Page):
        self.page = page
        self.code = None
        self.profile = None
        self.recent = []
        self.tab = TAB_TAGS
        # "Services" are helpers the phone provides: saved settings, links, clipboard.
        self.prefs = ft.SharedPreferences()
        self.launcher = ft.UrlLauncher()
        self.clipboard = ft.Clipboard()
        page.services.extend([self.prefs, self.launcher, self.clipboard])

    # ----- basic screens -----

    def toast(self, message):
        self.page.show_dialog(ft.SnackBar(ft.Text(message)))

    def reset_screen(self):
        self.page.controls.clear()
        self.page.navigation_bar = None
        self.page.floating_action_button = None

    def show_loading(self):
        self.reset_screen()
        self.page.add(ft.Container(ft.ProgressRing(), alignment=ft.Alignment.CENTER, expand=True))
        self.page.update()

    def show_login(self, error=None, code=""):
        self.reset_screen()
        field = ft.TextField(
            label="Seu código de acesso", value=code, autofocus=True,
            error=error, text_align=ft.TextAlign.CENTER,
        )

        async def enter(e):
            await self.login(field.value or "")

        field.on_submit = enter
        self.page.add(ft.SafeArea(expand=True, content=ft.Column(
            [
                ft.Text("🔍", size=64),
                ft.Text(APP_NAME, size=32, weight=ft.FontWeight.BOLD),
                ft.Text("Avisos de promoções feitos para você", color=ft.Colors.GREY),
                ft.Container(height=24),
                field,
                ft.Button(content="Entrar", on_click=enter),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            expand=True,
        )))
        self.page.update()

    async def start(self):
        saved = await self.prefs.get("code")
        if saved:
            await self.login(saved, saved_code=True)
        else:
            self.show_login()

    async def login(self, code, saved_code=False):
        code = code.strip().lower()
        if not code:
            self.show_login(error="Digite o código")
            return
        self.show_loading()
        try:
            self.profile = await call(api.get_profile, code)
        except api.ApiError as error:
            if error.kind == "invalid_code":
                await self.prefs.remove("code")
                code = ""
            self.show_login(error=str(error), code=code)
            return
        self.code = code
        await self.prefs.set("code", code)
        self.tab = TAB_TAGS
        self.render()

    async def logout(self, e):
        await self.prefs.remove("code")
        self.code = self.profile = None
        self.show_login()

    async def reload(self):
        """Fetches the profile again and redraws the screen."""
        try:
            self.profile = await call(api.get_profile, self.code)
        except api.ApiError as error:
            self.toast(str(error))
            return
        self.render()

    async def load_recent(self):
        try:
            self.recent = await call(api.recent_alerts, self.code)
        except api.ApiError as error:
            self.toast(str(error))
        self.render()

    # ----- main screen with the bottom bar -----

    def render(self):
        self.reset_screen()
        page = self.page
        page.navigation_bar = ft.NavigationBar(
            selected_index=self.tab,
            on_change=self.change_tab,
            destinations=[
                ft.NavigationBarDestination(icon=ft.Icons.SELL, label="Tags"),
                ft.NavigationBarDestination(icon=ft.Icons.CATEGORY, label="Categorias"),
                ft.NavigationBarDestination(icon=ft.Icons.HISTORY, label="Ofertas"),
                ft.NavigationBarDestination(icon=ft.Icons.NOTIFICATIONS, label="Avisos"),
            ],
        )
        if self.tab == TAB_TAGS:
            body = self.tags_view()
            page.floating_action_button = ft.FloatingActionButton(
                icon=ft.Icons.ADD, on_click=lambda e: self.open_tag_dialog())
        elif self.tab == TAB_CATEGORIES:
            body = self.categories_view()
            page.floating_action_button = ft.FloatingActionButton(
                icon=ft.Icons.ADD, on_click=lambda e: self.open_category_dialog())
        elif self.tab == TAB_RECENT:
            body = self.recent_view()
        else:
            body = self.alerts_view()
        page.add(ft.SafeArea(expand=True, content=body))
        page.update()

    async def change_tab(self, e):
        self.tab = e.control.selected_index
        if self.tab == TAB_RECENT:
            await self.load_recent()
        else:
            self.render()

    def title(self, text, subtitle=None):
        controls = [ft.Text(text, size=24, weight=ft.FontWeight.BOLD)]
        if subtitle:
            controls.append(ft.Text(subtitle, color=ft.Colors.GREY))
        return ft.Column(controls, spacing=2)

    # ----- tab: tags -----

    def tags_view(self):
        tags = self.profile["tags"]
        items = [self.title(f"Olá, {self.profile['name']}!", "Produtos que você quer caçar")]
        if not tags:
            items.append(ft.Text("Você ainda não tem tags. Toque no + para criar a primeira, "
                                 "por exemplo: rtx 5060 ti", color=ft.Colors.GREY))
        for tag in tags:
            items.append(ft.Card(content=ft.ListTile(
                leading=ft.Icon(ft.Icons.SELL),
                title=ft.Text(tag["text"]),
                subtitle=ft.Text(tag_summary(tag)),
                trailing=ft.IconButton(
                    ft.Icons.DELETE,
                    on_click=lambda e, t=tag: self.confirm_delete("tag", t)),
                on_click=lambda e, t=tag: self.open_tag_dialog(t),
            )))
        return ft.ListView(items, expand=True, spacing=6)

    def open_tag_dialog(self, tag=None):
        tag = tag or {}
        f_text = ft.TextField(label="Produto (ex.: rtx 5060 ti)", value=tag.get("text", ""),
                              autofocus=True)
        f_blocked = ft.TextField(label="Palavras bloqueadas (separe por vírgula)",
                                 value=", ".join(tag.get("blocked_words") or []),
                                 hint_text="notebook, pc gamer")
        f_max = ft.TextField(label="Preço máximo em R$ (opcional)",
                             value=number_to_text(tag.get("max_price")),
                             keyboard_type=ft.KeyboardType.NUMBER)
        f_market = ft.TextField(label="Preço de mercado em R$",
                                value=number_to_text(tag.get("market_price")),
                                keyboard_type=ft.KeyboardType.NUMBER,
                                disabled=not tag.get("absurd_alert"))
        f_limit = ft.TextField(label="Absurda = até quantos % do preço de mercado?",
                               value=str(tag.get("limit_pct") or 50),
                               keyboard_type=ft.KeyboardType.NUMBER,
                               disabled=not tag.get("absurd_alert"))

        def toggle_absurd(e):
            f_market.disabled = f_limit.disabled = not e.control.value
            f_market.update()
            f_limit.update()

        f_absurd = ft.Switch(label="Avisar promoção absurda", value=bool(tag.get("absurd_alert")),
                             on_change=toggle_absurd)

        async def save(e):
            text = (f_text.value or "").strip()
            if not text:
                f_text.error = "Digite o nome do produto"
                f_text.update()
                return
            market = parse_number(f_market.value)
            limit = parse_number(f_limit.value) or 50
            if f_absurd.value and not market:
                f_market.error = "Digite o preço de mercado"
                f_market.update()
                return
            if not 1 <= limit <= 100:
                f_limit.error = "Use um valor entre 1 e 100"
                f_limit.update()
                return
            blocked = [w.strip() for w in (f_blocked.value or "").split(",") if w.strip()]
            try:
                await call(api.save_tag, self.code, tag.get("id"), text, blocked,
                           parse_number(f_max.value), bool(f_absurd.value), market, int(limit))
            except api.ApiError as error:
                self.toast(str(error))
                return
            self.page.pop_dialog()
            await self.reload()

        self.page.show_dialog(ft.AlertDialog(
            modal=True,
            title=ft.Text("Editar tag" if tag else "Nova tag"),
            content=ft.Column([f_text, f_blocked, f_max, f_absurd, f_market, f_limit],
                              tight=True, scroll=ft.ScrollMode.AUTO, width=340),
            actions=[ft.TextButton(content="Cancelar", on_click=lambda e: self.page.pop_dialog()),
                     ft.FilledButton(content="Salvar", on_click=save)],
        ))

    # ----- tab: categories -----

    def categories_view(self):
        categories = self.profile["categories"]
        items = [self.title("Categorias", "Avisos de promoções boas em qualquer produto")]
        if not categories:
            items.append(ft.Text("Nenhuma categoria ainda. Toque no + para seguir uma.",
                                 color=ft.Colors.GREY))
        for category in categories:
            items.append(ft.Card(content=ft.ListTile(
                leading=ft.Icon(ft.Icons.CATEGORY),
                title=ft.Text(CATEGORY_LABELS.get(category["category"], category["category"])),
                subtitle=ft.Text(category_summary(category)),
                trailing=ft.IconButton(
                    ft.Icons.DELETE,
                    on_click=lambda e, c=category: self.confirm_delete("category", c)),
                on_click=lambda e, c=category: self.open_category_dialog(c),
            )))
        items.append(ft.Text("Notebooks e PCs prontos ficam de fora, para você ver só componentes.",
                             size=12, color=ft.Colors.GREY))
        return ft.ListView(items, expand=True, spacing=6)

    def open_category_dialog(self, category=None):
        category = category or {}
        f_category = ft.Dropdown(
            label="Categoria", value=category.get("category", "computers"),
            options=[ft.DropdownOption(key=k, text=v) for k, v in CATEGORY_LABELS.items()],
        )
        f_discount = ft.TextField(label="Desconto mínimo em % (Promobit)",
                                  value=number_to_text(category.get("min_discount_pct")),
                                  keyboard_type=ft.KeyboardType.NUMBER)
        f_temperature = ft.TextField(label="Temperatura mínima em ° (Pelando)",
                                     value=str(category.get("min_temperature") or ""),
                                     keyboard_type=ft.KeyboardType.NUMBER)

        async def save(e):
            discount = parse_number(f_discount.value)
            temperature = parse_number(f_temperature.value)
            if not discount and not temperature:
                f_discount.error = "Preencha o desconto ou a temperatura"
                f_discount.update()
                return
            try:
                await call(api.save_category, self.code, category.get("id"), f_category.value,
                           discount, int(temperature) if temperature else None)
            except api.ApiError as error:
                self.toast(str(error))
                return
            self.page.pop_dialog()
            await self.reload()

        self.page.show_dialog(ft.AlertDialog(
            modal=True,
            title=ft.Text("Editar categoria" if category else "Seguir categoria"),
            content=ft.Column(
                [f_category, f_discount, f_temperature,
                 ft.Text("Dica: 50% de desconto e 500° de temperatura são bons valores para começar.",
                         size=12, color=ft.Colors.GREY)],
                tight=True, scroll=ft.ScrollMode.AUTO, width=340),
            actions=[ft.TextButton(content="Cancelar", on_click=lambda e: self.page.pop_dialog()),
                     ft.FilledButton(content="Salvar", on_click=save)],
        ))

    # ----- delete (tags and categories) -----

    def confirm_delete(self, kind, item):
        name = item["text"] if kind == "tag" else CATEGORY_LABELS.get(item["category"], "")

        async def delete(e):
            try:
                if kind == "tag":
                    await call(api.delete_tag, self.code, item["id"])
                else:
                    await call(api.delete_category, self.code, item["id"])
            except api.ApiError as error:
                self.toast(str(error))
                return
            self.page.pop_dialog()
            await self.reload()

        self.page.show_dialog(ft.AlertDialog(
            modal=True,
            title=ft.Text("Apagar?"),
            content=ft.Text(f"Você vai parar de receber avisos de “{name}”."),
            actions=[ft.TextButton(content="Cancelar", on_click=lambda e: self.page.pop_dialog()),
                     ft.FilledButton(content="Apagar", on_click=delete)],
        ))

    # ----- tab: latest deals -----

    def recent_view(self):
        items = [self.title("Últimas ofertas", "O que o Garimpeiro avisou para você")]
        if not self.recent:
            items.append(ft.Text("Ainda não avisamos nenhuma oferta. Assim que aparecer uma "
                                 "boa, ela chega no celular e fica registrada aqui.",
                                 color=ft.Colors.GREY))
        for alert in self.recent:
            price = brl(alert["price"]) if alert.get("price") else ""
            subtitle = " · ".join(x for x in [
                price, REASON_LABELS.get(alert.get("reason"), ""), format_date(alert.get("sent_at"))
            ] if x)
            items.append(ft.Card(content=ft.ListTile(
                title=ft.Text(alert["title"], max_lines=2),
                subtitle=ft.Text(subtitle),
                trailing=ft.Icon(ft.Icons.OPEN_IN_NEW),
                on_click=lambda e, a=alert: self.page.run_task(self.open_link, a["link"]),
            )))
        return ft.ListView(items, expand=True, spacing=6)

    async def open_link(self, url):
        if url:
            await self.launcher.launch_url(url)

    # ----- tab: alerts settings -----

    def alerts_view(self):
        profile = self.profile
        topic = profile["ntfy_topic"]

        async def copy_topic(e):
            await self.clipboard.set(topic)
            self.toast("Canal copiado!")

        async def subscribe(e):
            try:
                await self.launcher.launch_url(f"ntfy://ntfy.sh/{topic}")
            except Exception:
                self.toast("Instale o app ntfy (Play Store) e assine o canal acima.")

        async def test_notification(e):
            try:
                await call(api.send_test_notification, topic)
                self.toast("Teste enviado! Confira o celular.")
            except api.ApiError as error:
                self.toast(str(error))

        f_whatsapp = ft.Switch(label="Receber também no WhatsApp",
                               value=bool(profile.get("whatsapp_enabled")))
        f_phone = ft.TextField(label="Seu número com DDI (ex.: +5511999999999)",
                               value=profile.get("whatsapp_phone") or "",
                               keyboard_type=ft.KeyboardType.PHONE)
        f_apikey = ft.TextField(label="Chave da CallMeBot", value=profile.get("whatsapp_apikey") or "")

        async def save_whatsapp(e):
            try:
                await call(api.save_settings, self.code, bool(f_whatsapp.value),
                           f_phone.value or "", f_apikey.value or "")
            except api.ApiError as error:
                self.toast(str(error))
                return
            self.toast("Salvo!")

        return ft.ListView([
            self.title("Avisos", "Por onde as promoções chegam até você"),
            ft.Card(content=ft.Container(padding=12, content=ft.Column([
                ft.Text("Notificações no celular (app ntfy)", weight=ft.FontWeight.BOLD),
                ft.Text("1. Instale o app ntfy pela Play Store.\n"
                        "2. Assine este canal (o botão abaixo abre o app já com ele):"),
                ft.Row([ft.Text(topic, selectable=True, weight=ft.FontWeight.BOLD, expand=True),
                        ft.IconButton(ft.Icons.CONTENT_COPY, tooltip="Copiar", on_click=copy_topic)]),
                ft.Row([ft.Button(content="Assinar no ntfy", on_click=subscribe),
                        ft.OutlinedButton(content="Enviar teste", on_click=test_notification)],
                       wrap=True),
            ]))),
            ft.Card(content=ft.Container(padding=12, content=ft.Column([
                ft.Text("WhatsApp (opcional)", weight=ft.FontWeight.BOLD),
                ft.Text("Usa o serviço gratuito CallMeBot. Para ativar, siga o passo a passo em "
                        "callmebot.com (pesquise “CallMeBot WhatsApp”): você recebe uma chave "
                        "para colar aqui. Às vezes o serviço fica lotado para novos usuários; "
                        "se for o caso, use só o ntfy.",
                        size=12),
                f_whatsapp, f_phone, f_apikey,
                ft.Button(content="Salvar WhatsApp", on_click=save_whatsapp),
            ]))),
            ft.TextButton(content="Sair da conta", icon=ft.Icons.LOGOUT, on_click=self.logout),
        ], expand=True, spacing=6)


async def main(page: ft.Page):
    page.title = APP_NAME
    page.theme_mode = ft.ThemeMode.SYSTEM
    page.theme = ft.Theme(color_scheme_seed=ft.Colors.GREEN)
    page.dark_theme = ft.Theme(color_scheme_seed=ft.Colors.GREEN)
    app = GarimpeiroApp(page)
    await app.start()


ft.run(main)
