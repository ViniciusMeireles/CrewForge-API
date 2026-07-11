from __future__ import annotations

import logging
from typing import Callable

from django.conf import settings
from django.core.files.storage import default_storage
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.utils.translation import gettext as _
from django.views.generic import TemplateView


class TemplateNotDefinedException(ValueError):
    pass


class EmailView(TemplateView):
    """
    A Django view that renders an email for preview purposes.
    Subclasses should set the `email_class` attribute to the email class
    they want to preview.
    """

    email_class: type[EmailBase] = None

    def __init__(self, email_class: type[EmailBase] | None = None, **kwargs):
        if email_class:
            self.email_class = email_class
        if not self.email_class:
            raise ValueError('email_class must be provided')
        self.email = None
        super().__init__(**kwargs)

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.email = self.email_class(
            is_preview=True, **self.email_class.get_preview_kwargs(view=self)
        )

    def get_template_names(self):
        if self.template_name:
            return super().get_template_names()
        return [self.email.get_template_name()]

    def get_context_data(self, merge_email_context: bool = True, **inner_kwargs):
        context = super().get_context_data(**inner_kwargs)
        if merge_email_context:
            context.update(self.email.get_context_data())
        return context


class CTAEmail:
    """Call-To-Action (CTA) button representation for emails."""

    def __init__(
        self,
        *,
        url: str,
        text: str = _('Click Here'),
        color: str = '#002180',
        text_color: str = '#FFFFFF',
    ):
        """
        Initializes a CTAEmail instance.
        :param url: The URL the button will link to.
        :param text: The text displayed on the button.
        :param color: The background color of the button.
        :param text_color: The text color of the button.
        """
        self.url = url
        self.text = text
        self.color = color
        self.text_color = text_color


class EmailBase:
    """
    Base class for sending HTML emails using Django's email framework.
    Subclasses should override the necessary attributes and methods to customize
    the email content and behavior.
    """

    template_name = 'emails/base.html'

    subject: str
    recipient_list: list[str] = []
    preheader: str = None
    theme_color: str = '#002180'

    title: str | None = None
    content: str | None = None
    logo: str | None = None
    cta: CTAEmail | None = None

    footer_text: str | None = None
    system_company_address: str | None = None
    unsubscribe_url: str | None = None

    file_path: str | None = None
    file_name: str | None = None
    file_mimetype: str | None = None

    from_email: str = settings.FROM_MAIL
    language: str = settings.LANGUAGE_CODE
    system_title = settings.SYSTEM_TITLE

    def __init__(self, is_preview: bool = False, **kwargs):
        """
        Initializes the EmailBase instance with recipient list and optional attributes.
        :param is_preview: Indicates if the email is being rendered for preview
                           purposes.
        :param kwargs: Additional attributes to override default values.
        """
        self._is_preview = is_preview
        self.kwargs = {}
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
            else:
                self.kwargs[key] = value

    @property
    def is_preview(self) -> bool:
        return self._is_preview

    def get_subject(self) -> str:
        if not self.subject:
            if self.is_preview:
                logging.warning('Subject is not defined in preview mode')
            else:
                raise ValueError('Subject is not defined')
        return self.subject

    def get_recipient_list(self) -> list[str]:
        if not self.recipient_list:
            if self.is_preview:
                logging.warning('Recipient list is empty in preview mode')
            else:
                raise ValueError('Recipient list is empty')
        return self.recipient_list

    def get_preheader(self) -> str:
        return self.preheader or ''

    def get_theme_color(self) -> str:
        return self.theme_color or '#002180'

    def get_title(self) -> str:
        return self.title or ''

    def get_content(self) -> str:
        return self.content or ''

    def get_logo(self) -> str:
        return self.logo or ''

    def get_cta(self) -> CTAEmail | None:
        cta = self.cta
        if cta and not cta.color and self.get_theme_color():
            cta.color = self.get_theme_color()
        return cta

    def get_footer_text(self) -> str:
        return self.footer_text or ''

    def get_system_company_address(self) -> str:
        return self.system_company_address or ''

    def get_unsubscribe_url(self) -> str:
        return self.unsubscribe_url or ''

    def get_file_path(self) -> str | None:
        return self.file_path

    def get_file_name(self) -> str | None:
        if not self.file_name and self.get_file_path():
            file_name = self.file_path.split('/')[-1] if self.file_path else None
            return file_name
        return self.file_name

    def get_file_mimetype(self) -> str | None:
        if not self.file_mimetype and self.get_file_path():
            raise ValueError('File mimetype is not defined')
        return self.file_mimetype

    def get_from_email(self) -> str:
        return self.from_email or settings.DEFAULT_FROM_EMAIL

    def get_system_title(self) -> str:
        return self.system_title or settings.SYSTEM_TITLE

    def get_template_name(self) -> str:
        if not self.template_name:
            raise TemplateNotDefinedException('Template name is not defined')
        return self.template_name

    @classmethod
    def _get_context_data_methods_map(cls) -> dict[str, Callable]:
        return {
            'subject': cls.get_subject,
            'recipient_list': cls.get_recipient_list,
            'preheader': cls.get_preheader,
            'theme_color': cls.get_theme_color,
            'title': cls.get_title,
            'content': cls.get_content,
            'logo': cls.get_logo,
            'cta': cls.get_cta,
            'footer_text': cls.get_footer_text,
            'system_company_address': cls.get_system_company_address,
            'unsubscribe_url': cls.get_unsubscribe_url,
            'file_path': cls.get_file_path,
            'file_name': cls.get_file_name,
            'file_mimetype': cls.get_file_mimetype,
            'from_email': cls.get_from_email,
            'system_title': cls.get_system_title,
        }

    def get_context_data(self) -> dict:
        context_data = {}
        for key, method in self._get_context_data_methods_map().items():
            try:
                context_data[key] = method(self)
            except Exception as e:
                if not self.is_preview:
                    raise e
                context_data[key] = getattr(self, key)
        return context_data

    def get_message(self) -> EmailMultiAlternatives:
        """Renders the email template and returns an EmailMultiAlternatives object."""
        html_content = render_to_string(
            template_name=self.get_template_name(),
            context=self.get_context_data(),
        )
        text_content = strip_tags(html_content)
        msg = EmailMultiAlternatives(
            subject=self.get_subject(),
            body=text_content,
            from_email=self.get_from_email(),
            to=self.get_recipient_list(),
        )
        msg.attach_alternative(html_content, 'text/html')
        if self.file_path:
            with default_storage.open(self.file_path, 'rb') as file:
                msg.attach(
                    filename=self.file_name or self.file_path.split('/')[-1],
                    content=file.read(),
                    mimetype=self.file_mimetype,
                )
        return msg

    def send(self, fail_silently: bool = False) -> int:
        """Sends the email and returns the number of successfully delivered messages."""
        email = self.get_message()
        return email.send(fail_silently=fail_silently)

    @classmethod
    def get_preview_kwargs(cls, view: EmailView | None = None) -> dict:
        """
        Returns the keyword arguments to instantiate the email class for preview
        purposes.
        """
        return view.kwargs if view else {}

    @classmethod
    def get_view_class(cls) -> type[EmailView]:
        """Returns a Django view class that renders the email for preview purposes."""

        class EmailPreview(EmailView):
            email_class = cls

        return EmailPreview

    @classmethod
    def as_view(cls, **kwargs):
        """Returns a Django view that renders the email for preview purposes."""
        return cls.get_view_class().as_view(**kwargs)
