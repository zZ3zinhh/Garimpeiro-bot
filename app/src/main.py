# Garimpeiro app: lets each person manage their own alerts and categories.
# The screens are in Portuguese because friends and family use them.
import asyncio
from datetime import datetime

import flet as ft

import api
from settings import APP_NAME

# Categories (key must match the database and bot/matcher.py): (key, emoji, label)
CATEGORIES = [
    ("computers", "💻", "Informática"),
    ("games", "🎮", "Games"),
    ("phones", "📱", "Celulares e tablets"),
    ("electronics", "📺", "Eletrônicos, áudio e vídeo"),
    ("cameras", "📷", "Câmeras e drones"),
    ("appliances", "🔌", "Eletrodomésticos"),
    ("home", "🛋️", "Casa e decoração"),
    ("tools", "🔧", "Ferramentas e jardim"),
    ("fashion_men", "👔", "Moda masculina"),
    ("fashion_women", "👗", "Moda feminina"),
    ("watches", "⌚", "Relógios e joias"),
    ("bags", "🎒", "Mochilas e malas"),
    ("kids", "🍼", "Bebês e crianças"),
    ("toys", "🧸", "Brinquedos e hobbies"),
    ("beauty", "💄", "Perfumes e beleza"),
    ("health", "🩺", "Saúde e higiene"),
    ("fitness", "💪", "Suplementos e fitness"),
    ("sports", "⚽", "Esporte e lazer"),
    ("drinks", "🍷", "Bebidas"),
    ("market", "🛒", "Supermercado"),
    ("books", "📚", "Livros e eBooks"),
    ("media", "🎬", "Filmes, música e séries"),
    ("auto", "🚗", "Automóveis"),
    ("travel", "✈️", "Viagens"),
    ("office", "🖇️", "Papelaria e escritório"),
    ("pets", "🐾", "Pets"),
]
CATEGORY_LABELS = {key: f"{emoji} {label}" for key, emoji, label in CATEGORIES}

# How good a deal must be to alert: (key, name, min discount % on Promobit, min temperature on Pelando)
LEVELS = [
    ("good", "Boas", 30, 300),
    ("great", "Muito boas", 50, 500),
    ("amazing", "Imperdíveis", 70, 1000),
]
LEVEL_HELP = {
    "good": "Avisa com mais frequência. Inclui promoções boas, mas comuns.",
    "great": "O equilíbrio ideal: só promoções realmente boas.",
    "amazing": "Raras. Só descontos enormes, quase sempre erros de preço ou queimas.",
}

# How far below the usual price counts as "absurd" (stored as the % you still pay)
ABSURD_STEPS = [(20, "20% mais barato"), (30, "30% mais barato"), (40, "40% mais barato"),
                (50, "metade do preço"), (60, "60% mais barato")]

DEFAULT_SAVED_WORDS = ["notebook", "pc gamer", "computador", "kit", "usado", "recondicionado"]

REASON_LABELS = {
    "absurd": "🔥 Promoção absurda",
    "normal": "🔔 Seu alerta",
    "category": "💸 Categoria",
}
TAB_TAGS, TAB_CATEGORIES, TAB_RECENT, TAB_SETTINGS = 0, 1, 2, 3


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


def split_words(text):
    """'a, b ,, c' -> ['a', 'b', 'c'] (lowercase, no repeats, order kept)"""
    result = []
    for word in (text or "").replace(";", ",").split(","):
        word = word.strip().lower()
        if word and word not in result:
            result.append(word)
    return result


def join_words(words):
    return ", ".join(words or [])


def format_date(iso_text):
    try:
        return datetime.fromisoformat(iso_text).astimezone().strftime("%d/%m %H:%M")
    except (ValueError, TypeError):
        return ""


def level_of(category):
    """Which level (good/great/amazing) a saved category is closest to."""
    discount = category.get("min_discount_pct") or 50
    return min(LEVELS, key=lambda level: abs(level[2] - discount))[0]


def level_numbers(level_key):
    for key, _, discount, temperature in LEVELS:
        if key == level_key:
            return discount, temperature
    return 50, 500


def level_name(level_key):
    return next(name for key, name, _, _ in LEVELS if key == level_key)


# ---------- the app ----------

