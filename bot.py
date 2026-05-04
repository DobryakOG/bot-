import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import Button, View, Modal, TextInput, Select
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
import json
import asyncio
import re

# Загружаем переменные окружения
load_dotenv()

TOKEN = os.getenv('DISCORD_TOKEN')
FAMILY_NAME = os.getenv('FAMILY_NAME', 'GLORY')
APPLICATION_CHANNEL_ID = int(os.getenv('APPLICATION_CHANNEL_ID'))
TICKET_CATEGORY_ID = int(os.getenv('TICKET_CATEGORY_ID'))
LOG_CHANNEL_ID = int(os.getenv('LOG_CHANNEL_ID'))
REVIEWER_ROLE_IDS = [int(role_id.strip()) for role_id in os.getenv('REVIEWER_ROLE_IDS', '').split(',') if role_id.strip()]
INTERVIEW_VOICE_CHANNELS = [int(ch_id.strip()) for ch_id in os.getenv('INTERVIEW_VOICE_CHANNELS', '').split(',') if ch_id.strip()]

# Настройки портфолио
PORTFOLIO_CHANNEL_ID = int(os.getenv('PORTFOLIO_CHANNEL_ID', 0)) if os.getenv('PORTFOLIO_CHANNEL_ID') else None
PORTFOLIO_CATEGORY_ID = int(os.getenv('PORTFOLIO_CATEGORY_ID', 0)) if os.getenv('PORTFOLIO_CATEGORY_ID') else None
PORTFOLIO_REVIEWER_ROLE_IDS = [int(role_id.strip()) for role_id in os.getenv('PORTFOLIO_REVIEWER_ROLE_IDS', '').split(',') if role_id.strip()]

# Настройки сборов
GATHERING_MANAGER_ROLE_IDS = [int(role_id.strip()) for role_id in os.getenv('GATHERING_MANAGER_ROLE_IDS', '').split(',') if role_id.strip()]
TIER1_ROLE_ID = int(os.getenv('TIER1_ROLE_ID', 0)) if os.getenv('TIER1_ROLE_ID') else None
TIER2_ROLE_ID = int(os.getenv('TIER2_ROLE_ID', 0)) if os.getenv('TIER2_ROLE_ID') else None
TIER3_ROLE_ID = int(os.getenv('TIER3_ROLE_ID', 0)) if os.getenv('TIER3_ROLE_ID') else None

# ID владельца бота (для админ панели)
BOT_OWNER_ID = 751806885258199121  # ЗАМЕНИТЕ НА ВАШ DISCORD ID

# Настройки логирования никнеймов
NICKNAME_LOG_CHANNEL_ID = int(os.getenv('NICKNAME_LOG_CHANNEL_ID', 0)) if os.getenv('NICKNAME_LOG_CHANNEL_ID') else None
NICKNAME_LOG_ROLE_IDS = [int(role_id.strip()) for role_id in os.getenv('NICKNAME_LOG_ROLE_IDS', '').split(',') if role_id.strip()]

# Название изображений
IMAGE_BANNER = os.getenv('IMAGE_BANNER', 'banner.png')
IMAGE_PORTFOLIO = os.getenv('IMAGE_PORTFOLIO', 'portfolio.png')

# Настройка интентов
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Хранилище данных о заявках
applications_data = {}

# Хранилище данных о портфолио
portfolio_data = {}

# Хранилище кулдаунов для кнопки "Хочу провериться" (user_id: timestamp)
portfolio_cooldowns = {}

# Хранилище данных о сборах (message_id: {data})
gatherings_data = {}

# Блокировка для предотвращения дублирования создания портфолио
portfolio_creation_lock = set()

# Файлы для сохранения данных
PORTFOLIO_DATA_FILE = 'portfolio_data.json'
COOLDOWNS_FILE = 'portfolio_cooldowns.json'
GATHERINGS_FILE = 'gatherings_data.json'

