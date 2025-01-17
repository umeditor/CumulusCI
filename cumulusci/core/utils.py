""" Utilities for CumulusCI Core

import_global: task class defn import helper
process_bool_arg: determine true/false for a commandline arg
decode_to_unicode: get unicode string from sf api """

from datetime import datetime
import copy
import glob
import pytz
import time
import yaml
from collections import OrderedDict

from cumulusci.core.exceptions import ConfigMergeError


def import_global(path):
    """ Import a class from a string module class path """
    components = path.split(".")
    module = components[:-1]
    module = ".".join(module)
    mod = __import__(module, fromlist=[str(components[-1])])
    return getattr(mod, str(components[-1]))


# For backwards-compatibility
import_class = import_global


def parse_datetime(dt_str, format):
    """Create a timezone-aware datetime object from a datetime string."""
    t = time.strptime(dt_str, format)
    return datetime(t[0], t[1], t[2], t[3], t[4], t[5], t[6], pytz.UTC)


def process_bool_arg(arg):
    """ Determine True/False from argument """
    if isinstance(arg, bool):
        return arg
    elif isinstance(arg, str):
        if arg.lower() in ["true", "1"]:
            return True
        elif arg.lower() in ["false", "0"]:
            return False


def process_glob_list_arg(arg):
    """Convert a list of glob patterns or filenames into a list of files
    The initial list can take the form of a comma-separated string or
    a proper list. Order is preserved, but duplicates will be removed.

    Note: this function processes glob patterns, but doesn't validate
    that the files actually exist. For example, if the pattern is
    'foo.bar' and there is no file named 'foo.bar', the literal string
    'foo.bar' will be included in the returned files.

    Similarly, if the pattern is '*.baz' and it doesn't match any files,
    the literal string '*.baz' will be returned.
    """
    initial_list = process_list_arg(arg)

    if not arg:
        return []

    files = []
    for path in initial_list:
        more_files = glob.glob(path, recursive=True)
        if len(more_files):
            files += sorted(more_files)
        else:
            files.append(path)
    # In python 3.6+ dict is ordered, so we'll use it to weed
    # out duplicates. We can't use a set because sets aren't ordered.
    return list(dict.fromkeys(files))


def process_list_arg(arg):
    """ Parse a string into a list separated by commas with whitespace stripped """
    if isinstance(arg, list):
        return arg
    elif isinstance(arg, str):
        args = []
        for part in arg.split(","):
            args.append(part.strip())
        return args


def decode_to_unicode(content):
    """ decode ISO-8859-1 to unicode, when using sf api """
    if content and not isinstance(content, str):
        try:
            # Try to decode ISO-8859-1 to unicode
            return content.decode("ISO-8859-1")
        except UnicodeEncodeError:
            # Assume content is unicode already
            return content
    return content


class OrderedLoader(yaml.SafeLoader):
    def _construct_dict_mapping(self, node):
        self.flatten_mapping(node)
        return OrderedDict(self.construct_pairs(node))


OrderedLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    OrderedLoader._construct_dict_mapping,
)


def represent_ordereddict(dumper, data):
    value = []

    for item_key, item_value in data.items():
        node_key = dumper.represent_data(item_key)
        node_value = dumper.represent_data(item_value)

        value.append((node_key, node_value))

    return yaml.nodes.MappingNode("tag:yaml.org,2002:map", value)


class OrderedDumper(yaml.SafeDumper):
    pass


OrderedDumper.add_representer(OrderedDict, represent_ordereddict)


def ordered_yaml_load(stream,):
    """ Load YAML file with OrderedDict, needed for Py2

    code adapted from: https://stackoverflow.com/a/21912744/5042831"""

    return yaml.load(stream, OrderedLoader)


def ordered_yaml_dump(content, stream):
    return yaml.dump(content, stream, Dumper=OrderedDumper)


def merge_config(configs):
    """ recursively deep-merge the configs into one another (highest priority comes first) """
    new_config = {}

    for name, config in configs.items():
        new_config = dictmerge(new_config, config, name)

    return new_config


def dictmerge(a, b, name=None):
    """ Deeply merge two ``dict``s that consist of lists, dicts, and scalars.
    This function (recursively) merges ``b`` INTO ``a``, does not copy any values, and returns ``a``.

    based on https://stackoverflow.com/a/15836901/5042831
    NOTE: tuples and arbitrary objects are NOT handled and will raise TypeError """

    key = None

    if b is None:
        return a

    try:
        if a is None or isinstance(a, (bytes, int, str, float)):
            # first run, or if ``a``` is a scalar
            a = b
        elif isinstance(a, list):
            # lists can be only appended
            if isinstance(b, list):
                # merge lists
                a.extend(b)
            else:
                # append to list
                a.append(b)
        elif isinstance(a, dict):
            # dicts must be merged
            if isinstance(b, dict):
                for key in b:
                    if key in a:
                        a[key] = dictmerge(a[key], b[key], name)
                    else:
                        a[key] = copy.copy(b[key])
            else:
                raise TypeError(
                    'Cannot merge non-dict of type "{}" into dict "{}"'.format(
                        type(b), a
                    )
                )
        else:
            raise TypeError(
                'dictmerge does not supporting merging "{}" into "{}"'.format(
                    type(b), type(a)
                )
            )
    except TypeError as e:
        raise ConfigMergeError(
            'TypeError "{}" in key "{}" when merging "{}" into "{}"'.format(
                e, key, type(b), type(a)
            ),
            config_name=name,
        )
    return a
