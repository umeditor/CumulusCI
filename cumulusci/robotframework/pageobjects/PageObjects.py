from robot.api import logger
from robot.libraries.BuiltIn import BuiltIn, RobotNotRunningError
from cumulusci.robotframework.pageobjects.baseobjects import BasePage
import inspect
import robot.utils
import os
import sys


def get_keyword_names(obj):
    """Returns a list of method names for the given object

    This excludes methods that begin with an underscore, and
    also excludes the special method `get_keyword_names`.
    """
    names = [
        member[0]
        for member in inspect.getmembers(obj, inspect.isroutine)
        if (not member[0].startswith("_")) and member[0] != "get_keyword_names"
    ]
    return names


class PageObjects(object):
    """Keyword library for importing and using page objects

    When importing, you can include one or more paths to python
    files that define page objects. For example, if you have a set
    of classes in robot/HEDA/resources/PageObjects.py, you can import
    this library into a test case like this:

    | Library  cumulusci.robotframework.PageObjects
    | ...  robot/HEDA/resources/PageObjects.py

    Page object classes need to use the @pageobject decorator from
    cumulusci.robotframework.pageobjects. The decorator takes two
    parameters: page_type and object_name. Both are arbitrary strings,
    but together should uniquely identify a collection of keywords for
    a page or objects on a page.

    Examples of page_type are Listing, Home, Detail, etc. Object types
    can be actual object types (Contact), custom object
    (Custom_object__c) or a logical name for a type of page (eg:
    AppointmentManager).

    Example:

    | from cumulusci.robotframework.pageobjects import BasePage
    | from cumulusci.robotframework.pageobjects import pageobject
    | ...
    | @pageobject(page_type="Detail", object_name="Custom__c")
    | class CustomDetailPage(BasePage):
    |     ...
    """

    ROBOT_LIBRARY_SCOPE = "TEST SUITE"
    registry = {}

    def __init__(self, *args):
        self.builtin = BuiltIn()
        logger.debug("initializing PageObjects...")
        importer = robot.utils.Importer()

        for file_path in args:
            try:
                importer.import_class_or_module_by_path(os.path.abspath(file_path))
                logger.debug("imported page object {}".format(file_path))
            except Exception as e:
                logger.warn(str(e))
        self.current_page_object = None

        # Start with this library at the front of the library search order;
        # that may change as page objects are loaded.
        try:
            self.builtin.set_library_search_order("PageObjects")
        except RobotNotRunningError:
            # this should only happen when trying to load this library
            # via the robot_libdoc task, in which case we don't care
            # whether this throws an error or not.
            pass

    @classmethod
    def _reset(cls):
        """Reset the internal data structures used to manage page objects

        This is to aid testing. It probably shouldn't be used at any other time.
        """
        for pobj in cls.registry.values():
            if pobj.__module__ in sys.modules:
                del sys.modules[pobj.__module__]
        cls.registry = {}

    @property
    def selenium(self):
        return self.builtin.get_library_instance("SeleniumLibrary")

    def __getattr__(self, name):
        """Return the keyword from the current page object

        This method is required by robot's dynamic library api
        """
        if self.current_page_object is None:
            raise AttributeError(name)
        return getattr(self.current_page_object, name)

    def get_keyword_names(self):
        """
        This method is required by robot's dynamic library api
        """
        names = get_keyword_names(self)
        if self.current_page_object is not None:
            names = names + get_keyword_names(self.current_page_object)
        return names

    def log_page_object_keywords(self):
        """Logs page objects and their keywords for all page objects
           which have been imported into the current suite.
        """
        for key in sorted(self.registry.keys()):
            pobj = self.registry[key]
            keywords = get_keyword_names(pobj)
            logger.info("{}: {}".format(key, ", ".join(keywords)))

    def get_page_object(self, page_type, object_name):
        """Return an instance of a page object

        This is useful if you want to call a single page object method
        from some other keyword without having to go to another page
        or load the page object into a page.

        This works a lot like robot's built-in "get library instance"
        keyword, but you can specify the page object by page type
        and object name rather than the library name, and it will
        autoload the appropriate library (assuming its module has
        been imported).
        """

        if (page_type, object_name) in self.registry:
            cls = self.registry[(page_type, object_name)]
            instance = cls()
            libname = instance.__class__.__name__

        else:
            # Page object has not been registered. Try to find
            # an appropriate generic class. For example, if
            # the requested page is "Listing", "Contact", look
            # for a "ListingPage" class. If we find it, we'll
            # create a library named "ContactListingPage"
            instance = None
            target = "{}Page".format(page_type)
            for subclass in BasePage.__subclasses__():
                if subclass.__name__ == target:
                    instance = subclass(object_name)
                    libname = "{}{}Page".format(
                        object_name, page_type
                    )  # eg: ContactListingPage
                    break

            if instance is None:
                raise Exception(
                    "Unable to find a page object for '{} {}'".format(
                        page_type, object_name
                    )
                )

        try:
            pobj = self.builtin.get_library_instance(libname)
        except Exception:
            # Hasn't been imported. Attempt to import it with the given name
            # for the given object; If this fails, just let it bubble up
            # because there's nothing else we can do.
            self.builtin.import_library(
                "cumulusci.robotframework.pageobjects._PageObjectLibrary",
                instance,
                libname,
                "WITH NAME",
                libname,
            )
            # sure would be nice if import_library returned the instance. Just sayin'.
            pobj = self.builtin.get_library_instance(libname)

        return pobj

    def go_to_page(self, page_type, object_name, **kwargs):
        """Go to the page of the given page object.

        The URL will be computed from the page_type and object_name
        associated with the object, if possible.

        Different pages support different additional arguments. For
        example, a Listing page supports the keyword argument `filter_name`.

        If this keyword is able to navigate to a page, the keyword
        `load page object` will automatically be called to load the keywords
        for the page.

        Custom page objects may define the function `_go_to_page`,
        which will be passed in all of the keyword arguments from this
        keyword. This allows each page object to define its own URL
        mapping using whatever algorithm it chooses.  The only
        requirement of the function is that it should compute an
        appropriate url and then call `self.selenium.go_to` with the
        URL.

        It is also recommended that the keyword wait until it knows
        that the page has finished rendering before returning (eg: by
        calling `self.salesforce.wait_until_loading_is_complete()`)
        """
        pobj = self.get_page_object(page_type, object_name)
        try:
            pobj._go_to_page(**kwargs)
            self._set_current_page_object(pobj)
        except Exception:
            self.selenium.capture_page_screenshot()
            raise

    def current_page_should_be(self, page_type, object_name, **kwargs):
        """Verifies that the page appears to be the requested page

        If the page matches the given page object or contains the
        given page object, the keyword will pass.a

        When this keyword is called, it will try to get the page
        object for the given page_tyope and object_name, and call the
        method `_is_current_page`.

        Custom page objects may define this function in whatever
        manner is necessary to determine that the current page is or
        contains the given page object. The only requirement is that
        this function raise an exception if it determines the current
        page either doesn't represent the page object or doesn't
        contain the page object.

        The default implementation of the function uses the page URL
        and compares it to a pattern based off of the page_type and
        object_name.

        """
        pobj = self.get_page_object(page_type, object_name)
        try:
            pobj._is_current_page(**kwargs)
            self.load_page_object(page_type, object_name)
        except Exception:
            self.selenium.capture_page_screenshot()
            raise

    def load_page_object(self, page_type, object_name=None):
        """Load the keywords for the page object identified by the type and object name

        The page type / object name pair must have been registered
        using the cumulusci.robotframework.pageobject decorator.
        """
        pobj = self.get_page_object(page_type, object_name)
        self._set_current_page_object(pobj)
        return pobj

    def _set_current_page_object(self, pobj):
        """This does the work of importing the keywords for the given page object

        Multiple page objects may be loaded. Each page object will be added
        to the front of robot's library search order. Note: this search order
        gets reset at the start of every suite.
        """

        self.current_page_object = pobj
        libname = pobj._libname

        old_order = list(self.builtin.set_library_search_order())
        if libname in old_order:
            old_order.remove(libname)
        new_order = [libname] + old_order
        self.builtin.log("new search order: {}".format(new_order), "DEBUG")
        self.builtin.set_library_search_order(*new_order)
        return pobj
