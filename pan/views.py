from datetime import timedelta
from json import loads as json_loads
from pathlib import Path
from shutil import rmtree, move as file_move
from uuid import UUID

from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User
from django.core.signing import Signer, TimestampSigner, BadSignature, SignatureExpired
from django.core.mail import send_mail
from django.http import FileResponse
from django.shortcuts import render
from django.template.loader import render_to_string
from django.utils import timezone
from django.views.generic import View, TemplateView, RedirectView
from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import ModelViewSet

from .forms import UserBaseForm, InfoForm, AvatarForm, PasswordForm
from .models import (GenericFile, UserFile, UserDir, FileShare, ShareRecord,
                        FileType, UserApproval, UserMessage, Notice)
from .paginations import NoticeResultSetPagination
from .serializers import FileSerializer, FileShareSerializer, FolderSerializer, NoticeSerializer
from .utils import AjaxObj, get_key_signature, get_dir_size, make_archive_bytes, file_size_format


class IndexView(TemplateView):
    """Первая страница"""
    template_name = 'pan/index.html'


class CloudView(LoginRequiredMixin, TemplateView):
    """Облачный диск"""
    template_name = 'pan/cloud.html'


class HistoryView(LoginRequiredMixin, TemplateView):
    """История загрузок"""
    template_name = 'pan/history.html'


class BinView(LoginRequiredMixin, TemplateView):
    """корзина"""
    template_name = 'pan/bin.html'


class FileDetailView(LoginRequiredMixin, TemplateView):
    """Сведения о файле"""
    template_name = 'pan/detail.html'


class ProfileView(LoginRequiredMixin, TemplateView):
    """Личная информация"""
    template_name = 'pan/profile.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data()
        role = self.request.user.profile.role.role_key
        if role == 'common':
            context['applied'] = UserApproval.objects.filter(state='0', create_by=self.request.user).exists()
        context['role'] = role
        context['record'] = UserApproval.objects.filter(create_by=self.request.user)
        context['message'] = UserMessage.objects.filter(create_by=self.request.user)
        return context


class ShareLinkView(TemplateView):
    """Ссылка для получения общих файлов"""
    template_name = 'pan/share.html'

    def get_context_data(self, **kwargs):
        signature = self.kwargs.get('signature')
        context = super().get_context_data()
        try:
            share = FileShare.objects.select_related('user_file').get(secret_key=Signer().unsign(signature))
        except (BadSignature, FileShare.DoesNotExist):
            context['expired'] = True
            return context
        expired = timezone.now() > share.expire_time
        if not expired:
            if self.request.user.is_authenticated:
                ShareRecord.objects.create(file_share=share, recipient=self.request.user)
            else:
                ShareRecord.objects.create(file_share=share, anonymous=self.request.META.get('REMOTE_ADDR'))
            context['file'] = share.user_file
            context['share'] = share
        context['expired'] = expired
        return context


class ResetDoneView(TemplateView):
    """Результат сброса пароля"""
    template_name = 'pan/reset_done.html'

    def get_context_data(self, **kwargs):
        param = self.kwargs.get('param')
        context = super().get_context_data()
        try:
            auth = TimestampSigner().unsign_object(param, max_age=settings.TOKEN_EXPIRY)
            if auth['token'] != settings.RESET_TOKEN:
                context['auth'] = False
            else:
                user = User.objects.get(username=auth['user'])
                user.set_password(settings.RESET_PASSWORD)
                user.save()
                context['auth'] = True
        except (BadSignature, SignatureExpired):
            context['auth'] = False
        return context


class LoginView(View):
    """войти"""

    def post(self, request):
        form = UserBaseForm(request.POST)
        if form.is_valid():
            user = authenticate(request, username=form.cleaned_data['username'], password=form.cleaned_data['password'])
            if user:
                login(request, user)
                if not form.cleaned_data['remember']:
                    request.session.set_expiry(0)
                return AjaxObj(msg='Успешный вход в систему', data=request.session['cloud']).get_response()

            return AjaxObj(400, 'ошибка', {'errors': {'username': ['Неправильное имя пользователя или пароль']}}).get_response()

        return AjaxObj(400, 'ошибка', {'errors': form.errors}).get_response()


