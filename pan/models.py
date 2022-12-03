from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User

from .utils import get_uuid, get_unique_filename


# Значение заполнения, полученное после удаления соответствующего поля
def get_deleted_role():
    return Role.objects.get_or_create(role_key='anonymous', defaults={'role_name': 'anonymous'})[0]


def get_deleted_user():
    return User.objects.get_or_create(username='anonymous', defaults={'password': 'anonymous'})[0]


def get_deleted_user_file():
    return GenericFile.objects.get_or_create(
        file_name='anonymous',
        create_by=None,
        defaults={
            'file_uuid': get_uuid(),
            'file_cate': '0',
            'file_size': 0,
            'file_path': 'anonymous'
        }
    )[0]


def get_deleted_file_type():
    return FileType.objects.get_or_create(
        suffix='',
        defaults={'type_name': 'неизвестный'}
    )[0]


def get_deleted_file_share():
    return FileShare.objects.get_or_create(
        secret_key='anonymous',
        defaults={
            'signature': 'anonymous',
            'user_file': get_deleted_user_file(),
            'expire_time': timezone.now()
        }
    )[0]


# Агент-менеджер
class UserFileManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(file_cate='0')


class UserDirManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(file_cate='1')


class MessageManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(action='0')


class ApprovalManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(action='1')


class BaseModel(models.Model):
    """Основные области"""

    create_time = models.DateTimeField(auto_now_add=True, verbose_name='Время создания')
    update_time = models.DateTimeField(auto_now=True, verbose_name='Время обновления')
    create_by = models.ForeignKey(User, on_delete=models.SET(get_deleted_user), blank=True, null=True,
                                  related_name='+', verbose_name='Cоздатель')
    update_by = models.ForeignKey(User, on_delete=models.SET(get_deleted_user), blank=True, null=True,
                                  related_name='+', verbose_name='Средство обновления')
    remark = models.TextField(blank=True, verbose_name='Замечания')

    class Meta:
        abstract = True


class Role(BaseModel):
    """роль"""

    role_name = models.CharField(max_length=50, verbose_name='Имя персонажа')
    role_key = models.CharField(unique=True, max_length=50, verbose_name='Характер')

    class Meta:
        verbose_name = 'роль'
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.role_name


class Limit(BaseModel):
    """условия"""

    limit_name = models.CharField(max_length=50, verbose_name='Ограниченное имя')
    limit_key = models.CharField(unique=True, max_length=50, verbose_name='Ограниченные символы')

    class Meta:
        verbose_name = 'условия'
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.limit_name


class RoleLimit(BaseModel):
    """Ролевые ограничения"""

    role = models.ForeignKey(Role, on_delete=models.CASCADE, verbose_name='роль')
    limit = models.ForeignKey(Limit, on_delete=models.CASCADE, verbose_name='ограничение')
    value = models.BigIntegerField(verbose_name='значение')

    class Meta:
        verbose_name = 'Ролевые ограничения'
        verbose_name_plural = verbose_name

    def __str__(self):
        return f'role: {self.role.role_key}, limit: {self.limit.limit_key}'


class Profile(BaseModel):
    """Профиль пользователя"""

    create_by = None

    GENDER = [
        ('0', 'Жен'),
        ('1', 'Муж')
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, verbose_name='пользователь')
    avatar = models.ImageField(upload_to=get_unique_filename, default='default/user.svg', verbose_name='аватар')
    gender = models.CharField(max_length=1, choices=GENDER, blank=True, verbose_name='пол')
    role = models.ForeignKey(Role, on_delete=models.SET(get_deleted_role), verbose_name='роль')

    class Meta:
        verbose_name = 'Профиль пользователя'
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.user.username


class FileType(BaseModel):
    """Тип файла"""

    type_name = models.CharField(max_length=50, verbose_name='Имя')
    suffix = models.CharField(unique=True, blank=True, max_length=10, verbose_name='Суффикс')

    class Meta:
        verbose_name = "Тип файла"
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.suffix


