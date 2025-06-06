from medcat.components.tagging import tagger
from medcat.components import types

import unittest

from ..helper import ComponentInitTests


class TaggerInitTests(ComponentInitTests, unittest.TestCase):
    comp_type = types.CoreComponentType.tagging
    default_cls = tagger.TagAndSkipTagger
    module = tagger