class RegisterView(View):
    """регистрация"""

    def post(self, request):
        form = UserBaseForm(request.POST)
        if form.is_valid():
            if User.objects.filter(username=form.cleaned_data['username']).exists():
                return AjaxObj(400, 'ошибка', {'errors': {'username': ['Имя пользователя уже существует']}}).get_response()

            User.objects.create_user(username=form.cleaned_data['username'],
                                     password=form.cleaned_data['password'])
            return AjaxObj(msg='Регистрация прошла успешно').get_response()

        return AjaxObj(400, 'ошибка', {'errors': form.errors}).get_response()


class LoginOutView(RedirectView):
    """опубликовывать"""
    pattern_name = 'pan:index'

    def get(self, request, *args, **kwargs):
        logout(request)
        return super().get(request, *args, **kwargs)


class AlterAvatarView(LoginRequiredMixin, View):
    """Изменить аватар"""

    def post(self, request):
        form = AvatarForm(request.POST, request.FILES)
        if form.is_valid():
            if form.cleaned_data['avatar'].size > settings.MAX_AVATAR_SIZE:
                return AjaxObj(400, f'Загруженное изображение не может быть больше, чем{file_size_format(settings.MAX_AVATAR_SIZE)}').get_response()
            profile = request.user.profile
            profile.avatar = form.cleaned_data['avatar']
            profile.update_by = request.user
            profile.save()
            return AjaxObj(msg='Загрузка прошла успешно').get_response()

        return AjaxObj(400, 'Незаконные файлы').get_response()


class AlterPasswordView(LoginRequiredMixin, View):
    """Поменять пароль"""

    def post(self, request):
        form = PasswordForm(request.POST)
        if form.is_valid():
            if request.user.check_password(form.cleaned_data['oldPassword']):
                request.user.set_password(form.cleaned_data['newPassword'])
                request.user.save()
                return AjaxObj(msg='Успешно модифицировано').get_response()

            return AjaxObj(400, 'ошибка', {'errors': {'oldPassword': ['Исходный пароль неверен']}}).get_response()

        return AjaxObj(400, 'ошибка', {'errors': form.errors}).get_response()


class ResetPasswordView(View):
    """Сброс пароля"""

    def post(self, request):
        username = request.POST.get('resetName').strip()
        queryset = User.objects.filter(username=username)
        if not queryset.exists():
            return AjaxObj(400, 'ошибка', {'errors': {'resetName': ['Имя пользователя не существует']}}).get_response()

        user = queryset.get()
        if user.email == '':
            return AjaxObj(400, 'ошибка', {'errors': {'resetName': ['Пользователь не привязан к почтовому ящику']}})\
                .get_response()

        auth = {'user': user.username, 'token': settings.RESET_TOKEN}
        context = {'scheme': request.META.get('wsgi.url_scheme'),
                   'host': request.META.get('HTTP_HOST'),
                   'param': TimestampSigner().sign_object(auth),
                   'password': settings.RESET_PASSWORD}
        html = render_to_string('pan/reset.html', context)
        send_mail(
            subject='Tiny Cloud',
            message=html,
            from_email=None,
            recipient_list=[user.email],
            fail_silently=True,
            html_message=html
        )
        return AjaxObj(msg='Электронное письмо с подтверждением было отправлено').get_response()


class AlterInfoView(LoginRequiredMixin, View):
    """Изменять информацию"""

    def post(self, request):
        form = InfoForm(request.POST)
        if form.is_valid():
            user = request.user
            profile = user.profile
            email = form.cleaned_data['email']
            gender = form.cleaned_data['gender']
            if email != '' and User.objects.filter(email=email).exclude(username=user.username).exists():
                return AjaxObj(400, 'ошибка', {'errors': {'email': ['Пользователь уже привязал почтовый ящик']}})\
                    .get_response()

            profile.gender = gender
            profile.update_by = user
            user.email = email
            profile.save()
            user.save()
            return AjaxObj(msg='Изменение было успешным').get_response()

        return AjaxObj(400, 'ошибка', {'errors': form.errors}).get_response()


