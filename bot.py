import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import Button, View, Modal, TextInput, Select
import os
from dotenv import load_dotenv
from datetime import datetime
import json

# Загружаем переменные окружения
load_dotenv()

TOKEN = os.getenv('DISCORD_TOKEN')
FAMILY_NAME = os.getenv('FAMILY_NAME', 'GLORY')
APPLICATION_CHANNEL_ID = int(os.getenv('APPLICATION_CHANNEL_ID'))
TICKET_CATEGORY_ID = int(os.getenv('TICKET_CATEGORY_ID'))
LOG_CHANNEL_ID = int(os.getenv('LOG_CHANNEL_ID'))
REVIEWER_ROLE_IDS = [int(role_id.strip()) for role_id in os.getenv('REVIEWER_ROLE_IDS', '').split(',') if role_id.strip()]
INTERVIEW_VOICE_CHANNELS = [int(ch_id.strip()) for ch_id in os.getenv('INTERVIEW_VOICE_CHANNELS', '').split(',') if ch_id.strip()]

# Название изображения баннера
IMAGE_BANNER = os.getenv('IMAGE_BANNER', 'banner.png')

# Настройка интентов
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Хранилище данных о заявках
applications_data = {}

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
        
        embed.add_field(name='Ваш ник в игре', value=self.name_age_nick.value, inline=False)
        embed.add_field(name='Статик #', value=self.name_age_nick.value.split('&')[-1].strip() if '&' in self.name_age_nick.value else 'Не указан', inline=False)
        embed.add_field(name='Возраст ООС', value=self.name_age_nick.value.split('&')[1].strip() if '&' in self.name_age_nick.value else 'Не указан', inline=False)
        embed.add_field(name='Откат стрельбы ( без отката не принимаем!)', value=self.shooting.value, inline=False)
        embed.add_field(name='Семьи в которых вы были.', value=self.family_experience.value, inline=False)
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
            await user.send(f'🎉 Поздравляем! Ваша заявка была принята!\nРекрутер: {interaction.user.mention}')
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
                    description=f'Ваша заявка в **{FAMILY_NAME}** **взята на рассмотрение**!',
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
                    description=f'Ваша заявка в **{FAMILY_NAME}** **отклонена**!',
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
                    description=f'Вы были вызваны на **обзвон**!',
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
async def on_ready():
    print(f'{bot.user} успешно подключен к Discord!')
    print(f'ID бота: {bot.user.id}')
    print('------')
    
    # Автоматически отправляем сообщение о заявках
    try:
        for guild in bot.guilds:
            channel = guild.get_channel(APPLICATION_CHANNEL_ID)
            if channel:
                # Удаляем предыдущие сообщения бота в канале
                async for message in channel.history(limit=50):
                    if message.author == bot.user:
                        try:
                            await message.delete()
                        except:
                            pass
                
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
    except Exception as e:
        print(f'❌ Ошибка при отправке сообщения о заявках: {e}')


# Запуск бота
if __name__ == '__main__':
    if not TOKEN:
        print('Ошибка: DISCORD_TOKEN не найден в .env файле!')
    else:
        bot.run(TOKEN)
