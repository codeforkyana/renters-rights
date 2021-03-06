import json
from io import BytesIO
from unittest.mock import patch

from django.core.files import File
from django.test import Client, TransactionTestCase, override_settings
from django.urls import reverse
from freezegun import freeze_time
from hamcrest import assert_that, contains, contains_inanyorder, equal_to, has_length, not_, not_none
from PIL import Image

from noauth.models import User
from units.models import DOCUMENT, MOVE_IN_PICTURE, MOVE_OUT_PICTURE, Unit, UnitImage
from units.tests import UnitBaseTestCase


class UnitViewTests(UnitBaseTestCase):
    def test_index_view_logged_out(self):
        response = self.client.get(reverse("homepage"))
        self.assertTemplateUsed(response, "index-logged-out.html")

    def test_index_view_logged_in(self):
        c = Client()
        c.force_login(UnitViewTests.u)
        response = c.get(reverse("homepage"))
        self.assertTemplateUsed(response, "index.html")

    def test_list_view_no_units_returned_when_not_logged_in(self):
        response = self.client.get(reverse("unit-list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Add your first unit")
        self.assertQuerysetEqual(response.context["unit_list"], [])

    def test_list_view_returns_a_signed_in_users_units_one_unit(self):
        c = Client()
        c.force_login(UnitViewTests.u)
        response = c.get(reverse("unit-list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, UnitViewTests.unit.unit_address_1)
        assert_that(response.context["unit_list"], contains(UnitViewTests.unit))

    def test_list_view_returns_a_signed_in_users_units_two_units(self):
        unit2 = Unit.objects.create(unit_address_1="u2", owner=UnitViewTests.u)
        i1 = UnitImage.objects.create(
            image=self.get_image_file(size=(200, 200)), image_type=MOVE_IN_PICTURE, unit=unit2, owner=UnitViewTests.u
        )
        i2 = UnitImage.objects.create(
            image=self.get_image_file(size=(200, 200)), image_type=MOVE_OUT_PICTURE, unit=unit2, owner=UnitViewTests.u
        )
        i3 = UnitImage.objects.create(
            image=self.get_image_file(size=(200, 200)), image_type=DOCUMENT, unit=unit2, owner=UnitViewTests.u
        )

        c = Client()
        c.force_login(UnitViewTests.u)
        response = c.get(reverse("unit-list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, i1.thumbnail)
        self.assertContains(response, i2.thumbnail)
        self.assertContains(response, i3.thumbnail)
        self.assertContains(response, UnitViewTests.unit.unit_address_1)
        self.assertContains(response, unit2.unit_address_1)
        assert_that(response.context["unit_list"], contains_inanyorder(UnitViewTests.unit, unit2))

    def test_list_view_does_not_return_another_users_units(self):
        other_user = User.objects.create(is_active=True, username="tahani@al-jamil.com")
        other_user_unit = Unit.objects.create(unit_address_1="other", owner=other_user)

        c = Client()
        c.force_login(UnitViewTests.u)
        response = c.get(reverse("unit-list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, UnitViewTests.unit.unit_address_1)
        assert_that(response.context["unit_list"], contains(UnitViewTests.unit))
        assert_that(response.context["unit_list"], not_(contains(other_user_unit)))

    def test_detail_view_requires_login(self):
        view_url = reverse("unit-detail", args=[self.unit.slug])
        response = self.client.get(view_url)
        self.assertRedirects(response, f"{reverse('noauth:log-in')}?next={view_url}")

    def test_detail_view_returns_expected_unit(self):
        c = Client()
        c.force_login(UnitViewTests.u)
        response = c.get(reverse("unit-detail", args=[self.unit.slug]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, UnitViewTests.unit.unit_address_1)

    def test_detail_view_returns_expected_unit_with_images(self):
        i1 = UnitImage.objects.create(
            image=self.get_image_file(size=(200, 200)),
            image_type=MOVE_IN_PICTURE,
            unit=UnitViewTests.unit,
            owner=UnitViewTests.u,
        )
        i2 = UnitImage.objects.create(
            image=self.get_image_file(size=(200, 200)),
            image_type=MOVE_OUT_PICTURE,
            unit=UnitViewTests.unit,
            owner=UnitViewTests.u,
        )
        i3 = UnitImage.objects.create(
            image=self.get_image_file(size=(200, 200)), image_type=DOCUMENT, unit=UnitViewTests.unit, owner=UnitViewTests.u
        )

        c = Client()
        c.force_login(UnitViewTests.u)
        response = c.get(reverse("unit-detail", args=[self.unit.slug]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, UnitViewTests.unit.unit_address_1)
        self.assertContains(response, i1.thumbnail)
        self.assertContains(response, "Move-in picture uploaded")
        self.assertContains(response, i2.thumbnail)
        self.assertContains(response, "Move-out picture uploaded")
        self.assertContains(response, i3.thumbnail)
        self.assertContains(response, "Document uploaded")

    def test_create_view_requires_login(self):
        view_url = reverse("unit-create")
        response = self.client.get(view_url)
        self.assertRedirects(response, f"{reverse('noauth:log-in')}?next={view_url}")

    def test_create_view_creates_and_redirects_to_expected_url(self):
        c = Client()
        c.force_login(UnitViewTests.u)
        response = c.post(
            reverse("unit-create"), {"unit_address_1": "my_address", "unit_state": "KY", "unit_zip_code": "40906"}
        )
        self.assertRedirects(response, reverse("unit-list"))
        assert_that(Unit.objects.get(unit_address_1="my_address"), not_none())

    @override_settings(MAX_UNITS=1)
    def test_create_view_get_redirects_to_unit_list_if_maximum_units_created(self):
        c = Client()
        c.force_login(UnitViewTests.u)
        response = c.get(reverse("unit-create"))
        self.assertRedirects(response, reverse("unit-list"))
        assert_that(Unit.objects.for_user(UnitViewTests.u).count(), equal_to(1))

    @override_settings(MAX_UNITS=1)
    def test_create_view_post_redirects_to_unit_list_without_creating_if_maximum_units_created(self):
        c = Client()
        c.force_login(UnitViewTests.u)
        response = c.post(
            reverse("unit-create"), {"unit_address_1": "my_address", "unit_state": "KY", "unit_zip_code": "40906"}
        )
        self.assertRedirects(response, reverse("unit-list"))
        assert_that(Unit.objects.for_user(UnitViewTests.u).count(), equal_to(1))

    @freeze_time("2000-01-01")
    def test_sign_files(self):
        c = Client()
        c.force_login(UnitViewTests.u)
        response = c.post(
            reverse("sign-files", args=[UnitViewTests.unit.slug]),
            json.dumps({"files": ["file1.jpg", "file2.jpg"]}),
            content_type="application/json",
        )
        self.assertJSONEqual(
            str(response.content, encoding="utf8"),
            {
                "file1.jpg": {
                    "url": "https://renters-rights-uploads-test.s3.amazonaws.com/",
                    "fields": {
                        "acl": "private",
                        "Content-Type": "image/png",
                        "key": "eleanor@shellstrop.com/file1.jpg",
                        "AWSAccessKeyId": "INVALID",
                        "policy": "eyJleHBpcmF0aW9uIjogIjIwMDAtMDEtMDFUMDE6MDA6MDBaIiwgImNvbmRpdGlvbnMiOiBbeyJhY2wiOiAicHJpdmF0ZSJ9LCB7IkNvbnRlbnQtVHlwZSI6ICJpbWFnZS9wbmcifSwgWyJjb250ZW50LWxlbmd0aC1yYW5nZSIsIDUwMDAsIDE1MDAwMDAwXSwgeyJidWNrZXQiOiAicmVudGVycy1yaWdodHMtdXBsb2Fkcy10ZXN0In0sIHsia2V5IjogImVsZWFub3JAc2hlbGxzdHJvcC5jb20vZmlsZTEuanBnIn1dfQ==",
                        "signature": "i1HURmd5vT8qSQ6pWrE7MkxhteA=",
                    },
                },
                "file2.jpg": {
                    "url": "https://renters-rights-uploads-test.s3.amazonaws.com/",
                    "fields": {
                        "acl": "private",
                        "Content-Type": "image/png",
                        "key": "eleanor@shellstrop.com/file2.jpg",
                        "AWSAccessKeyId": "INVALID",
                        "policy": "eyJleHBpcmF0aW9uIjogIjIwMDAtMDEtMDFUMDE6MDA6MDBaIiwgImNvbmRpdGlvbnMiOiBbeyJhY2wiOiAicHJpdmF0ZSJ9LCB7IkNvbnRlbnQtVHlwZSI6ICJpbWFnZS9wbmcifSwgWyJjb250ZW50LWxlbmd0aC1yYW5nZSIsIDUwMDAsIDE1MDAwMDAwXSwgeyJidWNrZXQiOiAicmVudGVycy1yaWdodHMtdXBsb2Fkcy10ZXN0In0sIHsia2V5IjogImVsZWFub3JAc2hlbGxzdHJvcC5jb20vZmlsZTIuanBnIn1dfQ==",
                        "signature": "CQmgOFWj8WCawFd1JkUH3A7gcOs=",
                    },
                },
            },
        )

    @override_settings(AWS_S3_ENDPOINT_URL="http://url")
    @override_settings(AWS_S3_CUSTOM_DOMAIN="http://domain")
    @freeze_time("2000-01-01")
    def test_sign_files_local(self):
        c = Client()
        c.force_login(UnitViewTests.u)
        response = c.post(
            reverse("sign-files", args=[UnitViewTests.unit.slug]),
            json.dumps({"files": ["file1.jpg", "file2.jpg"]}),
            content_type="application/json",
        )
        self.assertJSONEqual(
            str(response.content, encoding="utf8"),
            {
                "file1.jpg": {
                    "url": "http://url/renters-rights-uploads-test",
                    "fields": {
                        "acl": "private",
                        "Content-Type": "image/png",
                        "key": "eleanor@shellstrop.com/file1.jpg",
                        "AWSAccessKeyId": "INVALID",
                        "policy": "eyJleHBpcmF0aW9uIjogIjIwMDAtMDEtMDFUMDE6MDA6MDBaIiwgImNvbmRpdGlvbnMiOiBbeyJhY2wiOiAicHJpdmF0ZSJ9LCB7IkNvbnRlbnQtVHlwZSI6ICJpbWFnZS9wbmcifSwgWyJjb250ZW50LWxlbmd0aC1yYW5nZSIsIDUwMDAsIDE1MDAwMDAwXSwgeyJidWNrZXQiOiAicmVudGVycy1yaWdodHMtdXBsb2Fkcy10ZXN0In0sIHsia2V5IjogImVsZWFub3JAc2hlbGxzdHJvcC5jb20vZmlsZTEuanBnIn1dfQ==",
                        "signature": "i1HURmd5vT8qSQ6pWrE7MkxhteA=",
                    },
                },
                "file2.jpg": {
                    "url": "http://url/renters-rights-uploads-test",
                    "fields": {
                        "acl": "private",
                        "Content-Type": "image/png",
                        "key": "eleanor@shellstrop.com/file2.jpg",
                        "AWSAccessKeyId": "INVALID",
                        "policy": "eyJleHBpcmF0aW9uIjogIjIwMDAtMDEtMDFUMDE6MDA6MDBaIiwgImNvbmRpdGlvbnMiOiBbeyJhY2wiOiAicHJpdmF0ZSJ9LCB7IkNvbnRlbnQtVHlwZSI6ICJpbWFnZS9wbmcifSwgWyJjb250ZW50LWxlbmd0aC1yYW5nZSIsIDUwMDAsIDE1MDAwMDAwXSwgeyJidWNrZXQiOiAicmVudGVycy1yaWdodHMtdXBsb2Fkcy10ZXN0In0sIHsia2V5IjogImVsZWFub3JAc2hlbGxzdHJvcC5jb20vZmlsZTIuanBnIn1dfQ==",
                        "signature": "CQmgOFWj8WCawFd1JkUH3A7gcOs=",
                    },
                },
            },
        )

    @override_settings(MAX_DOCUMENTS_PER_UNIT=1)
    @override_settings(MAX_MOVE_IN_PICTURES_PER_UNIT=1)
    @override_settings(MAX_MOVE_OUT_PICTURES_PER_UNIT=1)
    @patch("django.db.models.query.QuerySet.count")
    def test_sign_files_returns_400_if_over_total_file_limit(self, m_count):
        m_count.return_value = 3

        c = Client()
        c.force_login(UnitViewTests.u)
        response = c.post(
            reverse("sign-files", args=[UnitViewTests.unit.slug]),
            json.dumps({"files": ["file1.jpg"]}),
            content_type="application/json",
        )
        assert_that(response.status_code, equal_to(400))


class UnitAddDocumentsFormViewGetTests(UnitBaseTestCase):
    def test_unit_add_documents_requires_login(self):
        view_url = reverse("unit-add-documents", args=[UnitAddDocumentsFormViewGetTests.unit.slug])
        response = self.client.get(view_url)
        self.assertRedirects(response, f"{reverse('noauth:log-in')}?next={view_url}")

    def test_unit_add_move_in_pictures_requires_login(self):
        view_url = reverse("unit-add-move-in-pictures", args=[UnitAddDocumentsFormViewGetTests.unit.slug])
        response = self.client.get(view_url)
        self.assertRedirects(response, f"{reverse('noauth:log-in')}?next={view_url}")

    def test_unit_add_move_out_pictures_requires_login(self):
        view_url = reverse("unit-add-move-out-pictures", args=[UnitAddDocumentsFormViewGetTests.unit.slug])
        response = self.client.get(view_url)
        self.assertRedirects(response, f"{reverse('noauth:log-in')}?next={view_url}")

    def test_unit_add_documents_form_valid(self):
        c = Client()
        c.force_login(UnitAddDocumentsFormViewGetTests.u)

        response = c.get(reverse("unit-add-documents", args=[UnitAddDocumentsFormViewGetTests.unit.slug]))
        self.assertContains(response, "Documents:")

    def test_unit_add_move_in_pictures_form_valid(self):
        c = Client()
        c.force_login(UnitAddDocumentsFormViewGetTests.u)

        response = c.get(reverse("unit-add-move-in-pictures", args=[UnitAddDocumentsFormViewGetTests.unit.slug]))
        self.assertContains(response, "Move-in Pictures:")

    def test_unit_add_move_out_pictures_form_valid(self):
        c = Client()
        c.force_login(UnitAddDocumentsFormViewGetTests.u)

        response = c.get(reverse("unit-add-move-out-pictures", args=[UnitAddDocumentsFormViewGetTests.unit.slug]))
        self.assertContains(response, "Move-out Pictures:")

    @override_settings(UNIT_IMAGE_MIN_HEIGHT_AND_WIDTH=10)
    @override_settings(UNIT_IMAGE_MAX_HEIGHT_AND_WIDTH=20)
    @override_settings(UNIT_IMAGE_SIZES=[5, 10, 20])
    @override_settings(MAX_DOCUMENTS_PER_UNIT=1)
    def test_unit_add_documents_page_will_not_allow_add_if_aready_at_doc_limit(self):
        c = Client()
        c.force_login(UnitAddDocumentsFormViewGetTests.u)

        UnitImage.objects.create(
            image=UnitBaseTestCase.get_image_file(),
            unit=UnitAddDocumentsFormViewGetTests.unit,
            owner=UnitAddDocumentsFormViewGetTests.u,
        )

        response = c.get(reverse("unit-add-documents", args=[UnitAddDocumentsFormViewGetTests.unit.slug]))
        self.assertContains(response, "Go back")
        self.assertContains(response, "You have uploaded 1 of 1 allowed images")


class UnitAddDocumentsFormViewPostTests(TransactionTestCase):
    @staticmethod
    def get_image_file(name="test.png", ext="png", size=(50, 50), color=(256, 0, 0)):
        file_obj = BytesIO()
        image = Image.new("RGBA", size=size, color=color)
        image.save(file_obj, ext)
        file_obj.seek(0)
        return File(file_obj, name=name)

    @override_settings(UNIT_IMAGE_MIN_HEIGHT_AND_WIDTH=10)
    @override_settings(UNIT_IMAGE_MAX_HEIGHT_AND_WIDTH=20)
    @override_settings(UNIT_IMAGE_SIZES=[5, 10, 20])
    def test_unit_add_documents_valid_two_documents(self):
        u = User.objects.create(is_active=True, username="eleanor@shellstrop.com")
        unit = Unit.objects.create(unit_address_1="u", owner=u)

        c = Client()
        c.force_login(u)

        i1 = UnitBaseTestCase.get_image_file()
        i2 = UnitBaseTestCase.get_image_file()

        response = c.post(reverse("unit-add-documents", args=[unit.slug]), {"images": [i1, i2]})
        self.assertRedirects(response, reverse("unit-list"))
        unit.refresh_from_db()
        assert_that(unit.unitimage_set.all(), has_length(2))

    def test_unit_add_documents_no_documents_returns_error(self):
        u = User.objects.create(is_active=True, username="eleanor2@shellstrop.com")
        unit = Unit.objects.create(unit_address_1="u", owner=u)

        c = Client()
        c.force_login(u)

        response = c.post(reverse("unit-add-documents", args=[unit.slug]), {"s3_images": ""})
        assert_that(response.status_code, equal_to(200))
        self.assertContains(response, "Please select at least one image.")
        unit.refresh_from_db()
        assert_that(unit.unitimage_set.all(), has_length(0))

    @patch("django.forms.ModelForm.save")
    @patch("boto3.client")
    @override_settings(UNIT_IMAGE_MIN_HEIGHT_AND_WIDTH=10)
    def test_unit_add_documents_valid_two_documents_s3(self, m_client, m_save):
        u = User.objects.create(is_active=True, username="eleanor2@shellstrop.com")
        unit = Unit.objects.create(unit_address_1="u", owner=u)
        m_save.return_value = unit

        i1 = UnitBaseTestCase.get_image_file()
        i2 = UnitBaseTestCase.get_image_file()
        m_client.return_value.get_object.side_effect = [{"Body": i1}, {"Body": i2}]

        c = Client()
        c.force_login(u)

        response = c.post(reverse("unit-add-documents", args=[unit.slug]), {"s3_images": "file1.jpg, file2.jpg"})
        self.assertRedirects(response, reverse("unit-list"))
        unit.refresh_from_db()
        assert_that(unit.unitimage_set.all(), has_length(2))

    @override_settings(UNIT_IMAGE_MIN_HEIGHT_AND_WIDTH=10)
    @override_settings(UNIT_IMAGE_MAX_HEIGHT_AND_WIDTH=20)
    @override_settings(UNIT_IMAGE_SIZES=[5, 10, 20])
    def test_unit_add_move_in_pictures_valid_two_move_in_pictures(self):
        u = User.objects.create(is_active=True, username="eleanor@shellstrop.com")
        unit = Unit.objects.create(unit_address_1="u", owner=u)

        c = Client()
        c.force_login(u)

        i1 = UnitBaseTestCase.get_image_file()
        i2 = UnitBaseTestCase.get_image_file()

        response = c.post(reverse("unit-add-move-in-pictures", args=[unit.slug]), {"images": [i1, i2]})
        self.assertRedirects(response, reverse("unit-list"))
        unit.refresh_from_db()
        assert_that(unit.unitimage_set.all(), has_length(2))

    @patch("django.forms.ModelForm.save")
    @patch("boto3.client")
    @override_settings(UNIT_IMAGE_MIN_HEIGHT_AND_WIDTH=10)
    def test_unit_add_move_in_pictures_valid_two_move_in_pictures_s3(self, m_client, m_save):
        u = User.objects.create(is_active=True, username="eleanor2@shellstrop.com")
        unit = Unit.objects.create(unit_address_1="u", owner=u)
        m_save.return_value = unit

        i1 = UnitBaseTestCase.get_image_file()
        i2 = UnitBaseTestCase.get_image_file()
        m_client.return_value.get_object.side_effect = [{"Body": i1}, {"Body": i2}]

        c = Client()
        c.force_login(u)

        response = c.post(reverse("unit-add-move-in-pictures", args=[unit.slug]), {"s3_images": "file1.jpg, file2.jpg"})
        self.assertRedirects(response, reverse("unit-list"))
        unit.refresh_from_db()
        assert_that(unit.unitimage_set.all(), has_length(2))

    def test_unit_add_move_in_pictures_no_pictures_returns_error(self):
        u = User.objects.create(is_active=True, username="eleanor2@shellstrop.com")
        unit = Unit.objects.create(unit_address_1="u", owner=u)

        c = Client()
        c.force_login(u)

        response = c.post(reverse("unit-add-move-in-pictures", args=[unit.slug]), {"s3_images": ""})
        assert_that(response.status_code, equal_to(200))
        self.assertContains(response, "Please select at least one image.")
        unit.refresh_from_db()
        assert_that(unit.unitimage_set.all(), has_length(0))

    @override_settings(UNIT_IMAGE_MIN_HEIGHT_AND_WIDTH=10)
    @override_settings(UNIT_IMAGE_MAX_HEIGHT_AND_WIDTH=20)
    @override_settings(UNIT_IMAGE_SIZES=[5, 10, 20])
    def test_unit_add_move_out_pictures_valid_two_move_out_pictures(self):
        u = User.objects.create(is_active=True, username="eleanor@shellstrop.com")
        unit = Unit.objects.create(unit_address_1="u", owner=u)

        c = Client()
        c.force_login(u)

        i1 = UnitBaseTestCase.get_image_file()
        i2 = UnitBaseTestCase.get_image_file()

        response = c.post(reverse("unit-add-move-out-pictures", args=[unit.slug]), {"images": [i1, i2]})
        self.assertRedirects(response, reverse("unit-list"))
        unit.refresh_from_db()
        assert_that(unit.unitimage_set.all(), has_length(2))

    @patch("django.forms.ModelForm.save")
    @patch("boto3.client")
    @override_settings(UNIT_IMAGE_MIN_HEIGHT_AND_WIDTH=10)
    def test_unit_add_move_out_pictures_valid_two_move_out_pictures_s3(self, m_client, m_save):
        u = User.objects.create(is_active=True, username="eleanor2@shellstrop.com")
        unit = Unit.objects.create(unit_address_1="u", owner=u)
        m_save.return_value = unit

        i1 = UnitBaseTestCase.get_image_file()
        i2 = UnitBaseTestCase.get_image_file()
        m_client.return_value.get_object.side_effect = [{"Body": i1}, {"Body": i2}]

        c = Client()
        c.force_login(u)

        response = c.post(reverse("unit-add-move-out-pictures", args=[unit.slug]), {"s3_images": "file1.jpg, file2.jpg"})
        self.assertRedirects(response, reverse("unit-list"))
        unit.refresh_from_db()
        assert_that(unit.unitimage_set.all(), has_length(2))

    def test_unit_add_move_out_pictures_no_pictures_returns_error(self):
        u = User.objects.create(is_active=True, username="eleanor2@shellstrop.com")
        unit = Unit.objects.create(unit_address_1="u", owner=u)

        c = Client()
        c.force_login(u)

        response = c.post(reverse("unit-add-move-out-pictures", args=[unit.slug]), {"s3_images": ""})
        assert_that(response.status_code, equal_to(200))
        self.assertContains(response, "Please select at least one image.")
        unit.refresh_from_db()
        assert_that(unit.unitimage_set.all(), has_length(0))


class UnitDeleteViewTests(UnitBaseTestCase):
    def test_get_returns_form(self):
        u = User.objects.create(is_active=True, username="eleanor2@shellstrop.com")
        unit = Unit.objects.create(unit_address_1="u", owner=u)

        c = Client()
        c.force_login(u)

        response = c.get(reverse("unit-delete", args=[unit.slug]))
        assert_that(response.status_code, equal_to(200))
        self.assertContains(response, "Are you sure you want to delete this unit?")

    def test_post_deletes_unit(self):
        u = User.objects.create(is_active=True, username="eleanor2@shellstrop.com")
        unit = Unit.objects.create(unit_address_1="u", owner=u)

        c = Client()
        c.force_login(u)

        assert_that(Unit.objects.filter(id=unit.id).count(), equal_to(1))
        response = c.post(reverse("unit-delete", args=[unit.slug]))
        self.assertRedirects(response, reverse("unit-list"))
        assert_that(Unit.objects.filter(id=unit.id).count(), equal_to(0))