class MsgApprView(LoginRequiredMixin, View):
    """Приложение и сообщение"""

    def post(self, request):
        message = request.POST.get('message').strip()
        if message == '' or message is None:
            return AjaxObj(400, 'Незаконная информация').get_response()
        if request.POST.get('way') == 'apply':
            msg = 'Успешно поданная заявка'
            UserApproval.objects.create(content=message, create_by=request.user)
        else:
            msg = 'Спасибо вам за ваше сообщение'
            UserMessage.objects.create(content=message, create_by=request.user)
        return AjaxObj(200, msg).get_response()


class FileBlobView(View):
    """загрузить файл"""

    def get(self, request, *args, **kwargs):
        uuid = self.kwargs.get('uuid')
        blob = self.request.GET.get('blob')
        root = settings.MEDIA_ROOT
        try:
            file = GenericFile.objects.get(file_uuid=uuid)
        except GenericFile.DoesNotExist:
            return AjaxObj(400, "Файл не существует").get_response()

        if file.file_cate == '0':
            response = FileResponse(open(root / file.file_path, 'rb'), as_attachment=True)
            if blob:
                response.as_attachment = False
            return response
        else:
            return FileResponse(make_archive_bytes(root / file.file_path), as_attachment=True, filename='cloud.zip')


class DuplicatedCheck(LoginRequiredMixin, View):
    """Проверьте то же имя файла"""

    def get(self, request, *args, **kwargs):
        folder = request.user.files.get(file_uuid=request.GET.get('folderUUID', request.session['root']))
        path = Path(folder.file_path) / request.GET.get('uploadName')

        if (Path(settings.MEDIA_ROOT) / path).exists():
            return AjaxObj(400, 'В папке есть файл с таким же именем，Пожалуйста, обратите внимание на корзину')\
                .get_response()

        return AjaxObj().get_response()


class FileUploadView(LoginRequiredMixin, View):
    """Загрузить файл"""

    def post(self, request):
        file = request.FILES.get('file')
        if file is None:
            return AjaxObj().get_response()

        use = request.session['cloud']['used'] + file.size
        if use > request.session['cloud']['storage']:
            return AjaxObj(400, 'Недостаточно оставшегося места').get_response()

        folder = request.user.files.get(file_uuid=request.POST.get('folderUUID', request.session['root']))
        file_path = Path(folder.file_path) / file.name
        file_type = FileType.objects.get_or_create(suffix=Path(file.name).suffix,
                                                   defaults={'type_name': 'неизвестный'})[0]
        dirs = []

        with open(settings.MEDIA_ROOT / file_path, 'wb') as f:
            for chunk in file.chunks():
                f.write(chunk)
        UserFile(file_name=file.name, file_type=file_type, file_size=file.size, file_path=file_path,
                 folder=folder, create_by=request.user).save()

        # Обновить размер родительской папки
        while folder is not None:
            folder.file_size = folder.file_size + file.size
            folder.update_by = request.user
            dirs.append(folder)
            folder = folder.folder
        UserDir.objects.bulk_update(dirs, ('file_size', 'update_by'))

        request.session['cloud']['used'] = use
        return AjaxObj(200, 'Успешная загрузка файла').get_response()


