from django.shortcuts import reverse
from django.urls import path
from django.utils.safestring import mark_safe
from django.utils.translation import gettext as _
from wagtail.contrib.modeladmin.helpers import ButtonHelper, PermissionHelper
from wagtail.contrib.modeladmin.options import ModelAdmin, modeladmin_register
from wagtail.contrib.modeladmin.views import IndexView
from wagtail.core import hooks
from wagtail.core.models import Page

from .models import TrashCan, TrashCanPage
from .utils import trash_can_for_request
from .views import trash_delete, trash_move, trash_restore, trash_real_delete


class TrashPermissionHelper(PermissionHelper):
    def user_can_create(self, user):
        return False


class TrashButtonHelper(ButtonHelper):
    delete_button_classnames = [
        "button-small",
        "button-secondary",
        "icon",
        "icon-bin",
    ]

    restore_button_classnames = [
        "button-small",
        "button-secondary",
        "icon",
        "icon-undo",
    ]

    # def restore_and_move_button(self, obj):
    #     return {
    #         "url": reverse("wagtail_trash_move", args=(obj.page.id,)),
    #         "label": _("Restore and move"),
    #         "classname": self.finalise_classname(self.restore_button_classnames),
    #         "title": _("Restore and move"),
    #     }

    def real_delete_button(self, obj):
        return {
            "url": reverse("wagtail_trash_real_delete", args=(obj.page.id,)),
            # "url": self.url_helper.get_action_url('delete', quote(obj.page.id)),
            "label": _("Delete Forever"),
            "classname": self.finalise_classname(self.delete_button_classnames),
            "title": _("Delete Forever")
        }

    def restore_button(self, obj):
        return {
            "url": reverse("wagtail_trash_restore", args=(obj.page.id,)),
            "label": _("Restore"),
            "classname": self.finalise_classname(self.restore_button_classnames),
            "title": _("Restore"),
        }

    def has_ancestor_in_bin(self, obj):
        parent = obj.get_parent()

        if not parent:
            return False

        ancestor_app_labels = list(
            parent.get_ancestors(inclusive=True).values_list(
                "content_type__app_label", flat=True
            )
        )

        return "wagtail_trash" in ancestor_app_labels

    def get_buttons_for_obj(
        self, obj, exclude=["edit", "delete"], classnames_add=None, classnames_exclude=None
    ):
        buttons = super().get_buttons_for_obj(
            obj, exclude, classnames_add, classnames_exclude
        )

        if "restore" not in (exclude or []):
            parent = obj.parent
            if parent and not self.has_ancestor_in_bin(parent):
                buttons.append(self.restore_button(obj))
            # buttons.append(self.restore_and_move_button(obj))

        buttons.append(self.real_delete_button(obj))

        return buttons


class TrashCanIndexView(IndexView):
    def get_page_title(self):
        return _("Trash Can")


class TrashCanModelAdmin(ModelAdmin):
    model = TrashCan
    menu_label = _("Trash Can")
    menu_icon = "bin"
    admin_order_field = "title"

    list_display = ("page_tree", "time_recycled", "user")
    # search_fields = ("title",)

    button_helper_class = TrashButtonHelper
    permission_helper_class = TrashPermissionHelper

    index_view_class = TrashCanIndexView
    index_template_name = "wagtail_trash/index.html"

    def page_tree(self, rb):
        descendants = rb.page.get_descendants(inclusive=True)

        depth = rb.page.depth
        output = ""

        for i, x in enumerate(descendants):
            output += "&nbsp;" * (x.depth - depth)

            if i == 0:
                output += "<strong>" + x.title + "</strong><br>"
            else:
                output += x.title + "<br>"

        return mark_safe(output)

    def get_queryset(self, request):
        # Create a bin if there is none
        trash_can_for_request(request)

        return super().get_queryset(request).prefetch_related("page")


modeladmin_register(TrashCanModelAdmin)


# move delete page hooks into main project
# @hooks.register("before_delete_page")
# def delete_page(request, page):
#     return trash_delete(request, page)


@hooks.register("construct_page_chooser_queryset")
def exclude_trash_can_from_chooser(pages, request):
    pages = pages.not_type(TrashCanPage)

    return pages


@hooks.register("construct_explorer_page_queryset")
def exclude_trash_can_from_explorer(parent_page, pages, request):
    pages = pages.not_type(TrashCanPage)

    return pages


@hooks.register("register_admin_urls")
def urlconf_time():
    return [
        path(
            "wagtail_trash/restore_and_move/<int:page_id>/",
            trash_move,
            name="wagtail_trash_move",
        ),
        path(
            "wagtail_trash/restore/<int:page_id>/",
            trash_restore,
            name="wagtail_trash_restore",
        ),
        path(
            "wagtail_trash/delete/<int:page_id>",
            trash_real_delete,
            name="wagtail_trash_real_delete",
        )
    ]