class GarimpeiroApp:
    def __init__(self, page: ft.Page):
        self.page = page
        self.code = None
        self.profile = None
        self.recent = []
        self.tab = TAB_TAGS
        self.hint_done = False
        # "Services" are helpers the phone provides: saved settings, links, clipboard.
        self.prefs = ft.SharedPreferences()
        self.launcher = ft.UrlLauncher()
        self.clipboard = ft.Clipboard()
        page.services.extend([self.prefs, self.launcher, self.clipboard])

    # ----- building blocks -----

    def toast(self, message):
        self.page.show_dialog(ft.SnackBar(ft.Text(message)))

    def title(self, text, subtitle=None):
        controls = [ft.Text(text, size=26, weight=ft.FontWeight.BOLD)]
        if subtitle:
            controls.append(ft.Text(subtitle, color=ft.Colors.ON_SURFACE_VARIANT))
        return ft.Container(ft.Column(controls, spacing=4), padding=ft.Padding.only(top=8, bottom=8))

    def card(self, content, color=None):
        return ft.Card(bgcolor=color, content=ft.Container(content=content, padding=16))

    def pill(self, text):
        return ft.Container(
            content=ft.Text(text, size=12, color=ft.Colors.ON_SECONDARY_CONTAINER),
            bgcolor=ft.Colors.SECONDARY_CONTAINER,
            padding=ft.Padding.symmetric(horizontal=10, vertical=4),
            border_radius=ft.BorderRadius.all(12),
        )

    def big_button(self, text, icon, on_click):
        return ft.FilledButton(content=text, icon=icon, on_click=on_click, height=48)

    def list_view(self, items):
        # The bottom space keeps the last card clear of the navigation bar.
        return ft.ListView(items, expand=True, spacing=8,
                           padding=ft.Padding.only(left=4, right=4, bottom=24))

    def reset_screen(self):
        self.page.controls.clear()
        self.page.navigation_bar = None
        self.page.floating_action_button = None

    def show_loading(self):
        self.reset_screen()
        self.page.add(ft.Container(ft.ProgressRing(), alignment=ft.Alignment.CENTER, expand=True))
        self.page.update()

    # ----- login -----

    def show_login(self, error=None, code=""):
        self.reset_screen()
        field = ft.TextField(
            label="Código de acesso", value=code, autofocus=True,
            error=error, text_align=ft.TextAlign.CENTER,
        )

        async def enter(e):
            await self.login(field.value or "")

        field.on_submit = enter
        self.page.add(ft.SafeArea(expand=True, content=ft.Column(
            [
                ft.Text("🔍", size=72),
                ft.Text(APP_NAME, size=34, weight=ft.FontWeight.BOLD),
                ft.Text("Avisos de promoções feitos para você", color=ft.Colors.ON_SURFACE_VARIANT),
                ft.Container(height=28),
                ft.Container(field, width=300),
                ft.Text("Digite o código que você recebeu.", size=12,
                        color=ft.Colors.ON_SURFACE_VARIANT),
                ft.Container(height=4),
                ft.FilledButton(content="Entrar", on_click=enter, height=48, width=300),
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
        self.hint_done = bool(await self.prefs.get("hint_done"))
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

    def saved_words(self):
        words = self.profile.get("saved_blocked_words")
        return list(DEFAULT_SAVED_WORDS) if words is None else list(words)

    # ----- main screen with the bottom bar -----

    def render(self):
        self.reset_screen()
        page = self.page
        page.navigation_bar = ft.NavigationBar(
            selected_index=self.tab,
            on_change=self.change_tab,
            destinations=[
                ft.NavigationBarDestination(icon=ft.Icons.NOTIFICATIONS_ACTIVE, label="Alertas"),
                ft.NavigationBarDestination(icon=ft.Icons.GRID_VIEW, label="Categorias"),
                ft.NavigationBarDestination(icon=ft.Icons.LOCAL_OFFER, label="Ofertas"),
                ft.NavigationBarDestination(icon=ft.Icons.SETTINGS, label="Ajustes"),
            ],
        )
        body = [self.tags_view, self.categories_view, self.recent_view, self.settings_view][self.tab]()
        page.add(ft.SafeArea(expand=True, content=body))
        page.update()

    async def change_tab(self, e):
        self.tab = e.control.selected_index
        if self.tab == TAB_RECENT:
            await self.load_recent()
        else:
            self.render()

    def go_to_tab(self, tab):
        async def go(e):
            self.tab = tab
            self.render()
        return go

    # ----- tab: alerts (tags) -----

    def tag_pills(self, tag):
        pills = []
        if tag.get("brands"):
            pills.append(self.pill("Marca: " + join_words(tag["brands"])))
        if tag.get("keywords"):
            pills.append(self.pill("Com: " + join_words(tag["keywords"])))
        if tag.get("max_price"):
            pills.append(self.pill(f"Até {brl(tag['max_price'])}"))
        if tag.get("absurd_alert"):
            pills.append(self.pill("🔥 Avisa preço absurdo"))
        if tag.get("blocked_words"):
            pills.append(self.pill("Sem: " + join_words(tag["blocked_words"])))
        return pills

    def tags_view(self):
        tags = self.profile["tags"]
        items = [self.title(f"Olá, {self.profile['name']}!",
                            "Diga o que você procura. Quando aparecer uma promoção, você recebe um aviso.")]

        if not self.hint_done:
            async def dismiss(e):
                self.hint_done = True
                await self.prefs.set("hint_done", True)
                self.render()

            items.append(self.card(ft.Column([
                ft.Text("📲 Primeiro passo: receber os avisos", weight=ft.FontWeight.BOLD),
                ft.Text("Os avisos chegam pelo app ntfy. Instale e assine o seu canal em Ajustes."),
                ft.Row([
                    ft.FilledTonalButton(content="Abrir Ajustes", on_click=self.go_to_tab(TAB_SETTINGS)),
                    ft.TextButton(content="Já fiz isso", on_click=dismiss),
                ], wrap=True),
            ], spacing=6), color=ft.Colors.PRIMARY_CONTAINER))

        items.append(self.big_button("Novo alerta", ft.Icons.ADD, lambda e: self.open_tag_dialog()))

        if not tags:
            items.append(self.card(ft.Column([
                ft.Text("Como funciona", weight=ft.FontWeight.BOLD, size=16),
                ft.Text("1. Toque em “Novo alerta” e escreva o que você quer, "
                        "por exemplo: tênis de corrida, geladeira, fone bluetooth.\n\n"
                        "2. Se quiser, escolha a marca e o preço máximo.\n\n"
                        "3. Pronto! O Garimpeiro olha o Pelando e o Promobit o dia todo e "
                        "avisa no seu celular quando aparecer."),
            ], spacing=6)))
        for tag in tags:
            items.append(self.tag_card(tag))
        return self.list_view(items)

    def tag_card(self, tag):
        pills = self.tag_pills(tag)
        return ft.Card(content=ft.Container(padding=ft.Padding.only(left=16, top=8, bottom=14, right=4),
                                            on_click=lambda e, t=tag: self.open_tag_dialog(t),
                                            content=ft.Column([
            ft.Row([
                ft.Text(tag["text"], size=18, weight=ft.FontWeight.BOLD, expand=True),
                ft.PopupMenuButton(items=[
                    ft.PopupMenuItem(content="Editar", icon=ft.Icons.EDIT,
                                     on_click=lambda e, t=tag: self.open_tag_dialog(t)),
                    ft.PopupMenuItem(content="Apagar", icon=ft.Icons.DELETE,
                                     on_click=lambda e, t=tag: self.confirm_delete("tag", t)),
                ]),
            ]),
            ft.Row(pills, wrap=True, spacing=6, run_spacing=6) if pills
            else ft.Text("Qualquer marca, qualquer preço", size=12,
                         color=ft.Colors.ON_SURFACE_VARIANT),
        ], spacing=2)))

    def open_tag_dialog(self, tag=None):
        editing = tag is not None
        tag = tag or {}
        saved = self.saved_words()
        current_blocked = tag.get("blocked_words") or []

        f_text = ft.TextField(label="O que você quer encontrar?",
                              hint_text="ex.: tênis de corrida, geladeira, fone",
                              value=tag.get("text", ""), autofocus=not editing)
        f_keywords = ft.TextField(
            label="Mais palavras (opcional)",
            helper="Separe por vírgula. ex.: azul, 128gb",
            value=join_words(tag.get("keywords")))
        f_brands = ft.TextField(
            label="Marca (opcional)",
            helper="Qualquer uma serve. ex.: samsung, lg",
            value=join_words(tag.get("brands")))
        f_max = ft.TextField(label="Preço máximo em R$ (opcional)",
                             value=number_to_text(tag.get("max_price")),
                             keyboard_type=ft.KeyboardType.NUMBER)

        # Saved blocked words appear as checkboxes. Words that are not saved go in the text field.
        boxes = [ft.Checkbox(label=word, value=word in current_blocked) for word in saved]
        extra_blocked = [w for w in current_blocked if w not in saved]
        f_blocked = ft.TextField(label="Outras palavras (opcional)",
                                 helper="Separe por vírgula",
                                 value=join_words(extra_blocked))

        f_market = ft.TextField(label="Preço que você costuma ver",
                                helper="Opcional. Ajuda a achar o que é barato",
                                value=number_to_text(tag.get("market_price")),
                                keyboard_type=ft.KeyboardType.NUMBER,
                                disabled=not tag.get("absurd_alert"))
        current_pct = tag.get("limit_pct") or 50
        closest = min(ABSURD_STEPS, key=lambda step: abs((100 - step[0]) - current_pct))
        f_limit = ft.Dropdown(
            label="Considerar absurdo quando for",
            value=str(100 - closest[0]),
            options=[ft.DropdownOption(key=str(100 - drop), text=text) for drop, text in ABSURD_STEPS],
            disabled=not tag.get("absurd_alert"))

        def toggle_absurd(e):
            f_market.disabled = f_limit.disabled = not e.control.value
            f_market.update()
            f_limit.update()

        f_absurd = ft.Switch(label="Avisar promoção absurda 🔥", value=bool(tag.get("absurd_alert")),
                             on_change=toggle_absurd)

        state = {"saving": False}  # stops a double tap on "Salvar" from saving twice
        save_button = ft.FilledButton(content="Salvar")

        async def save(e):
            if state["saving"]:
                return
            text = (f_text.value or "").strip()
            if not text:
                f_text.error = "Escreva o que você quer encontrar"
                f_text.update()
                return
            f_text.error = None
            blocked = [b.label for b in boxes if b.value]
            for word in split_words(f_blocked.value):
                if word not in blocked:
                    blocked.append(word)
            state["saving"] = True
            save_button.disabled = True
            save_button.content = "Salvando..."
            save_button.update()
            try:
                await call(api.save_tag, self.code, tag.get("id"), text,
                           split_words(f_keywords.value), split_words(f_brands.value), blocked,
                           parse_number(f_max.value), bool(f_absurd.value),
                           parse_number(f_market.value), int(f_limit.value or 50))
            except api.ApiError as error:
                state["saving"] = False
                save_button.disabled = False
                save_button.content = "Salvar"
                save_button.update()
                self.toast(str(error))
                return
            self.page.pop_dialog()
            await self.reload()

        save_button.on_click = save

        blocked_section = [ft.Text("Não quero ver…", weight=ft.FontWeight.BOLD)]
        if boxes:
            blocked_section.append(ft.Column(boxes, spacing=0))
        blocked_section.append(f_blocked)

        self.page.show_dialog(ft.AlertDialog(
            modal=True,
            title=ft.Text("Editar alerta" if editing else "Novo alerta"),
            content=ft.Column(
                [f_text, f_keywords, f_brands, f_max,
                 ft.Divider(), *blocked_section,
                 ft.Divider(), f_absurd,
                 ft.Text("Chega com prioridade máxima quando o Promobit marcar o preço como "
                         "incrível, ou quando ficar bem abaixo do preço que você costuma ver.",
                         size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                 f_market, f_limit],
                tight=True, scroll=ft.ScrollMode.AUTO, width=340, spacing=10),
            actions=[ft.TextButton(content="Cancelar", on_click=lambda e: self.page.pop_dialog()),
                     save_button],
        ))

    # ----- tab: categories -----

    def categories_view(self):
        categories = self.profile["categories"]
        items = [self.title("Categorias",
                            "Receba as melhores promoções de um assunto inteiro, "
                            "sem precisar digitar nada."),
                 self.big_button("Seguir uma categoria", ft.Icons.ADD,
                                 lambda e: self.open_category_dialog())]
        if not categories:
            items.append(self.card(ft.Text(
                "Você ainda não segue nenhuma categoria. Que tal seguir “Casa e decoração” "
                "ou “Moda”? Você escolhe o quão boa a promoção precisa ser.")))
        for category in categories:
            items.append(self.category_card(category))
        return self.list_view(items)

    def category_card(self, category):
        label = CATEGORY_LABELS.get(category["category"], category["category"])
        level = level_of(category)
        return ft.Card(content=ft.Container(
            padding=ft.Padding.only(left=16, top=8, bottom=12, right=4),
            on_click=lambda e, c=category: self.open_category_dialog(c),
            content=ft.Column([
                ft.Row([
                    ft.Text(label, size=18, weight=ft.FontWeight.BOLD, expand=True),
                    ft.PopupMenuButton(items=[
                        ft.PopupMenuItem(content="Editar", icon=ft.Icons.EDIT,
                                         on_click=lambda e, c=category: self.open_category_dialog(c)),
                        ft.PopupMenuItem(content="Apagar", icon=ft.Icons.DELETE,
                                         on_click=lambda e, c=category: self.confirm_delete("category", c)),
                    ]),
                ]),
                ft.Row([self.pill("Promoções " + level_name(level).lower())], wrap=True),
            ], spacing=2)))

    def open_category_dialog(self, category=None):
        editing = category is not None
        category = category or {}
        f_category = ft.Dropdown(
            label="Categoria", value=category.get("category", "home"),
            options=[ft.DropdownOption(key=key, text=text) for key, text in CATEGORY_LABELS.items()],
            menu_height=360,
        )
        level_key = level_of(category) if editing else "great"
        f_level = ft.Dropdown(
            label="Quão boa a promoção precisa ser?", value=level_key,
            options=[ft.DropdownOption(key=key, text=name) for key, name, _, _ in LEVELS],
        )
        help_text = ft.Text(LEVEL_HELP[level_key], size=12, color=ft.Colors.ON_SURFACE_VARIANT)

        def level_changed(e):
            help_text.value = LEVEL_HELP.get(f_level.value, "")
            help_text.update()

        f_level.on_select = level_changed
        state = {"saving": False}
        save_button = ft.FilledButton(content="Salvar")

        async def save(e):
            if state["saving"]:
                return
            discount, temperature = level_numbers(f_level.value)
            state["saving"] = True
            save_button.disabled = True
            save_button.content = "Salvando..."
            save_button.update()
            try:
                await call(api.save_category, self.code, category.get("id"), f_category.value,
                           discount, temperature)
            except api.ApiError as error:
                state["saving"] = False
                save_button.disabled = False
                save_button.content = "Salvar"
                save_button.update()
                self.toast(str(error))
                return
            self.page.pop_dialog()
            await self.reload()

        save_button.on_click = save
        self.page.show_dialog(ft.AlertDialog(
            modal=True,
            title=ft.Text("Editar categoria" if editing else "Seguir categoria"),
            content=ft.Column(
                [f_category, f_level, help_text,
                 ft.Text("Usamos o desconto no Promobit e a temperatura (votos da "
                         "comunidade) no Pelando.", size=12, color=ft.Colors.ON_SURFACE_VARIANT)],
                tight=True, scroll=ft.ScrollMode.AUTO, width=340, spacing=10),
            actions=[ft.TextButton(content="Cancelar", on_click=lambda e: self.page.pop_dialog()),
                     save_button],
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
        items = [self.title("Ofertas encontradas", "As últimas promoções que o Garimpeiro avisou para você")]
        if not self.recent:
            items.append(self.card(ft.Text(
                "Ainda não avisamos nenhuma oferta. Assim que aparecer uma boa, ela chega no "
                "celular e fica registrada aqui.")))
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
        return self.list_view(items)

    async def open_link(self, url):
        if url:
            await self.launcher.launch_url(url)

    # ----- tab: settings -----

    def settings_view(self):
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

        # --- saved blocked words ---
        saved = self.saved_words()
        f_new_word = ft.TextField(label="Adicionar palavra", expand=True, dense=True)

        async def save_prefs(words, trusted):
            try:
                await call(api.save_preferences, self.code, words, trusted)
            except api.ApiError as error:
                self.toast(str(error))
                return False
            profile["saved_blocked_words"] = words
            profile["only_trusted_stores"] = trusted
            return True

        async def add_word(e):
            word = (f_new_word.value or "").strip().lower()
            if not word or word in saved:
                return
            if await save_prefs(saved + [word], bool(profile.get("only_trusted_stores"))):
                self.render()

        def remove_word(word):
            async def remove(e):
                if await save_prefs([w for w in saved if w != word],
                                    bool(profile.get("only_trusted_stores"))):
                    self.render()
            return remove

        f_new_word.on_submit = add_word
        word_chips = ft.Row(
            [ft.Chip(label=ft.Text(word), on_delete=remove_word(word)) for word in saved],
            wrap=True, spacing=6, run_spacing=6)

        async def toggle_trusted(e):
            await save_prefs(saved, bool(e.control.value))

        # --- WhatsApp ---
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

        return self.list_view([
            self.title("Ajustes", "Deixe o Garimpeiro do seu jeito"),

            self.card(ft.Column([
                ft.Text("📲 Avisos no celular", weight=ft.FontWeight.BOLD, size=16),
                ft.Text("Os avisos chegam pelo app ntfy (grátis).\n"
                        "1. Instale o ntfy pela Play Store.\n"
                        "2. Toque em “Assinar no ntfy” para entrar no seu canal."),
                ft.Row([ft.Text(topic, selectable=True, size=13, expand=True),
                        ft.IconButton(ft.Icons.CONTENT_COPY, tooltip="Copiar", on_click=copy_topic)]),
                ft.Row([ft.FilledButton(content="Assinar no ntfy", on_click=subscribe),
                        ft.OutlinedButton(content="Enviar teste", on_click=test_notification)],
                       wrap=True),
            ], spacing=8)),

            self.card(ft.Column([
                ft.Text("🚫 Palavras que eu costumo bloquear", weight=ft.FontWeight.BOLD, size=16),
                ft.Text("Elas aparecem como caixinhas ao criar um alerta, é só marcar. "
                        "Toque no x para remover uma.", size=12,
                        color=ft.Colors.ON_SURFACE_VARIANT),
                word_chips,
                ft.Row([f_new_word, ft.FilledTonalButton(content="Adicionar", on_click=add_word)]),
            ], spacing=8)),

            self.card(ft.Column([
                ft.Text("🛡️ Lojas", weight=ft.FontWeight.BOLD, size=16),
                ft.Switch(label="Só avisar de lojas confiáveis",
                          value=bool(profile.get("only_trusted_stores")), on_change=toggle_trusted),
                ft.Text("Considera confiáveis as lojas verificadas pelo Promobit e as grandes "
                        "lojas conhecidas. Em todo aviso há um botão para ver a reputação da "
                        "loja no Reclame Aqui.", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
            ], spacing=6)),

            ft.Card(content=ft.ExpansionTile(
                title=ft.Text("WhatsApp (opcional)", weight=ft.FontWeight.BOLD),
                subtitle=ft.Text("Pode estar indisponível"),
                controls=[ft.Container(padding=16, content=ft.Column([
                    ft.Text("Usa o serviço gratuito CallMeBot. Para ativar, siga o passo a passo em "
                            "callmebot.com (pesquise “CallMeBot WhatsApp”): você recebe uma chave "
                            "para colar aqui. Às vezes o serviço fica lotado para novos usuários; "
                            "se for o caso, use só o ntfy.", size=12),
                    f_whatsapp, f_phone, f_apikey,
                    ft.FilledButton(content="Salvar WhatsApp", on_click=save_whatsapp),
                ], spacing=8))],
            )),

            ft.TextButton(content="Sair da conta", icon=ft.Icons.LOGOUT, on_click=self.logout),
        ])


async def main(page: ft.Page):
    page.title = APP_NAME
    page.theme_mode = ft.ThemeMode.SYSTEM
    page.theme = ft.Theme(color_scheme_seed=ft.Colors.GREEN)
    page.dark_theme = ft.Theme(color_scheme_seed=ft.Colors.GREEN)
    app = GarimpeiroApp(page)
    await app.start()


ft.run(main)