class FolderUploadView(LoginRequiredMixin, View):
    """Папка для загрузки"""

    def post(self, request):
        files = request.FILES.getlist('files')
        paths = request.POST.getlist('paths')

        if files is None or paths is None:
            return AjaxObj().get_response()

        path_nums = len(paths)
        if path_nums * 2 > settings.DATA_UPLOAD_MAX_NUMBER_FIELDS:
            return AjaxObj(400, f'Количество загруженных записей превышает{settings.DATA_UPLOAD_MAX_NUMBER_FIELDS}предел').get_response()

        use = request.session['cloud']['used'] + sum(s.size for s in files)
        if use > request.session['cloud']['storage']:
            return AjaxObj(400, 'Недостаточно оставшегося места').get_response()

        folder = request.user.files.get(file_uuid=request.POST.get('folderUUID', request.session['root']))
        folder_path = Path(folder.file_path)
        objs = []
        dirs = []

        for i in range(path_nums):
            # Рекурсивно создайте каталог
            parts = Path(paths[i]).parts[:-1]
            temp_folder = folder
            temp_path = folder_path
            for part in parts:
                part_path = temp_path / part
                if Path(settings.MEDIA_ROOT / part_path).exists():
                    prev = UserDir.objects.get(file_path=part_path)
                    temp_folder = prev
                    temp_path = Path(part_path)
                else:
                    prev = UserDir(file_name=part, file_path=part_path, folder=temp_folder, create_by=request.user)
                    dirs.append(prev)
                    prev.save()
                    Path.mkdir(settings.MEDIA_ROOT / part_path)
                    temp_folder = prev
                    temp_path = Path(part_path)
            # Создать файл
            file = files[i]
            file_path = temp_path / file.name
            with open(settings.MEDIA_ROOT / file_path, 'wb') as f:
                for chunk in file.chunks():
                    f.write(chunk)
            file_type = FileType.objects.get_or_create(suffix=Path(file.name).suffix,
                                                       defaults={'type_name': 'неизвестный'})[0]
            objs.append(UserFile(file_name=file.name, file_cate='0', file_type=file_type, file_size=file.size,
                                 file_path=file_path, folder=temp_folder, create_by=request.user))

        # Рассчитайте размер файла и обновите базу данных
        for d in dirs:
            d.file_size = get_dir_size(settings.MEDIA_ROOT / d.file_path)
            d.update_by = request.user

        while folder is not None:
            folder.file_size = get_dir_size(settings.MEDIA_ROOT / folder_path)
            folder.update_by = request.user
            dirs.append(folder)
            folder = folder.folder
            folder_path = folder.file_path if folder is not None else None

        UserFile.objects.bulk_create(objs)
        UserDir.objects.bulk_update(dirs, ('file_size', 'update_by'))

        request.session['cloud']['used'] = use
        return AjaxObj(200, 'Успешная загрузка папки').get_response()


class ShareCreateView(LoginRequiredMixin, View):
    """Создайте общий файл"""

    def post(self, request):
        uuid = request.POST.get('uuid')
        while True:
            key, signature = get_key_signature()
            if not FileShare.objects.filter(secret_key=key).exists():
                break

        share = FileShare.objects.create(secret_key=key, signature=signature,
                                         user_file=GenericFile.objects.get(file_uuid=uuid),
                                         expire_time=timezone.now() + timedelta(days=7))
        return AjaxObj(200, data={'key': key, 'signature': signature, 'id': share.id}).get_response()


class ShareUpdateView(LoginRequiredMixin, View):
    """Обновление общих файлов"""

    def post(self, request):
        data = json_loads(request.body)
        share = FileShare.objects.get(id=data.get('id'))
        delta = data.get('delta')
        summary = data.get('summary')
        if delta is None and summary is not None:
            share.summary = summary
        elif delta is not None and summary is None:
            share.expire_time = timezone.now() + timedelta(days=delta)
        else:
            share.summary = summary
            share.expire_time = timezone.now() + timedelta(days=delta if delta is not None else 0)
        share.update_by = request.user
        share.save()
        return AjaxObj(200, 'Ссылка была установлена успешно').get_response()


