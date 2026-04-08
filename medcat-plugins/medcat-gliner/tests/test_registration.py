from unittest import TestCase
import re

from medcat.components import types
from medcat import __version__ as mct_ver


def is_before_automatic_addon_init():
    ver_match = re.match(r"(\d+)\.(\d+)\.(\d+).*", mct_ver)
    version = tuple([int(part) for part in ver_match.group(1, 2, 3)])
    return version < (2, 5, 0)


if is_before_automatic_addon_init():
    print("Loading in Pre medcat==2.5.0")
    print("So I need to manually do an import to get registration done")
    print("After 2.5.0 this should be picked up by core lib automatically")
    import medcat_gliner  # noqa


class HasBeenRegisteredTests(TestCase):

    def test_has_been_registered(self):
        registrations = types.get_registered_components(
            types.CoreComponentType.ner)
        self.assertTrue(any(
            "gliner" in reg_name for reg_name, _ in registrations
        ))
        if not is_before_automatic_addon_init():
            # NOTE: prior to v2.5 there was an issue with registrations
            #       after they were made un-lazy such that the class name
            #       wasn't shown (i.e the results from registrations was
            #       different for lazy and non-lazy components)
            self.assertTrue(any(
                "gliner" in reg_cls.lower() for _, reg_cls in registrations
            ))

    def test_registered_once(self):
        registrations = types.get_registered_components(
            types.CoreComponentType.ner)
        self.assertEqual(sum(
            "gliner" in reg_name for reg_name, _ in registrations
        ), 1)
        if not is_before_automatic_addon_init():
            # NOTE: prior to v2.5 there was an issue with registrations
            #       after they were made un-lazy such that the class name
            #       wasn't shown (i.e the results from registrations was
            #       different for lazy and non-lazy components)
            self.assertEqual(sum(
                "gliner" in reg_cls.lower() for _, reg_cls in registrations
            ), 1)

    def test_get_creator(self):
        creator = types.get_component_creator(
            types.CoreComponentType.ner, "gliner_ner")
        from medcat_gliner.gliner_ner import GlinerNER
        self.assertIs(creator.__self__, GlinerNER)