class GenericFile(BaseModel):
    """Пользовательский файл"""

    CATEGORY = [
        ('0', 'документ'),
        ('1', 'папка')
    ]

    DEL_FLAGS = [
        ('0', 'Не собранный'),
        ('1', 'Переработанный'),
    ]

    create_by = models.ForeignKey(User, on_delete=models.SET(get_deleted_user), related_name='files',
                                  blank=True, null=True,
                                  verbose_name='создатель')

    file_name = models.CharField(max_length=100, verbose_name='Имя файла')
    file_uuid = models.UUIDField(unique=True, default=get_uuid, verbose_name='Номер файла')
    file_cate = models.CharField(choices=CATEGORY, max_length=1, verbose_name='Классификация файлов')
    file_type = models.ForeignKey(FileType, blank=True, null=True, on_delete=models.SET(get_deleted_file_type),
                                  verbose_name="Тип файла")
    file_size = models.BigIntegerField(default=0, verbose_name='Размер файла')
    file_path = models.CharField(db_index=True, max_length=500, verbose_name="Путь к файлу")
    folder = models.ForeignKey('self', on_delete=models.CASCADE, to_field='file_uuid', null=True, blank=True,
                               verbose_name="Улучшенный каталог")
    del_flag = models.CharField(max_length=1, default='0', choices=DEL_FLAGS, verbose_name='Логотип')

    class Meta:
        ordering = ['-create_time']
        verbose_name = 'Пользовательский файл'
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.file_name


class UserFile(GenericFile):
    """Файловый агент"""
    objects = UserFileManager()

    class Meta:
        proxy = True
        verbose_name = 'Пользовательский файл'
        verbose_name_plural = verbose_name


class UserDir(GenericFile):
    """Прокси-сервер папки"""
    objects = UserDirManager()

    class Meta:
        proxy = True
        verbose_name = 'Папка пользователя'
        verbose_name_plural = verbose_name


class FileShare(BaseModel):
    """Запись общего доступа к файлам"""

    create_by = None

    secret_key = models.CharField(db_index=True, max_length=10, verbose_name='Поделиться ключом')
    signature = models.CharField(max_length=70, verbose_name='Цифровая подпись')
    user_file = models.ForeignKey(GenericFile, on_delete=models.CASCADE, verbose_name='документ')
    expire_time = models.DateTimeField(verbose_name='Срок годности')
    summary = models.CharField(blank=True, max_length=100, verbose_name='Поделиться дополнительным описанием')

    class Meta:
        ordering = ['-create_time']
        verbose_name = 'Общий доступ к файлам'
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.user_file.file_name


class ShareRecord(BaseModel):
    """Запись приема файла"""

    create_by = None

    file_share = models.ForeignKey(FileShare, on_delete=models.SET(get_deleted_file_share), verbose_name='Общий доступ к файлам')
    recipient = models.ForeignKey(User, null=True, on_delete=models.SET(get_deleted_user), verbose_name='получатель')
    anonymous = models.GenericIPAddressField(null=True, blank=True, verbose_name='Анонимный пользователь')

    class Meta:
        verbose_name = 'Запись приема файла'
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.file_share.user_file.file_name


class Notice(BaseModel):
    """уведомление"""

    title = models.CharField(max_length=50, verbose_name='подпись')
    content = models.TextField(verbose_name='Содержание уведомления')

    class Meta:
        verbose_name = 'уведомление'
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.title


class Message(BaseModel):
    """Сообщение пользователя"""

    ACTIONS = [
        ('0', 'сообщение'),
        ('1', 'заявление')
    ]

    STATE = [
        ('0', 'Неподтвержденный'),
        ('1', 'Принятый'),
        ('2', 'Неудачный')
    ]

    action = models.CharField(max_length=1, choices=ACTIONS, verbose_name='тип')
    state = models.CharField(max_length=1, default='0', choices=STATE, verbose_name='состояние')
    content = models.TextField(verbose_name='Содержание сообщения')

    class Meta:
        verbose_name = 'сообщение'
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.create_by.username


class UserMessage(Message):
    """Агент сообщений"""
    objects = MessageManager()

    class Meta:
        proxy = True
        verbose_name = 'Сообщение пользователя'
        verbose_name_plural = verbose_name


class UserApproval(Message):
    """Агент по аудиту"""
    objects = ApprovalManager()

    class Meta:
        proxy = True
        verbose_name = 'Пользовательское приложение'
        verbose_name_plural = verbose_name


class UserLog(models.Model):
    """Журнал посещений пользователя"""

    ACTIONS = [
        ('0', 'войти'),
        ('1', 'опубликовывать'),
        ('2', 'Ошибка входа')
    ]

    username = models.CharField(max_length=128, verbose_name='имя пользователя')
    ipaddress = models.GenericIPAddressField(verbose_name='IP-адрес :')
    browser = models.CharField(max_length=200, verbose_name='браузер')
    os = models.CharField(max_length=30, verbose_name='операционная система')
    action = models.CharField(max_length=1, choices=ACTIONS, verbose_name='действия')
    msg = models.CharField(max_length=100, verbose_name='данные')
    action_time = models.DateTimeField(auto_now_add=True, verbose_name='время')

    class Meta:
        verbose_name = 'Журнал посещений пользователя'
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.ipaddress