class ShareGetView(View):
    """Получить общие файлы"""

    def post(self, request):
        key = request.POST.get('key')
        try:
            share = FileShare.objects.select_related('user_file').get(secret_key=key)
        except FileShare.DoesNotExist:
            return AjaxObj(400, 'Срок действия пароля истек').get_response()

        if timezone.now() > share.expire_time:
            return AjaxObj(400, 'Срок действия пароля истек').get_response()
        file = share.user_file
        if request.user.is_authenticated:
            ShareRecord.objects.create(file_share=share, recipient=request.user)
        else:
            ShareRecord.objects.create(file_share=share, anonymous=request.META.get('REMOTE_ADDR'))
        return AjaxObj(200, data={
            'file': {'name': file.file_name, 'size': file.file_size, 'uuid': file.file_uuid},
            'share': {'expire': share.expire_time, 'summary': share.summary}
        }).get_response()


class ShareDelete(LoginRequiredMixin, View):
    """Удаление общих файлов"""

    def post(self, request):
        ids = json_loads(request.body).get('ids')
        for i in ids:
            try:
                FileShare.objects.select_related('user_file').filter(
                    user_file__create_by=request.user).get(id=i).delete()
            except FileShare.DoesNotExist:
                return AjaxObj(400, "В выбранной записи есть файлы, которые не существуют или были удалены")\
                    .get_response()
        return AjaxObj(200, 'Успешно удалена выбранная запись').get_response()


class FileMoveView(LoginRequiredMixin, View):
    """Перемещение файла"""

    def post(self, request):
        data = json_loads(request.body)
        if data.get('src') == data.get('dst'):
            return AjaxObj(400, 'Папка пустая').get_response()

        src = request.user.files.get(file_uuid=data.get('src'))
        dst = request.user.files.get(file_uuid=data.get('dst', request.session['root']))

        if request.user.files.filter(folder=dst, file_cate=src.file_cate, file_name=src.file_name).exists():
            return AjaxObj(400, 'В папке есть файл с таким же именем').get_response()

        dirs = []
        src_folder = src.folder

        file_move(str(settings.MEDIA_ROOT / src.file_path), str(settings.MEDIA_ROOT / dst.file_path))
        src.folder = dst
        src.file_path = Path(dst.file_path) / src.file_name
        src.update_by = request.user
        src.save()

        # Обновите папку назначения и исходную папку, а также размер ее родительской папки
        # (за исключением корневого каталога)
        while dst.folder is not None:
            dst.file_size = dst.file_size + src.file_size
            dst.update_by = request.user
            dirs.append(dst)
            dst = dst.folder
        while src_folder.folder is not None:
            src_folder.file_size = src_folder.file_size - src.file_size
            src_folder.update_by = request.user
            dirs.append(src_folder)
            src_folder = src_folder.folder

        if len(dirs) != 0:
            UserDir.objects.bulk_update(dirs, ('file_size', 'update_by'))

        return AjaxObj(200, 'Успешное перемещение папки').get_response()


class FileDeleteView(LoginRequiredMixin, View):
    """Удаление файла"""

    def post(self, request):
        uuids = json_loads(request.body).get('uuids')
        use = request.session['cloud']['used']
        code = msg = folder = None
        discard = 0
        dirs = []
        for uuid in uuids:
            try:
                file = request.user.files.get(file_uuid=uuid)
                discard += file.file_size
                if folder is None:
                    folder = file.folder
            except GenericFile.DoesNotExist:
                break
            real_path = settings.MEDIA_ROOT / file.file_path
            if file.file_cate == '0':
                real_path.unlink()
            else:
                rmtree(real_path)
            file.delete()
        else:
            code, msg = 200, 'Успешно удален выбранный файл'
        if code is None and msg is None:
            code, msg = 400, 'Некоторые файлы не существуют или были удалены'

        # Обновить размер родительской папки
        while folder is not None:
            folder.file_size = folder.file_size - discard
            folder.update_by = request.user
            dirs.append(folder)
            folder = folder.folder
        if len(dirs) != 0:
            UserDir.objects.bulk_update(dirs, ('file_size', 'update_by'))

        use -= discard
        request.session['cloud']['used'] = use

        return AjaxObj(code, msg).get_response()