# Загрузка данных при запуске
def load_portfolio_data():
    global portfolio_data, portfolio_cooldowns, gatherings_data
    try:
        if os.path.exists(PORTFOLIO_DATA_FILE):
            with open(PORTFOLIO_DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                portfolio_data = {int(k): v for k, v in data.items()}
    except Exception as e:
        print(f'Ошибка загрузки данных портфолио: {e}')
    
    try:
        if os.path.exists(COOLDOWNS_FILE):
            with open(COOLDOWNS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                portfolio_cooldowns = {int(k): datetime.fromisoformat(v) for k, v in data.items()}
    except Exception as e:
        print(f'Ошибка загрузки кулдаунов: {e}')
    
    try:
        if os.path.exists(GATHERINGS_FILE):
            with open(GATHERINGS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                gatherings_data = {int(k): v for k, v in data.items()}
    except Exception as e:
        print(f'Ошибка загрузки данных сборов: {e}')

# Сохранение данных
def save_portfolio_data():
    try:
        with open(PORTFOLIO_DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(portfolio_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f'Ошибка сохранения данных портфолио: {e}')
    
    try:
        cooldowns_serializable = {k: v.isoformat() for k, v in portfolio_cooldowns.items()}
        with open(COOLDOWNS_FILE, 'w', encoding='utf-8') as f:
            json.dump(cooldowns_serializable, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f'Ошибка сохранения кулдаунов: {e}')

def save_gatherings_data():
    try:
        with open(GATHERINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(gatherings_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f'Ошибка сохранения данных сборов: {e}')

# Функция для получения предыдущих заявок пользователя
def get_user_previous_applications(user_id, current_app_id):
    """Возвращает список предыдущих заявок пользователя с их статусами"""
    previous = []
    for app_id, data in applications_data.items():
        if data['user_id'] == user_id and app_id != current_app_id:
            if 'log_message_id' in data and 'status' in data:
                status_emoji = '✅' if data['status'] == 'accepted' else '❌' if data['status'] == 'rejected' else '⏳'
                # Формируем ссылку на лог
                log_link = f"https://discord.com/channels/{data.get('guild_id', '@me')}/{LOG_CHANNEL_ID}/{data['log_message_id']}"
                previous.append(f"[Заявка]({log_link}) {status_emoji}")
    return previous

# Модальное окно для заполнения анкеты
class ApplicationModal(Modal, title='Подать заявку на вступление в семью'):
    name_age_nick = TextInput(
        label='ВАШЕ ИМЯ & ВОЗРАСТ В IRL & ВАШ ИГРОВОЙ НИК',
        placeholder='Дмитрий & Возраст: 54 года & Игровой никнейм: Zhmyshe',
        style=discord.TextStyle.short,
        required=True,
        max_length=200
    )
    
    experience = TextInput(
        label='ВАШ ОПЫТ НА RP ПРОЕКТАХ?',
        placeholder='Мой путь начинался с легендарного сервера FiveStar в далеком 2018 году.',
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=1000
    )
    
    shooting = TextInput(
        label='ОТКАТ СТРЕЛЬБЫ (ОБЯЗАТЕЛЕН)',
        placeholder='Откат с ГГ тяжолой винтовкой лобби 7+ людей от 5 минут',
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=500
    )
    
    lvl_online = TextInput(
        label='ВАШ ЛВЛ В ИГРЕ & ВАШ ОНЛАЙН И ЧАСОВОЙ ПОЯС',
        placeholder='10 LVL & 10 h & (+-1МСК)',
        style=discord.TextStyle.short,
        required=True,
        max_length=200
    )
    
    family_experience = TextInput(
        label='ЕСТЬ ЛИ У ВАС ОПЫТ В СЕМЬЯХ ? ГДЕ СОСТОЯЛИ?',
        placeholder='Опыт присутствует. Gucci, Uzi, Blade, Allegri',
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=1000
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        # Создаем тикет-канал
        guild = interaction.guild
        category = guild.get_channel(TICKET_CATEGORY_ID)
        
        # Создаем приватный канал
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        
        # Добавляем права для ролей рекрутеров
        for role_id in REVIEWER_ROLE_IDS:
            role = guild.get_role(role_id)
            if role:
                overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        
        ticket_channel = await guild.create_text_channel(
            name=f'👁️заявление-{interaction.user.name}',
            category=category,
            overwrites=overwrites
        )
        
        # Сохраняем данные заявки
        application_id = ticket_channel.id
        applications_data[application_id] = {
            'user_id': interaction.user.id,
            'username': interaction.user.name,
            'display_name': interaction.user.display_name,
            'user_mention': interaction.user.mention,
            'answers': {
                'name_age_nick': self.name_age_nick.value,
                'experience': self.experience.value,
                'shooting': self.shooting.value,
                'lvl_online': self.lvl_online.value,
                'family_experience': self.family_experience.value
            },
            'status': 'pending',
            'reviewer': None,
            'created_at': datetime.now().isoformat(),
            'ticket_channel_id': ticket_channel.id
        }
        
        # Получаем предыдущие заявки пользователя
        previous_apps = get_user_previous_applications(interaction.user.id, application_id)
        
        # Создаем embed с заявкой
        embed = discord.Embed(
            title='Заявление',
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        
        embed.add_field(name='ВАШЕ ИМЯ & ВОЗРАСТ В IRL & ВАШ ИГРОВОЙ НИК', value=self.name_age_nick.value, inline=False)
        embed.add_field(name='ВАШ ОПЫТ НА RP ПРОЕКТАХ?', value=self.experience.value, inline=False)
        embed.add_field(name='ОТКАТ СТРЕЛЬБЫ (ОБЯЗАТЕЛЕН)', value=self.shooting.value, inline=False)
        embed.add_field(name='ВАШ ЛВЛ В ИГРЕ & ВАШ ОНЛАЙН И ЧАСОВОЙ ПОЯС', value=self.lvl_online.value, inline=False)
        embed.add_field(name='ЕСТЬ ЛИ У ВАС ОПЫТ В СЕМЬЯХ ? ГДЕ СОСТОЯЛИ?', value=self.family_experience.value, inline=False)
        embed.add_field(name='Пользователь', value=interaction.user.mention, inline=False)
        embed.add_field(name='Username', value=interaction.user.name, inline=True)
        embed.add_field(name='ID', value=str(interaction.user.id), inline=True)
        
        # Добавляем предыдущие заявки
        if previous_apps:
            prev_text = '\n'.join(previous_apps)
            embed.add_field(name='Предыдущие заявки:', value=prev_text, inline=False)
        else:
            embed.add_field(name='Предыдущие заявки:', value='Заявок не найдено.', inline=False)
        
        embed.set_footer(text=f'Сегодня, в {datetime.now().strftime("%H:%M")}')
        
        # Создаем кнопки управления
        view = ApplicationControlView(application_id)
        
        # Формируем упоминания ролей рекрутеров
        role_mentions = []
        for role_id in REVIEWER_ROLE_IDS:
            role = guild.get_role(role_id)
            if role:
                role_mentions.append(role.mention)
        
        roles_text = ' '.join(role_mentions) if role_mentions else ''
        
        message = await ticket_channel.send(
            content=roles_text,
            embed=embed,
            view=view
        )
        
        applications_data[application_id]['message_id'] = message.id
        applications_data[application_id]['guild_id'] = guild.id
        
        # Отправляем в лог-канал
        await send_to_log(guild, application_id, interaction.user)
        
        # Уведомляем пользователя
        await interaction.followup.send(
            f'✅ Ваша заявка успешно отправлена в ваш тикет {ticket_channel.mention}!\n'
            f'Обычно заявки обрабатываются в течение 15-60 минут.',
            ephemeral=True
        )
        
        # Отправляем сообщение в тикет
        await ticket_channel.send(
            f'{interaction.user.mention}, ваша заявка принята на рассмотрение. '
            f'Пожалуйста, ожидайте ответа от наших рекрутеров.'
        )

# View с кнопкой "Заполнить анкету"
class ApplicationStartView(View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label='Заполнить анкету', style=discord.ButtonStyle.green, emoji='📧', custom_id='start_application')
    async def start_application(self, interaction: discord.Interaction, button: Button):
        modal = ApplicationModal()
        await interaction.response.send_modal(modal)

# View с кнопкой "Создать свое портфолио"
class PortfolioStartView(View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label='Создать свое портфолио', style=discord.ButtonStyle.primary, emoji='📁', custom_id='create_portfolio')
    async def create_portfolio(self, interaction: discord.Interaction, button: Button):
        user_id = interaction.user.id
        
        # Проверяем блокировку - если пользователь уже создает портфолио
        if user_id in portfolio_creation_lock:
            await interaction.response.send_message('⏳ Ваше портфолио уже создается, подождите...', ephemeral=True)
            return
        
        # Добавляем блокировку
        portfolio_creation_lock.add(user_id)
        
        try:
            guild = interaction.guild
            category = guild.get_channel(PORTFOLIO_CATEGORY_ID)
            
            if not category:
                await interaction.response.send_message('❌ Категория для портфолио не найдена!', ephemeral=True)
                return
            
            # Проверяем, есть ли уже портфолио у пользователя в данных
            for channel_id, data in portfolio_data.items():
                if data['user_id'] == user_id:
                    channel = guild.get_channel(channel_id)
                    if channel:
                        await interaction.response.send_message(
                            f'❌ У вас уже есть портфолио: {channel.mention}',
                            ephemeral=True
                        )
                        return
                    else:
                        # Канал был удален, удаляем из данных
                        del portfolio_data[channel_id]
                        save_portfolio_data()
                        break
            
            # Дополнительная проверка: ищем канал в категории по имени пользователя
            for channel in category.text_channels:
                if channel.name == f'💼{interaction.user.display_name}'.lower().replace(' ', '-'):
                    # Проверяем права доступа пользователя к каналу
                    permissions = channel.permissions_for(interaction.user)
                    if permissions.read_messages:
                        await interaction.response.send_message(
                            f'❌ У вас уже есть портфолио: {channel.mention}',
                            ephemeral=True
                        )
                        # Добавляем в данные если отсутствует
                        if channel.id not in portfolio_data:
                            portfolio_data[channel.id] = {
                                'user_id': user_id,
                                'username': interaction.user.name,
                                'display_name': interaction.user.display_name,
                                'created_at': datetime.now().isoformat()
                            }
                            save_portfolio_data()
                        return
            
            # Отправляем подтверждение сразу
            await interaction.response.send_message('⏳ Создаю ваше портфолио...', ephemeral=True)
            
            # Создаем приватный канал портфолио
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
                guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
            }
            
            # Добавляем права для ролей проверяющих
            for role_id in PORTFOLIO_REVIEWER_ROLE_IDS:
                role = guild.get_role(role_id)
                if role:
                    overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
            
            portfolio_channel = await guild.create_text_channel(
                name=f'💼{interaction.user.display_name}',
                category=category,
                overwrites=overwrites
            )
            
            # Сохраняем данные портфолио СРАЗУ после создания канала
            portfolio_data[portfolio_channel.id] = {
                'user_id': user_id,
                'username': interaction.user.name,
                'display_name': interaction.user.display_name,
                'created_at': datetime.now().isoformat()
            }
            save_portfolio_data()
            
            # Создаем приветственное сообщение с заголовком (БЕЗ изображения)
            embed = discord.Embed(
                title='Portfolio💼',
                description='Привет! Как будешь готов получить/улучшить свой тир нажми на кнопку «Хочу провериться». Удачи!',
                color=discord.Color.from_rgb(255, 105, 180)  # Розовый цвет
            )
            
            view = PortfolioCheckView()
            message = await portfolio_channel.send(embed=embed, view=view)
            
            # Закрепляем сообщение
            await message.pin()
            
            # Сохраняем ID приветственного сообщения
            portfolio_data[portfolio_channel.id]['welcome_message_id'] = message.id
            save_portfolio_data()
            
            await interaction.followup.send(
                f'✅ Ваше портфолио создано: {portfolio_channel.mention}',
                ephemeral=True
            )
        finally:
            # Убираем блокировку в любом случае
            portfolio_creation_lock.discard(user_id)

# View с кнопкой "Хочу провериться"
class PortfolioCheckView(View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label='Хочу провериться', style=discord.ButtonStyle.primary, emoji='✨', custom_id='portfolio_check')
    async def portfolio_check(self, interaction: discord.Interaction, button: Button):
        user_id = interaction.user.id
        current_time = datetime.now()
        
        # Проверяем кулдаун (72 часа = 259200 секунд)
        if user_id in portfolio_cooldowns:
            last_check = portfolio_cooldowns[user_id]
            time_passed = (current_time - last_check).total_seconds()
            cooldown_time = 72 * 3600  # 72 часа в секундах
            
            if time_passed < cooldown_time:
                remaining_time = cooldown_time - time_passed
                hours = int(remaining_time // 3600)
                minutes = int((remaining_time % 3600) // 60)
                
                await interaction.response.send_message(
                    f'⏰ Вы сможете повторно нажать эту кнопку через {hours} часов {minutes} минут.',
                    ephemeral=True
                )
                return
        
        # Обновляем время последнего использования
        portfolio_cooldowns[user_id] = current_time
        save_portfolio_data()  # Сохраняем кулдауны
        
        # Формируем упоминания ролей проверяющих
        role_mentions = []
        for role_id in PORTFOLIO_REVIEWER_ROLE_IDS:
            role = interaction.guild.get_role(role_id)
            if role:
                role_mentions.append(role.mention)
        
        roles_text = ' '.join(role_mentions) if role_mentions else ''
        
        # Создаем кнопку "Принять"
        view = PortfolioAcceptView(interaction.message.id)
        
        # Отправляем сообщение
        await interaction.response.send_message(
            content=f'{roles_text}\n\nЧеловек готов получить свой тир🧟‍♀️',
            view=view
        )

# View с кнопкой "Принять"
class PortfolioAcceptView(View):
    def __init__(self, original_message_id):
        super().__init__(timeout=None)
        self.original_message_id = original_message_id
    
    @discord.ui.button(label='Принять', style=discord.ButtonStyle.success, emoji='✅', custom_id='portfolio_accept')
    async def portfolio_accept(self, interaction: discord.Interaction, button: Button):
        # Проверяем права
        user_role_ids = [role.id for role in interaction.user.roles]
        has_permission = any(role_id in PORTFOLIO_REVIEWER_ROLE_IDS for role_id in user_role_ids)
        
        if not has_permission:
            await interaction.response.send_message('❌ У вас нет прав для выполнения этого действия.', ephemeral=True)
            return
        
        # Просто подтверждаем, не удаляем сообщение
        await interaction.response.send_message('✅ Проверка принята!', ephemeral=True)

# Модальное окно для создания сбора
class GatheringModal(Modal, title='Создать сбор'):
    gathering_name = TextInput(
        label='Название',
        placeholder='Например: Сбор на МП',
        style=discord.TextStyle.short,
        required=False,
        max_length=100
    )
    
    date = TextInput(
        label='Дата',
        placeholder='Например: 05.05.2026 20:00',
        style=discord.TextStyle.short,
        required=False,
        max_length=50
    )
    
    time = TextInput(
        label='Роли',
        placeholder='Например: Без ограничений',
        style=discord.TextStyle.short,
        required=False,
        max_length=50
    )
    
    image_url = TextInput(
        label='Изображение',
        placeholder='Ссылка на изображение (необязательно)',
        style=discord.TextStyle.short,
        required=False,
        max_length=500
    )
    
    comment = TextInput(
        label='Комментарий',
        placeholder='Дополнительная информация (необязательно)',
        style=discord.TextStyle.paragraph,
        required=False,
        max_length=1000
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        # Парсим дату и время для отсчета
        gathering_datetime = None
        if self.date.value:
            gathering_datetime = parse_datetime(self.date.value)
        
        # Проверяем валидность URL изображения
        image_url = None
        if self.image_url.value and self.image_url.value.strip():
            url = self.image_url.value.strip()
            # Проверяем что это валидный URL
            if url.startswith(('http://', 'https://')):
                image_url = url
        
        # Создаем embed для сбора с синей линией
        embed = discord.Embed(
            color=discord.Color.blue()
        )
        
        # Формируем описание
        description_parts = []
        description_parts.append(f'**Создал:** {interaction.user.mention}')
        
        if self.date.value:
            date_text = self.date.value
            # Добавляем отсчет времени если дата распознана
            if gathering_datetime:
                time_until = calculate_time_until(gathering_datetime)
                date_text += f' ({time_until})'
            description_parts.append(f'**Дата:** {date_text}')
        
        if self.time.value:
            description_parts.append(f'**Роли:** {self.time.value}')
        else:
            description_parts.append(f'**Роли:** Без ограничений')
        
        embed.description = '\n'.join(description_parts)
        
        # Добавляем заголовок как название сбора
        title = self.gathering_name.value if self.gathering_name.value else 'Сбор'
        
        # Добавляем список участников по тирам
        participants_text = self._format_participants([])
        
        # Устанавливаем изображение если указано и валидно
        if image_url:
            try:
                embed.set_image(url=image_url)
            except:
                pass  # Игнорируем если URL все равно невалиден
        
        embed.set_footer(text=datetime.now().strftime('%d.%m.%Y %H:%M'))
        
        # Создаем кнопки управления
        view = GatheringView()
        
        # Отправляем заголовок отдельно
        message = await interaction.channel.send(
            content=f'**{title}**',
            embed=embed,
            view=view
        )
        
        # Сохраняем данные сбора
        gatherings_data[message.id] = {
            'creator_id': interaction.user.id,
            'participants': [],
            'name': title,
            'date': self.date.value,
            'roles_text': self.time.value if self.time.value else 'Без ограничений',
            'comment': self.comment.value,
            'image_url': image_url,
            'datetime': gathering_datetime.isoformat() if gathering_datetime else None,
            'channel_id': interaction.channel.id
        }
        save_gatherings_data()
        
        await interaction.followup.send('✅ Сбор создан!', ephemeral=True)
    
    def _format_participants(self, participants):
        """Форматирует список участников по тирам"""
        if not participants:
            return 'Пока никого нет'
        
        tier1_users = []
        tier2_users = []
        tier3_users = []
        other_users = []
        
        for user_data in participants:
            user_mention = user_data['mention']
            user_roles = user_data.get('roles', [])
            
            if TIER1_ROLE_ID and TIER1_ROLE_ID in user_roles:
                tier1_users.append(user_mention)
            elif TIER2_ROLE_ID and TIER2_ROLE_ID in user_roles:
                tier2_users.append(user_mention)
            elif TIER3_ROLE_ID and TIER3_ROLE_ID in user_roles:
                tier3_users.append(user_mention)
            else:
                other_users.append(user_mention)
        
        result = []
        if tier1_users:
            result.append('**1 Тир:**\n' + '\n'.join(tier1_users))
        if tier2_users:
            result.append('**2 Тир:**\n' + '\n'.join(tier2_users))
        if tier3_users:
            result.append('**3 Тир:**\n' + '\n'.join(tier3_users))
        if other_users:
            result.append('**Другие:**\n' + '\n'.join(other_users))
        
        return '\n\n'.join(result) if result else 'Пока никого нет'

# View с кнопками для сбора
class GatheringView(View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label='Присоединиться к сбору', style=discord.ButtonStyle.success, emoji='➕', custom_id='gathering_join')
    async def join_button(self, interaction: discord.Interaction, button: Button):
        message_id = interaction.message.id
        
        if message_id not in gatherings_data:
            await interaction.response.send_message('❌ Данные сбора не найдены.', ephemeral=True)
            return
        
        gathering = gatherings_data[message_id]
        user_id = interaction.user.id
        
        # Проверяем, не записан ли уже пользователь
        if any(p['user_id'] == user_id for p in gathering['participants']):
            await interaction.response.send_message('✅ Вы уже записаны на сбор!', ephemeral=True)
            return
        
        # Получаем роли пользователя
        user_roles = [role.id for role in interaction.user.roles]
        
        # Добавляем пользователя с информацией о ролях
        gathering['participants'].append({
            'user_id': user_id,
            'mention': interaction.user.mention,
            'display_name': interaction.user.display_name,
            'roles': user_roles
        })
        save_gatherings_data()
        
        # Обновляем embed
        await update_gathering_embed(interaction.message, gathering)
        
        await interaction.response.send_message('✅ Вы успешно присоединились к сбору!', ephemeral=True)
    
    @discord.ui.button(label='Выйти со сбора', style=discord.ButtonStyle.danger, emoji='➖', custom_id='gathering_leave')
    async def leave_button(self, interaction: discord.Interaction, button: Button):
        message_id = interaction.message.id
        
        if message_id not in gatherings_data:
            await interaction.response.send_message('❌ Данные сбора не найдены.', ephemeral=True)
            return
        
        gathering = gatherings_data[message_id]
        user_id = interaction.user.id
        
        # Проверяем, записан ли пользователь
        participant = next((p for p in gathering['participants'] if p['user_id'] == user_id), None)
        
        if not participant:
            await interaction.response.send_message('❌ Вы не были присоединены к сбору.', ephemeral=True)
            return
        
        # Удаляем пользователя
        gathering['participants'].remove(participant)
        save_gatherings_data()
        
        # Обновляем embed
        await update_gathering_embed(interaction.message, gathering)
        
        await interaction.response.send_message('✅ Вы вышли из сбора.', ephemeral=True)
    
    @discord.ui.button(label='Админ панель', style=discord.ButtonStyle.primary, emoji='🔧', custom_id='gathering_admin')
    async def admin_button(self, interaction: discord.Interaction, button: Button):
        message_id = interaction.message.id
        
        if message_id not in gatherings_data:
            await interaction.response.send_message('❌ Данные сбора не найдены.', ephemeral=True)
            return
        
        gathering = gatherings_data[message_id]
        
        # Проверяем права (создатель или администратор)
        is_creator = interaction.user.id == gathering['creator_id']
        is_admin = interaction.user.guild_permissions.administrator
        
        if not (is_creator or is_admin):
            await interaction.response.send_message('❌ У вас нет прав для управления этим сбором.', ephemeral=True)
            return
        
        # Создаем админ панель
        view = GatheringAdminView(message_id)
        await interaction.response.send_message('🔧 **Админ панель сбора**', view=view, ephemeral=True)

# View для админ панели
class GatheringAdminView(View):
    def __init__(self, message_id):
        super().__init__(timeout=60)
        self.message_id = message_id
    
    @discord.ui.button(label='Вписать участника', style=discord.ButtonStyle.success, emoji='➕')
    async def add_button(self, interaction: discord.Interaction, button: Button):
        if self.message_id not in gatherings_data:
            await interaction.response.send_message('❌ Данные сбора не найдены.', ephemeral=True)
            return
        
        gathering = gatherings_data[self.message_id]
        
        # Получаем всех участников канала
        channel = interaction.channel
        members = [m for m in channel.members if not m.bot and m.id != gathering['creator_id']]
        
        # Фильтруем тех, кто еще не вписан
        already_joined = [p['user_id'] for p in gathering['participants']]
        available_members = [m for m in members if m.id not in already_joined]
        
        if not available_members:
            await interaction.response.send_message('❌ Все участники канала уже вписаны в сбор.', ephemeral=True)
            return
        
        # Создаем селект с доступными участниками
        options = []
        for member in available_members[:25]:  # Discord лимит 25
            options.append(discord.SelectOption(
                label=member.display_name,
                value=str(member.id),
                description=f'@{member.name}'
            ))
        
        select = Select(placeholder='Выберите участника для добавления', options=options)
        
        async def select_callback(select_interaction: discord.Interaction):
            user_id = int(select_interaction.data['values'][0])
            member = interaction.guild.get_member(user_id)
            
            if member:
                # Получаем роли пользователя
                user_roles = [role.id for role in member.roles]
                
                # Добавляем пользователя
                gathering['participants'].append({
                    'user_id': user_id,
                    'mention': member.mention,
                    'display_name': member.display_name,
                    'roles': user_roles
                })
                save_gatherings_data()
                
                # Обновляем embed
                message = await interaction.channel.fetch_message(self.message_id)
                await update_gathering_embed(message, gathering)
                
                await select_interaction.response.send_message(
                    f'✅ {member.mention} добавлен в сбор.',
                    ephemeral=True
                )
        
        select.callback = select_callback
        view = View(timeout=60)
        view.add_item(select)
        
        await interaction.response.send_message('Выберите участника:', view=view, ephemeral=True)
    
    @discord.ui.button(label='Выписать участника', style=discord.ButtonStyle.danger, emoji='👤')
    async def kick_button(self, interaction: discord.Interaction, button: Button):
        if self.message_id not in gatherings_data:
            await interaction.response.send_message('❌ Данные сбора не найдены.', ephemeral=True)
            return
        
        gathering = gatherings_data[self.message_id]
        
        if not gathering['participants']:
            await interaction.response.send_message('❌ В сборе нет участников.', ephemeral=True)
            return
        
        # Создаем селект с участниками
        options = []
        guild = interaction.guild
        for participant in gathering['participants'][:25]:  # Discord лимит 25
            user_id = participant['user_id']
            member = guild.get_member(user_id)
            if member:
                options.append(discord.SelectOption(
                    label=member.display_name,
                    value=str(user_id),
                    description=f'@{member.name}'
                ))
        
        if not options:
            await interaction.response.send_message('❌ Не удалось загрузить список участников.', ephemeral=True)
            return
        
        select = Select(placeholder='Выберите участника для удаления', options=options)
        
        async def select_callback(select_interaction: discord.Interaction):
            user_id = int(select_interaction.data['values'][0])
            
            # Находим и удаляем участника
            participant = next((p for p in gathering['participants'] if p['user_id'] == user_id), None)
            if participant:
                gathering['participants'].remove(participant)
                save_gatherings_data()
            
            # Обновляем embed
            message = await interaction.channel.fetch_message(self.message_id)
            await update_gathering_embed(message, gathering)
            
            member = guild.get_member(user_id)
            await select_interaction.response.send_message(
                f'✅ {member.mention} удален из сбора.',
                ephemeral=True
            )
        
        select.callback = select_callback
        view = View(timeout=60)
        view.add_item(select)
        
        await interaction.response.send_message('Выберите участника:', view=view, ephemeral=True)
    
    @discord.ui.button(label='Упомянуть', style=discord.ButtonStyle.primary, emoji='📢')
    async def mention_button(self, interaction: discord.Interaction, button: Button):
        if self.message_id not in gatherings_data:
            await interaction.response.send_message('❌ Данные сбора не найдены.', ephemeral=True)
            return
        
        gathering = gatherings_data[self.message_id]
        
        if not gathering['participants']:
            await interaction.response.send_message('❌ В сборе нет участников для упоминания.', ephemeral=True)
            return
        
        # Формируем список упоминаний
        mentions = [p['mention'] for p in gathering['participants']]
        mentions_text = ' '.join(mentions)
        
        # Отправляем в канал
        await interaction.channel.send(
            f'{mentions_text}\n\n📢 **Напоминание о сборе:** {gathering["name"]}\n'
            f'Не забудьте подготовиться!'
        )
        
        # Отправляем в ЛС каждому участнику
        guild = interaction.guild
        sent_count = 0
        for participant in gathering['participants']:
            member = guild.get_member(participant['user_id'])
            if member:
                try:
                    await member.send(
                        f'{member.mention} 📢 **Напоминание о сборе:** {gathering["name"]}\n\n'
                        f'Дата: {gathering.get("date", "Не указана")}\n'
                        f'Не забудьте подготовиться!'
                    )
                    sent_count += 1
                except:
                    pass
        
        await interaction.response.send_message(
            f'✅ Участники упомянуты в канале. ЛС отправлено: {sent_count}/{len(gathering["participants"])}',
            ephemeral=True
        )
    
    @discord.ui.button(label='Пересоздать', style=discord.ButtonStyle.secondary, emoji='🔄')
    async def recreate_button(self, interaction: discord.Interaction, button: Button):
        if self.message_id not in gatherings_data:
            await interaction.response.send_message('❌ Данные сбора не найдены.', ephemeral=True)
            return
        
        gathering = gatherings_data[self.message_id]
        
        # Парсим дату и время для отсчета
        gathering_datetime = None
        if gathering.get('datetime'):
            gathering_datetime = datetime.fromisoformat(gathering['datetime'])
        
        # Создаем новый embed
        embed = discord.Embed(color=discord.Color.blue())
        
        description_parts = []
        description_parts.append(f'**Создал:** {interaction.user.mention}')
        
        if gathering.get('date'):
            date_text = gathering['date']
            if gathering_datetime:
                time_until = calculate_time_until(gathering_datetime)
                date_text += f' ({time_until})'
            description_parts.append(f'**Дата:** {date_text}')
        
        description_parts.append(f'**Роли:** {gathering.get("roles_text", "Без ограничений")}')
        
        embed.description = '\n'.join(description_parts)
        
        if gathering.get('image_url'):
            embed.set_image(url=gathering['image_url'])
        
        embed.set_footer(text=datetime.now().strftime('%d.%m.%Y %H:%M'))
        
        view = GatheringView()
        
        # Отправляем новое сообщение
        channel = interaction.guild.get_channel(gathering.get('channel_id', interaction.channel.id))
        message = await channel.send(
            content=f'**{gathering["name"]}**',
            embed=embed,
            view=view
        )
        
        # Сохраняем новый сбор
        gatherings_data[message.id] = {
            'creator_id': interaction.user.id,
            'participants': [],
            'name': gathering['name'],
            'date': gathering.get('date'),
            'roles_text': gathering.get('roles_text', 'Без ограничений'),
            'comment': gathering.get('comment'),
            'image_url': gathering.get('image_url'),
            'datetime': gathering.get('datetime'),
            'channel_id': channel.id
        }
        save_gatherings_data()
        
        await interaction.response.send_message(f'✅ Сбор пересоздан: {message.jump_url}', ephemeral=True)
    
    @discord.ui.button(label='Удалить', style=discord.ButtonStyle.danger, emoji='🗑️')
    async def delete_button(self, interaction: discord.Interaction, button: Button):
        if self.message_id not in gatherings_data:
            await interaction.response.send_message('❌ Данные сбора не найдены.', ephemeral=True)
            return
        
        # Удаляем из данных
        del gatherings_data[self.message_id]
        save_gatherings_data()
        
        # Удаляем сообщение
        try:
            message = await interaction.channel.fetch_message(self.message_id)
            await message.delete()
            await interaction.response.send_message('✅ Сбор удален.', ephemeral=True)
        except:
            await interaction.response.send_message('✅ Данные сбора удалены.', ephemeral=True)

# Функция обновления embed сбора
async def update_gathering_embed(message, gathering):
    embed = message.embeds[0]
    
    # Формируем список участников по тирам
    tier1_users = []
    tier2_users = []
    tier3_users = []
    other_users = []
    
    for participant in gathering['participants']:
        user_mention = participant['mention']
        user_roles = participant.get('roles', [])
        
        if TIER1_ROLE_ID and TIER1_ROLE_ID in user_roles:
            tier1_users.append(user_mention)
        elif TIER2_ROLE_ID and TIER2_ROLE_ID in user_roles:
            tier2_users.append(user_mention)
        elif TIER3_ROLE_ID and TIER3_ROLE_ID in user_roles:
            tier3_users.append(user_mention)
        else:
            other_users.append(user_mention)
    
    # Формируем текст участников
    participants_parts = []
    total_count = len(gathering['participants'])
    
    if tier1_users:
        participants_parts.append(f'**1 Тир:**\n' + '\n'.join(tier1_users))
    if tier2_users:
        participants_parts.append(f'**2 Тир:**\n' + '\n'.join(tier2_users))
    if tier3_users:
        participants_parts.append(f'**3 Тир:**\n' + '\n'.join(tier3_users))
    if other_users:
        participants_parts.append(f'**Другие:**\n' + '\n'.join(other_users))
    
    participants_text = '\n\n'.join(participants_parts) if participants_parts else 'Пока никого нет'
    
    # Обновляем описание с добавлением участников
    description_parts = []
    
    # Извлекаем информацию из текущего описания
    current_desc = embed.description.split('\n')
    for line in current_desc:
        if line.startswith('**Создал:**') or line.startswith('**Дата:**') or line.startswith('**Роли:**'):
            # Обновляем отсчет времени в дате если есть
            if line.startswith('**Дата:**') and gathering.get('datetime'):
                gathering_datetime = datetime.fromisoformat(gathering['datetime'])
                date_text = gathering.get('date', '')
                time_until = calculate_time_until(gathering_datetime)
                description_parts.append(f'**Дата:** {date_text} ({time_until})')
            else:
                description_parts.append(line)
    
    # Добавляем счетчик участников
    description_parts.append(f'\n**Участники ({total_count}/25)**')
    description_parts.append(participants_text)
    
    embed.description = '\n'.join(description_parts)
    
    await message.edit(embed=embed)

# Функция парсинга даты и времени
def parse_datetime(date_string):
    """Парсит дату в формате '05.05.2026 20:00' или подобном"""
    try:
        # Пробуем разные форматы
        formats = [
            '%d.%m.%Y %H:%M',
            '%d.%m.%Y %H:%M:%S',
            '%d/%m/%Y %H:%M',
            '%Y-%m-%d %H:%M'
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(date_string, fmt)
            except:
                continue
        
        return None
    except:
        return None

# Функция расчета времени до события
def calculate_time_until(target_datetime):
    """Возвращает строку с отсчетом времени"""
    now = datetime.now()
    delta = target_datetime - now
    
    if delta.total_seconds() < 0:
        return 'началось'
    
    days = delta.days
    hours, remainder = divmod(delta.seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    
    parts = []
    if days > 0:
        parts.append(f'{days} дн.')
    if hours > 0:
        parts.append(f'{hours} ч.')
    if minutes > 0 or not parts:
        parts.append(f'{minutes} мин.')
    
    time_str = ' '.join(parts)
    return f'{time_str} назад' if delta.total_seconds() < 0 else time_str

# Команда /сбор
@bot.tree.command(name='сбор', description='Создать сбор на МП или другое мероприятие')
async def gathering_command(interaction: discord.Interaction):
    # Проверяем права пользователя
    user_role_ids = [role.id for role in interaction.user.roles]
    has_permission = any(role_id in GATHERING_MANAGER_ROLE_IDS for role_id in user_role_ids)
    is_admin = interaction.user.guild_permissions.administrator
    
    if not (has_permission or is_admin):
        await interaction.response.send_message(
            '❌ У вас нет прав для создания сборов.',
            ephemeral=True
        )
        return
    
    modal = GatheringModal()
    await interaction.response.send_modal(modal)

# View с кнопками управления заявкой
class ApplicationControlView(View):
    def __init__(self, application_id):
        super().__init__(timeout=None)
        self.application_id = application_id
    
    @discord.ui.button(label='Принять', style=discord.ButtonStyle.success, emoji='✅', custom_id='accept')
    async def accept_button(self, interaction: discord.Interaction, button: Button):
        if not await check_reviewer_permission(interaction):
            return
        
        app_data = applications_data.get(self.application_id)
        if not app_data:
            await interaction.response.send_message('❌ Данные заявки не найдены.', ephemeral=True)
            return
        
        user = interaction.guild.get_member(app_data['user_id'])
        if not user:
            await interaction.response.send_message('❌ Пользователь не найден на сервере.', ephemeral=True)
            return
        
        # Обновляем статус
        app_data['status'] = 'accepted'
        app_data['reviewer'] = interaction.user.mention
        
        # Отправляем в ЛС
        try:
            await user.send(f'{user.mention} 🎉 Поздравляем! Ваша заявка была принята!\nРекрутер: {interaction.user.mention}')
        except:
            pass
        
        # Обновляем лог
        await update_log(interaction.guild, self.application_id, 'accepted', interaction.user)
        
        await interaction.response.send_message(f'✅ Заявка принята! Пользователь {user.mention} уведомлен.', ephemeral=False)
        
        # Удаляем канал через 5 секунд
        await interaction.channel.send('Этот канал будет удален через 5 секунд...')
        import asyncio
        await asyncio.sleep(5)
        await interaction.channel.delete()
    
    @discord.ui.button(label='Взять на рассмотрение', style=discord.ButtonStyle.primary, emoji='👀', custom_id='review')
    async def review_button(self, interaction: discord.Interaction, button: Button):
        if not await check_reviewer_permission(interaction):
            return
        
        app_data = applications_data.get(self.application_id)
        if not app_data:
            await interaction.response.send_message('❌ Данные заявки не найдены.', ephemeral=True)
            return
        
        # Обновляем статус
        app_data['status'] = 'reviewing'
        app_data['reviewer'] = interaction.user.mention
        app_data['reviewer_name'] = interaction.user.name
        
        user = interaction.guild.get_member(app_data['user_id'])
        
        # Отправляем сообщение в канал
        await interaction.response.send_message(
            f'{user.mention if user else app_data["user_mention"]} {interaction.user.mention} взял(а) вашу заявку на рассмотрение',
            ephemeral=False
        )
        
        # Отправляем в ЛС с изображением
        if user:
            try:
                embed = discord.Embed(
                    title='Рассмотрение заявки.',
                    description=f'{user.mention}\n\nВаша заявка в **{FAMILY_NAME}** **взята на рассмотрение**!',
                    color=discord.Color.blue()
                )
                
                # Добавляем информацию
                ticket_channel = interaction.guild.get_channel(self.application_id)
                embed.add_field(
                    name='',
                    value=(
                        f'Ссылка на заявку: {ticket_channel.mention if ticket_channel else "неизвестно"}\n'
                        f'ID Дискорд сервера: {interaction.guild.id}\n'
                        f'Дата события: {discord.utils.format_dt(datetime.now(), "R")}'
                    ),
                    inline=False
                )
                
                await user.send(embed=embed)
            except Exception as e:
                print(f'Не удалось отправить ЛС: {e}')
        
        # Обновляем лог (меняем цвет на оранжевый)
        await update_log(interaction.guild, self.application_id, 'reviewing', interaction.user)
    
    @discord.ui.button(label='Вызвать на обзвон', style=discord.ButtonStyle.primary, emoji='🔊', custom_id='call')
    async def call_button(self, interaction: discord.Interaction, button: Button):
        if not await check_reviewer_permission(interaction):
            return
        
        app_data = applications_data.get(self.application_id)
        if app_data:
            app_data['reviewer'] = interaction.user.mention
            app_data['reviewer_name'] = interaction.user.name
        
        # Создаем селект с голосовыми каналами
        view = VoiceChannelSelectView(self.application_id, interaction.user, interaction.guild)
        await interaction.response.send_message('Выберите голосовой канал для собеседования:', view=view, ephemeral=True)
    
    @discord.ui.button(label='Отклонить', style=discord.ButtonStyle.danger, emoji='❌', custom_id='reject')
    async def reject_button(self, interaction: discord.Interaction, button: Button):
        if not await check_reviewer_permission(interaction):
            return
        
        # Открываем модальное окно для причины отказа
        modal = RejectReasonModal(self.application_id)
        await interaction.response.send_modal(modal)

# Модальное окно для причины отказа
class RejectReasonModal(Modal, title='Причина отказа'):
    reason = TextInput(
        label='Укажите причину отказа',
        placeholder='Введите причину отказа...',
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=1000
    )
    
    def __init__(self, application_id):
        super().__init__()
        self.application_id = application_id
    
    async def on_submit(self, interaction: discord.Interaction):
        app_data = applications_data.get(self.application_id)
        if not app_data:
            await interaction.response.send_message('❌ Данные заявки не найдены.', ephemeral=True)
            return
        
        user = interaction.guild.get_member(app_data['user_id'])
        
        # Обновляем статус
        app_data['status'] = 'rejected'
        app_data['reviewer'] = interaction.user.mention
        app_data['reviewer_name'] = interaction.user.name
        app_data['reject_reason'] = self.reason.value
        
        # Отправляем в ЛС с изображением
        if user:
            try:
                embed = discord.Embed(
                    title='Отклонение заявки',
                    description=f'{user.mention}\n\nВаша заявка в **{FAMILY_NAME}** **отклонена**!',
                    color=discord.Color.red()
                )
                
                # Добавляем информацию
                embed.add_field(
                    name='',
                    value=(
                        f'ID Дискорд сервера: {interaction.guild.id}\n'
                        f'Дата отклонения: {discord.utils.format_dt(datetime.now(), "R")}\n\n'
                        f'Лог вашей заявки был записан в нашу базу данных.'
                    ),
                    inline=False
                )
                
                await user.send(embed=embed)
            except Exception as e:
                print(f'Не удалось отправить ЛС: {e}')
        
        # Обновляем лог
        await update_log(interaction.guild, self.application_id, 'rejected', interaction.user, self.reason.value)
        
        await interaction.response.send_message(
            f'❌ Заявка отклонена. Пользователь уведомлен.\n**Причина:** {self.reason.value}',
            ephemeral=False
        )
        
        # Удаляем канал через 5 секунд
        await interaction.channel.send('Этот канал будет удален через 5 секунд...')
        import asyncio
        await asyncio.sleep(5)
        await interaction.channel.delete()

# View для выбора голосового канала
class VoiceChannelSelectView(View):
    def __init__(self, application_id, reviewer, guild):
        super().__init__(timeout=60)
        self.application_id = application_id
        self.reviewer = reviewer
        self.guild = guild
        
        # Создаем селект с каналами используя их названия
        options = []
        for channel_id in INTERVIEW_VOICE_CHANNELS[:25]:  # Discord лимит 25 опций
            channel = guild.get_channel(channel_id)
            if channel:
                options.append(discord.SelectOption(
                    label=channel.name,
                    value=str(channel_id),
                    emoji='🔊'
                ))
        
        if options:
            select = Select(placeholder='Выберите голосовой канал для обзвона', options=options)
            select.callback = self.select_callback
            self.add_item(select)
    
    async def select_callback(self, interaction: discord.Interaction):
        channel_id = int(interaction.data['values'][0])
        channel = interaction.guild.get_channel(channel_id)
        
        app_data = applications_data.get(self.application_id)
        if not app_data:
            await interaction.response.send_message('❌ Данные заявки не найдены.', ephemeral=True)
            return
        
        user = interaction.guild.get_member(app_data['user_id'])
        
        if channel and user:
            # Создаем embed с информацией о канале
            channel_embed = discord.Embed(
                title=f'🔊 • {channel.name}',
                description=f'в {FAMILY_NAME} 🎀',
                color=discord.Color.blue()
            )
            
            # Создаем кнопку для присоединения
            join_view = View(timeout=None)
            join_button = Button(
                label='Присоединиться к голосовому каналу',
                style=discord.ButtonStyle.success,
                emoji='🔊'
            )
            join_view.add_item(join_button)
            
            # Отправляем сообщение в тикет с упоминанием канала
            await interaction.channel.send(
                f'{user.mention} был вызван на **обзвон** модератором {self.reviewer.mention} в канал 🔊 • {channel.name}\n'
                f'🔊 • {channel.name}',
                embed=channel_embed,
                view=join_view
            )
            
            # Отправляем в ЛС
            try:
                embed = discord.Embed(
                    title='Приглашение на обзвон',
                    description=f'{user.mention}\n\nВы были вызваны на **обзвон**!',
                    color=discord.Color.blue()
                )
                
                embed.add_field(
                    name='',
                    value=(
                        f'Вас приглашают присоединиться к голосовому каналу: {channel.mention}\n'
                        f'ID Дискорд сервера: {interaction.guild.id}\n'
                        f'Дата события: {discord.utils.format_dt(datetime.now(), "R")}'
                    ),
                    inline=False
                )
                
                await user.send(embed=embed)
            except Exception as e:
                print(f'Не удалось отправить ЛС: {e}')
            
            await interaction.response.send_message(f'✅ Пользователь вызван в {channel.mention}', ephemeral=True)
        else:
            await interaction.response.send_message('❌ Канал или пользователь не найден.', ephemeral=True)

# Проверка прав рекрутера
async def check_reviewer_permission(interaction: discord.Interaction) -> bool:
    user_role_ids = [role.id for role in interaction.user.roles]
    has_permission = any(role_id in REVIEWER_ROLE_IDS for role_id in user_role_ids)
    
    if not has_permission:
        await interaction.response.send_message('❌ У вас нет прав для выполнения этого действия.', ephemeral=True)
        return False
    return True

# Отправка в лог-канал
async def send_to_log(guild, application_id, user):
    log_channel = guild.get_channel(LOG_CHANNEL_ID)
    if not log_channel:
        return
    
    app_data = applications_data[application_id]
    answers = app_data['answers']
    
    embed = discord.Embed(
        title='Ваш ник в игре',
        description=answers['name_age_nick'].split('&')[-1].strip() if '&' in answers['name_age_nick'] else answers['name_age_nick'],
        color=discord.Color.blue(),  # Синий = на рассмотрении
        timestamp=datetime.now()
    )
    
    embed.add_field(name='Статик #', value=answers['name_age_nick'].split('&')[-1].strip() if '&' in answers['name_age_nick'] else 'Не указан', inline=False)
    embed.add_field(name='Возраст ООС', value=answers['name_age_nick'].split('&')[1].strip() if len(answers['name_age_nick'].split('&')) > 1 else 'Не указан', inline=False)
    embed.add_field(name='Откат стрельбы ( без отката не принимаем!)', value=answers['shooting'], inline=False)
    embed.add_field(name='Семьи в которых вы были.', value=answers['family_experience'], inline=False)
    embed.add_field(name='Пользователь', value=user.mention, inline=False)
    embed.add_field(name='Username', value=user.name, inline=True)
    embed.add_field(name='ID', value=str(user.id), inline=True)
    
    embed.set_footer(text=f'Сегодня, в {datetime.now().strftime("%H:%M")}')
    
    message = await log_channel.send(embed=embed)
    app_data['log_message_id'] = message.id

# Обновление лога
async def update_log(guild, application_id, status, reviewer, reason=None):
    log_channel = guild.get_channel(LOG_CHANNEL_ID)
    if not log_channel:
        return
    
    app_data = applications_data.get(application_id)
    if not app_data or 'log_message_id' not in app_data:
        return
    
    try:
        message = await log_channel.fetch_message(app_data['log_message_id'])
        embed = message.embeds[0]
        
        # Меняем цвет в зависимости от статуса
        if status == 'accepted':
            embed.color = discord.Color.green()
            embed.add_field(name='Кого', value=app_data['user_mention'], inline=True)
            embed.add_field(name='Принял', value=reviewer.mention, inline=True)
            embed.timestamp = datetime.now()
        elif status == 'rejected':
            embed.color = discord.Color.red()
            embed.add_field(name='Кого', value=app_data['user_mention'], inline=True)
            embed.add_field(name='Отклонил', value=reviewer.mention, inline=True)
            if reason:
                embed.add_field(name='Причина', value=reason, inline=False)
            embed.timestamp = datetime.now()
        elif status == 'reviewing':
            embed.color = discord.Color.orange()
            embed.add_field(name='Кого', value=app_data['user_mention'], inline=True)
            embed.add_field(name='Вызвал на обзвон', value=reviewer.mention, inline=True)
            embed.timestamp = datetime.now()
        
        await message.edit(embed=embed)
    except Exception as e:
        print(f'Ошибка обновления лога: {e}')

@bot.event
async def on_message(message):
    """Событие при получении сообщения"""
    # Игнорируем сообщения от самого бота
    if message.author == bot.user:
        return
    
    # Проверяем, это ЛС от владельца бота
    if isinstance(message.channel, discord.DMChannel) and message.author.id == BOT_OWNER_ID:
        if message.content.lower() in ['админ', 'admin', 'панель', '!админ', '!admin', '!панель']:
            await show_admin_panel(message.author)
            return
    
    # Обрабатываем команды
    await bot.process_commands(message)

# Команда !админ для вызова панели
@bot.command(name='админ', aliases=['admin', 'панель'])
async def admin_command(ctx):
    """Команда для вызова админ панели (только в ЛС владельца)"""
    # Проверяем что это ЛС и от владельца
    if isinstance(ctx.channel, discord.DMChannel) and ctx.author.id == BOT_OWNER_ID:
        await show_admin_panel(ctx.author)
    elif not isinstance(ctx.channel, discord.DMChannel):
        await ctx.send('❌ Эта команда доступна только в личных сообщениях.', delete_after=5)
        try:
            await ctx.message.delete()
        except:
            pass
    else:
        await ctx.send('❌ У вас нет прав для использования этой команды.')


# Функция показа админ панели
async def show_admin_panel(user):
    embed = discord.Embed(
        title='🔧 Админ панель бота',
        description='Управление ботом',
        color=discord.Color.gold()
    )
    
    embed.add_field(
        name='Доступные функции:',
        value='• Выбор сервера\n• Получение списка ролей',
        inline=False
    )
    
    view = AdminPanelView()
    await user.send(embed=embed, view=view)

# View для админ панели
class AdminPanelView(View):
    def __init__(self):
        super().__init__(timeout=300)
    
    @discord.ui.button(label='Выбрать сервер', style=discord.ButtonStyle.primary, emoji='🏠')
    async def select_server(self, interaction: discord.Interaction, button: Button):
        # Получаем список серверов где бот имеет права администратора
        admin_guilds = []
        for guild in bot.guilds:
            bot_member = guild.get_member(bot.user.id)
            if bot_member and bot_member.guild_permissions.administrator:
                admin_guilds.append(guild)
        
        if not admin_guilds:
            await interaction.response.send_message('❌ Бот не имеет прав администратора ни на одном сервере.', ephemeral=True)
            return
        
        # Создаем селект с серверами
        options = []
        for guild in admin_guilds[:25]:  # Discord лимит 25
            options.append(discord.SelectOption(
                label=guild.name,
                value=str(guild.id),
                description=f'ID: {guild.id}'
            ))
        
        select = Select(placeholder='Выберите сервер', options=options)
        
        async def select_callback(select_interaction: discord.Interaction):
            guild_id = int(select_interaction.data['values'][0])
            guild = bot.get_guild(guild_id)
            
            if guild:
                embed = discord.Embed(
                    title=f'Сервер: {guild.name}',
                    color=discord.Color.blue()
                )
                embed.add_field(name='ID сервера', value=str(guild.id), inline=False)
                embed.add_field(name='Участников', value=str(guild.member_count), inline=True)
                embed.add_field(name='Ролей', value=str(len(guild.roles)), inline=True)
                
                if guild.icon:
                    embed.set_thumbnail(url=guild.icon.url)
                
                # Создаем кнопку для получения ролей
                view = ServerActionsView(guild_id)
                await select_interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        
        select.callback = select_callback
        view = View(timeout=60)
        view.add_item(select)
        
        await interaction.response.send_message('Выберите сервер:', view=view, ephemeral=True)
    
    @discord.ui.button(label='Получить все роли', style=discord.ButtonStyle.success, emoji='📋')
    async def get_all_roles(self, interaction: discord.Interaction, button: Button):
        # Получаем список серверов где бот имеет права администратора
        admin_guilds = []
        for guild in bot.guilds:
            bot_member = guild.get_member(bot.user.id)
            if bot_member and bot_member.guild_permissions.administrator:
                admin_guilds.append(guild)
        
        if not admin_guilds:
            await interaction.response.send_message('❌ Бот не имеет прав администратора ни на одном сервере.', ephemeral=True)
            return
        
        # Создаем селект с серверами
        options = []
        for guild in admin_guilds[:25]:  # Discord лимит 25
            options.append(discord.SelectOption(
                label=guild.name,
                value=str(guild.id),
                description=f'ID: {guild.id}'
            ))
        
        select = Select(placeholder='Выберите сервер для получения ролей', options=options)
        
        async def select_callback(select_interaction: discord.Interaction):
            guild_id = int(select_interaction.data['values'][0])
            guild = bot.get_guild(guild_id)
            
            if not guild:
                await select_interaction.response.send_message('❌ Сервер не найден.', ephemeral=True)
                return
            
            bot_member = guild.get_member(bot.user.id)
            
            # Получаем роли которые бот может выдать
            manageable_roles = [role for role in guild.roles if role.position < bot_member.top_role.position and not role.is_default()]
            
            if not manageable_roles:
                await select_interaction.response.send_message('❌ Нет доступных ролей для управления на этом сервере.', ephemeral=True)
                return
            
            roles_text = [f'📋 **Роли сервера {guild.name}:**\n']
            
            for role in manageable_roles:
                roles_text.append(f'• {role.name} - `{role.id}`')
            
            text = '\n'.join(roles_text)
            
            if len(text) > 4000:
                # Разбиваем на части
                chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]
                await select_interaction.response.send_message(chunks[0], ephemeral=True)
                
                for chunk in chunks[1:]:
                    await select_interaction.followup.send(chunk, ephemeral=True)
            else:
                await select_interaction.response.send_message(text, ephemeral=True)
        
        select.callback = select_callback
        view = View(timeout=60)
        view.add_item(select)
        
        await interaction.response.send_message('Выберите сервер для получения списка ролей:', view=view, ephemeral=True)

# View для действий с выбранным сервером
class ServerActionsView(View):
    def __init__(self, guild_id):
        super().__init__(timeout=60)
        self.guild_id = guild_id
    
    @discord.ui.button(label='Получить роли сервера', style=discord.ButtonStyle.primary, emoji='📋')
    async def get_roles(self, interaction: discord.Interaction, button: Button):
        guild = bot.get_guild(self.guild_id)
        
        if not guild:
            await interaction.response.send_message('❌ Сервер не найден.', ephemeral=True)
            return
        
        bot_member = guild.get_member(bot.user.id)
        
        # Получаем роли которые бот может выдать
        manageable_roles = [role for role in guild.roles if role.position < bot_member.top_role.position and not role.is_default()]
        
        if not manageable_roles:
            await interaction.response.send_message('❌ Нет доступных ролей для управления.', ephemeral=True)
            return
        
        roles_text = [f'**Роли сервера {guild.name}:**\n']
        
        for role in manageable_roles:
            roles_text.append(f'• {role.name} - `{role.id}`')
        
        text = '\n'.join(roles_text)
        
        if len(text) > 4000:
            # Разбиваем на части
            chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]
            await interaction.response.send_message(chunks[0], ephemeral=True)
            
            for chunk in chunks[1:]:
                await interaction.followup.send(chunk, ephemeral=True)
        else:
            await interaction.response.send_message(text, ephemeral=True)

@bot.event
async def on_member_update(before, after):
    """Отслеживание изменения никнейма участника"""
    # Проверяем изменился ли никнейм
    if before.display_name == after.display_name:
        return
    
    # Проверяем есть ли канал для логов
    if not NICKNAME_LOG_CHANNEL_ID:
        return
    
    log_channel = after.guild.get_channel(NICKNAME_LOG_CHANNEL_ID)
    if not log_channel:
        return
    
    # Проверяем есть ли у участника нужные роли
    if not NICKNAME_LOG_ROLE_IDS:
        return
    
    user_role_ids = [role.id for role in after.roles]
    has_tracked_role = any(role_id in NICKNAME_LOG_ROLE_IDS for role_id in user_role_ids)
    
    if not has_tracked_role:
        return
    
    # Создаем embed с логом изменения никнейма
    embed = discord.Embed(
        title='📝 Изменение никнейма',
        color=discord.Color.gold(),  # Желтый цвет
        timestamp=datetime.now()
    )
    
    # Добавляем информацию
    embed.add_field(
        name='Участник',
        value=f'{after.mention} ({after.name})',
        inline=False
    )
    
    embed.add_field(
        name='Старый никнейм',
        value=before.display_name,
        inline=True
    )
    
    embed.add_field(
        name='Новый никнейм',
        value=after.display_name,
        inline=True
    )
    
    # Добавляем аватар пользователя
    if after.avatar:
        embed.set_thumbnail(url=after.avatar.url)
    
    embed.set_footer(text=f'ID: {after.id}')
    
    await log_channel.send(embed=embed)

@bot.event
async def on_ready():
    print(f'{bot.user} успешно подключен к Discord!')
    print(f'ID бота: {bot.user.id}')
    print('------')
    
    # Загружаем данные портфолио
    load_portfolio_data()
    
    # Синхронизируем slash команды
    try:
        synced = await bot.tree.sync()
        print(f'Синхронизировано {len(synced)} slash команд')
    except Exception as e:
        print(f'Ошибка синхронизации команд: {e}')
    
    # Автоматически отправляем сообщение о заявках
    try:
        for guild in bot.guilds:
            # Сообщение о заявках
            channel = guild.get_channel(APPLICATION_CHANNEL_ID)
            if channel:
                print(f'📝 Обработка канала заявок: {channel.name}')
                
                # Удаляем предыдущие сообщения бота в канале
                deleted_count = 0
                async for message in channel.history(limit=50):
                    if message.author == bot.user:
                        try:
                            await message.delete()
                            deleted_count += 1
                        except Exception as e:
                            print(f'⚠️ Не удалось удалить сообщение: {e}')
                
                print(f'🗑️ Удалено {deleted_count} старых сообщений')
                
                # Создаем embed с информацией
                embed = discord.Embed(
                    title='👋 Путь в семью начинается здесь!',
                    description=(
                        '• Уведомление о приглашении на обзвон обычно отправляется в личные сообщения. '
                        'Если ЛС закрыты, оно отправляется в ваш тикет.\n\n'
                        '• Обычно заявки обрабатываются в течение 15-60 минут — все зависит от того, '
                        'насколько загружены наши рекрутеры на данный момент.\n\n'
                        'Подать заявку можно только при открытом наборе. Если не выходит — набор закрыт. '
                        'Внимательно прочтите сообщение ниже.'
                    ),
                    color=discord.Color.purple()
                )
                
                # Проверяем наличие изображения
                image_path = f'images/{IMAGE_BANNER}'
                if os.path.exists(image_path):
                    file = discord.File(image_path, filename=IMAGE_BANNER)
                    embed.set_image(url=f'attachment://{IMAGE_BANNER}')
                    await channel.send(embed=embed, file=file)
                else:
                    await channel.send(embed=embed)
                
                # Отправляем сообщение с кнопкой
                embed2 = discord.Embed(
                    title='Здесь Вы можете подать заявку',
                    color=discord.Color.blue()
                )
                
                view = ApplicationStartView()
                await channel.send(embed=embed2, view=view)
                
                print(f'✅ Сообщение о заявках отправлено в канал {channel.name}')
            else:
                print(f'❌ Канал заявок с ID {APPLICATION_CHANNEL_ID} не найден')
            
            # Сообщение о портфолио
            if PORTFOLIO_CHANNEL_ID:
                portfolio_channel = guild.get_channel(PORTFOLIO_CHANNEL_ID)
                if portfolio_channel:
                    # Удаляем предыдущие сообщения бота в канале
                    async for message in portfolio_channel.history(limit=50):
                        if message.author == bot.user:
                            try:
                                await message.delete()
                            except:
                                pass
                    
                    # Создаем embed с информацией о портфолио
                    embed = discord.Embed(
                        title='Ваш путь в семье продолжается именно здесь! 🚀',
                        description=(
                            '• Здесь вы сможете создать своё портфолио 📁, постепенно повышать свой тир 📈, '
                            'а также получить шанс попасть в основной состав (main) ⭐️\n\n'
                            '• Что для этого нужно? Всё просто! Вы отправляете ссылки на свои откаты 🔗, '
                            'а когда будете готовы повысить тир — нажимаете кнопку «Хочу провериться». '
                            'После этого ваша заявка отправится на рассмотрение 👀'
                        ),
                        color=discord.Color.from_rgb(255, 105, 180)  # Розовый цвет
                    )
                    
                    # Проверяем наличие изображения для портфолио
                    image_path = f'images/{IMAGE_PORTFOLIO}'
                    view = PortfolioStartView()
                    
                    if os.path.exists(image_path):
                        file = discord.File(image_path, filename=IMAGE_PORTFOLIO)
                        embed.set_image(url=f'attachment://{IMAGE_PORTFOLIO}')
                        await portfolio_channel.send(embed=embed, file=file, view=view)
                    else:
                        await portfolio_channel.send(embed=embed, view=view)
                    
                    print(f'✅ Сообщение о портфолио отправлено в канал {portfolio_channel.name}')
                    
            # Восстанавливаем приветственные сообщения в существующих портфолио
            if PORTFOLIO_CATEGORY_ID:
                category = guild.get_channel(PORTFOLIO_CATEGORY_ID)
                if category:
                    for channel_id, data in list(portfolio_data.items()):
                        channel = guild.get_channel(channel_id)
                        if channel and 'welcome_message_id' in data:
                            # Проверяем существует ли сообщение
                            try:
                                await channel.fetch_message(data['welcome_message_id'])
                                print(f'✅ Приветственное сообщение в {channel.name} уже существует')
                            except:
                                # Сообщение не найдено, создаем новое
                                print(f'⚠️ Восстанавливаем приветственное сообщение в {channel.name}')
                                await recreate_welcome_message(channel, data['user_id'])
                        elif channel and 'welcome_message_id' not in data:
                            # Создаем приветственное сообщение если его нет
                            print(f'⚠️ Создаем приветственное сообщение в {channel.name}')
                            await recreate_welcome_message(channel, data['user_id'])
    except Exception as e:
        print(f'❌ Ошибка при отправке сообщения о заявках: {e}')

# Функция для пересоздания приветственного сообщения
async def recreate_welcome_message(channel, user_id):
    try:
        # Создаем приветственное сообщение с заголовком (БЕЗ изображения)
        embed = discord.Embed(
            title='Portfolio💼',
            description='Привет! Как будешь готов получить/улучшить свой тир нажми на кнопку «Хочу провериться». Удачи!',
            color=discord.Color.from_rgb(255, 105, 180)
        )
        
        view = PortfolioCheckView()
        message = await channel.send(embed=embed, view=view)
        
        # Закрепляем сообщение
        await message.pin()
        
        # Сохраняем ID сообщения
        portfolio_data[channel.id]['welcome_message_id'] = message.id
        save_portfolio_data()
    except Exception as e:
        print(f'Ошибка создания приветственного сообщения: {e}')


# Запуск бота
if __name__ == '__main__':
    if not TOKEN:
        print('Ошибка: DISCORD_TOKEN не найден в .env файле!')
    else:
        bot.run(TOKEN)
