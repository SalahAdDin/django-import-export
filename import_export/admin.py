import tempfile

from django.contrib import admin
from django.utils.translation import ugettext_lazy as _
from django.conf.urls.defaults import patterns, url
from django.template.response import TemplateResponse
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.utils.importlib import import_module

from .forms import ImportForm
from .core import Importer


class ImportMixin(object):

    change_list_template = 'admin/import_export/change_list_import.html'
    import_template_name = 'admin/import_export/import.html'
    importer_class = Importer
    format_choices = (
            ('', '---'),
            ('tablib.formats.csv', 'CSV'),
            ('tablib.formats.xls', 'Excel XLS'),
            )

    def get_urls(self):
        urls = super(ImportMixin, self).get_urls()
        info = self.model._meta.app_label, self.model._meta.module_name
        my_urls = patterns('',
            url(r'^import/$',
                self.admin_site.admin_view(self.import_action),
                name='%s_%s_import' % info),
        )
        return my_urls + urls

    def get_importer_class(self):
        return self.importer_class

    def get_format(self, format_class):
        if format_class:
            return import_module(format_class)
        return None

    def get_mode_for_format(self, format):
        """
        Return mode for opening files.
        """
        return 'rU'

    def import_action(self, request, *args, **kwargs):
        importer_class = self.get_importer_class()
        if request.POST and request.POST.get('tmp_file'):
            input_format = self.get_format(request.POST.get('input_format'))
            import_mode = self.get_mode_for_format(input_format)
            import_file = open(request.POST.get('tmp_file'), import_mode)
            result = self.importer_class(import_file,
                    model=self.model,
                    format=input_format,
                    dry_run=False,
                    raise_errors=True).run()
            success_message = _('Import finished')
            messages.success(request, success_message)
            import_file.close()
            return HttpResponseRedirect('..')

        form = ImportForm(self.format_choices,
                request.POST or None,
                request.FILES or None)
        result = None
        tmp_file_name = None
        input_format = None
        if request.POST:
            if form.is_valid():
                input_format = form.cleaned_data['input_format']
                import_mode = self.get_mode_for_format(input_format)
                import_file = form.cleaned_data['import_file']
                import_file.open(import_mode)
                result = importer_class(import_file,
                        model=self.model,
                        raise_errors=False,
                        format=self.get_format(input_format),
                        dry_run=True).run()
                if not result.has_errors():
                    tmp_file = tempfile.NamedTemporaryFile(delete=False)
                    for chunk in import_file.chunks():
                        tmp_file.write(chunk)
                    tmp_file.close()
                    tmp_file_name = tmp_file.name
        fields = importer_class(model=self.model).get_representation_fields()
        context = {
                'form': form,
                'result': result,
                'opts': self.model._meta,
                'fields': fields,
                'tmp_file': tmp_file_name,
                'input_format': input_format,
                }
        return TemplateResponse(request, [self.import_template_name],
                context, current_app=self.admin_site.name)