class FileTrashView(LoginRequiredMixin, View):
    """Мягкое удаление файла, восстановление"""

    def post(self, request):
        json_data = json_loads(request.body)
        method = json_data.get('method')
        uuids = json_data.get('uuids')
        objs = []
        if method == 'trash':
            del_flag = '1'
            msg = 'Успешно удален выбранный файл'
        else:
            del_flag = '0'
            msg = 'Успешно восстановлены выбранные файлы'
        for uuid in uuids:
            try:
                file = request.user.files.get(file_uuid=uuid)
            except GenericFile.DoesNotExist:
                return AjaxObj(400, 'Некоторые файлы не существуют или были удалены').get_response()
            file.del_flag = del_flag
            file.update_by = request.user
            objs.append(file)

        GenericFile.objects.bulk_update(objs, ('del_flag',))
        return AjaxObj(200, msg).get_response()


class CloudViewSet(ModelViewSet):
    """Облачный диск api"""
    serializer_class = FileSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None

    def get_queryset(self):
        folder_uuid = self.request.query_params.get('folderUUID', self.request.session['root'])
        sort = self.request.query_params.get('sort')
        order = self.request.query_params.get('order')
        search = self.request.query_params.get('search')

        if search:
            queryset = self.request.user.files.filter(file_name__icontains=search, file_cate='0', del_flag='0')
        else:
            queryset = self.request.user.files.select_related('folder').filter(folder__file_uuid=folder_uuid,
                                                                               del_flag='0')
        if sort:
            if order == 'desc':
                queryset = queryset.order_by('-' + sort)
            else:
                queryset = queryset.order_by(sort)
        return queryset


class HistoryViewSet(ModelViewSet):
    """История загрузок api"""
    serializer_class = FileShareSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        sort = self.request.query_params.get('sort')
        order = self.request.query_params.get('order')
        search = self.request.query_params.get('search')
        queryset = FileShare.objects.select_related('user_file').filter(user_file__create_by=self.request.user)

        if search:
            queryset = queryset.filter(user_file__file_name__icontains=search)
        if sort:
            if order == 'desc':
                queryset = queryset.order_by('-' + sort)
            else:
                queryset = queryset.order_by(sort)
        return queryset


class BinViewSet(ModelViewSet):
    """корзина api"""
    serializer_class = FileSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        sort = self.request.query_params.get('sort')
        order = self.request.query_params.get('order')
        search = self.request.query_params.get('search')
        queryset = self.request.user.files.filter(del_flag='1')

        if search:
            queryset = queryset.filter(file_name__icontains=search)
        if sort:
            if order == 'desc':
                queryset = queryset.order_by('-' + sort)
            else:
                queryset = queryset.order_by(sort)
        return queryset


class FolderViewSet(ModelViewSet):
    """папка api"""
    serializer_class = FolderSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None

    def get_queryset(self):
        exclude = self.request.query_params.get('exclude')
        folder_uuid = self.request.query_params.get('folderUUID', self.request.session['root'])
        return self.request.user.files.select_related('folder').filter(folder__file_uuid=folder_uuid,
                                                                       file_cate='1',
                                                                       del_flag='0').exclude(file_uuid=exclude)


class FileViewSet(ModelViewSet):
    """Сведения о файле api"""
    serializer_class = FileSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None

    def get_queryset(self):
        try:
            uuid = UUID(hex=self.request.query_params.get('uuid'))
        except ValueError:
            return GenericFile.objects.none()
        return self.request.user.files.filter(file_uuid=uuid, file_cate='0')


class NoticeViewSet(ModelViewSet):
    """сообщение api"""
    serializer_class = NoticeSerializer
    queryset = Notice.objects.all()
    permission_classes = [IsAuthenticated]
    pagination_class = NoticeResultSetPagination


# Представление исключения
def bad_request_view(request, exception, template_name='errors/400.html'):
    return render(request, template_name, status=400)


def permission_denied_view(request, exception, template_name='errors/403.html'):
    return render(request, template_name, status=403)


def not_found_view(request, exception, template_name='errors/404.html'):
    return render(request, template_name, status=404)


def server_error_view(request, template_name='errors/500.html'):
    return render(request, template_name, status=500)
