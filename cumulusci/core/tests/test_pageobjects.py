"""Tests for the PageObjects class

Testing notes:

The PageObjects library uses robot's BuiltIn library. However,
instantiating that will throw an error if done outside the context of
a running robot test. To work around that, these tests mock out the
_get_context method to fool the BuiltIn library into not complaining.

These tests use two external files in the same directory as this test:
FooTestPage.py and BarTestPage.py. FooTestPage has a single keyword,
BarTestPage has two.

"""

import unittest
import os.path
from unittest import mock
from cumulusci.robotframework import PageObjects
from cumulusci.robotframework.CumulusCI import CumulusCI
from cumulusci.robotframework.pageobjects.PageObjectLibrary import _PageObjectLibrary
import robot.utils


HERE = os.path.dirname(__file__)
FOO_PATH = os.path.join(HERE, "FooTestPage.py")
BAR_PATH = os.path.join(HERE, "BarTestPage.py")
CORE_KEYWORDS = [
    "current_page_should_be",
    "get_page_object",
    "go_to_page",
    "load_page_object",
    "log_page_object_keywords",
]

# this is the importer used by the page objects, which makes it easy
# peasy to import by file path
importer = robot.utils.Importer()


class MockGetLibraryInstance:
    libs = {
        "SeleniumLibrary": mock.Mock(),
        "cumulusci.robotframework.CumulusCI": CumulusCI(),
        "cumulusci.robotframework.Salesforce": mock.Mock(),
    }

    def __call__(self, libname):
        if libname in self.libs:
            return self.libs[libname]
        else:
            raise Exception("unknown library: {}".format(libname))


@mock.patch(
    "robot.libraries.BuiltIn.BuiltIn.get_library_instance",
    side_effect=MockGetLibraryInstance(),
)
# We have to mock out _get_context or the robot libraries will
# throw an exception saying it cannot access the execution context.
@mock.patch("robot.libraries.BuiltIn.BuiltIn._get_context")
class TestPageObjects(unittest.TestCase):
    def test_PageObject(self, get_context_mock, get_library_instance_mock):
        po = PageObjects()
        self.assertEqual(po.get_keyword_names(), CORE_KEYWORDS)
        self.assertEqual(po.registry, {})

        po = PageObjects(FOO_PATH, BAR_PATH)
        if hasattr(self, "assertCountEqual"):
            self.assertCountEqual(
                po.registry.keys(), (("Test", "Foo__c"), ("Test", "Bar__c"))
            )
        else:
            # gah! python3 renamed this assert
            self.assertItemsEqual(
                po.registry.keys(), (("Test", "Foo__c"), ("Test", "Bar__c"))
            )

        # The page object class will have been imported by robot.utils.Importer,
        # so we need to use that here to validate which class got imported.
        FooTestPage = importer.import_class_or_module_by_path(FOO_PATH)
        BarTestPage = importer.import_class_or_module_by_path(BAR_PATH)
        self.assertEqual(po.registry[("Test", "Foo__c")], FooTestPage)
        self.assertEqual(po.registry[("Test", "Bar__c")], BarTestPage)

    def test_namespaced_object_name(self, get_context_mock, get_library_instance_mock):
        """Verify that the object name is prefixed by the namespace when there's a namespace"""
        with mock.patch.object(
            CumulusCI, "get_namespace_prefix", return_value="foobar__"
        ):
            po = PageObjects(FOO_PATH)

            FooTestPage = importer.import_class_or_module_by_path(FOO_PATH)
            MockGetLibraryInstance.libs["FooTestPage"] = _PageObjectLibrary(
                FooTestPage()
            )

            pobj = po.get_page_object("Test", "Foo__c")
            self.assertEqual(pobj.object_name, "foobar__Foo__c")

    def test_non_namespaced_object_name(
        self, get_context_mock, get_library_instance_mock
    ):
        """Verify that the object name is not prefixed by a namespace when there is no namespace"""
        with mock.patch.object(CumulusCI, "get_namespace_prefix", return_value=""):
            po = PageObjects(FOO_PATH)

            FooTestPage = importer.import_class_or_module_by_path(FOO_PATH)
            MockGetLibraryInstance.libs["FooTestPage"] = _PageObjectLibrary(
                FooTestPage()
            )

            pobj = po.get_page_object("Test", "Foo__c")
            self.assertEqual(pobj.object_name, "Foo__c")
